#!/usr/bin/env python3
"""Common config entry point for GUI launch, diagnostics and service generation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib
import platform
import zipfile

from runtime_config import ConfigError, acquire_runtime_lease, install_drive_aliases, load_config, load_voice_registry


def systemd_quote(value):
    # systemd has its own quoting/specifier rules; do not use shell quoting.
    value = str(value)
    if any(c in value for c in '\n\r\x00'):
        raise ConfigError('Newlines are not supported in service paths')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def render_service(config,server_path=None):
    if config.config_file is None:
        raise ConfigError('Service cài cho khách cần cấu hình tường minh')
    server = Path(server_path) if server_path else Path(__file__).with_name('server.py')
    command = ' '.join(systemd_quote(p) for p in
                       [sys.executable, server, '--config', config.config_file])
    return ('[Unit]\nDescription=A.I.VOICE2 local TTS for Anki\nAfter=default.target\n\n'
            '[Service]\nType=simple\nExecStart=' + command + '\n'
            'Environment=PYTHONUNBUFFERED=1\nRestart=on-failure\nRestartSec=5\n'
            'TimeoutStopSec=10\n\n[Install]\nWantedBy=default.target\n')


def diagnose(config):
    registry = load_voice_registry(config.voice_registry)
    required = [config.app_dir / p for p in
                ['aivoice.exe', 'aitalk_engine.dll', 'Lib/AITalk/aitalk.lic',
                 'Lang/standard/standard.aildic']]
    required.append(config.worker)
    unknown, incomplete = [], []
    for folder in sorted((config.app_dir / 'Voice').glob('*')):
        if not folder.is_dir():
            continue
        if folder.name not in registry:
            unknown.append(folder.name)
            continue
        dialect = registry[folder.name]['language']
        packages=sorted(folder.glob('*.aivdic'))
        canonical=folder/(folder.name+'.aivdic')
        package=canonical if canonical.is_file() else (packages[0] if len(packages)==1 else canonical)
        files = [package, folder / 'voice.lic',
                 config.app_dir / 'Lang' / dialect / (dialect + '.aildic')]
        if any(not p.is_file() for p in files):
            incomplete.append(folder.name)
    missing = [str(p) for p in required if not p.is_file()]
    return {'config': config.as_dict(), 'missing_files': missing,
            'unregistered_voices': unknown, 'incomplete_voices': incomplete,
            'prefixes_initialized': {name:(prefix/'system.reg').is_file()
                                     for name,prefix in [('gui',config.gui_prefix),('engine',config.engine_prefix)]},
            'files_ready': not missing and not unknown and not incomplete,
            'scope': 'Read-only file/config checks; no audio, API or activation test'}


def verify_files(config):
    if config.config_file is None:raise ConfigError('File verification needs a managed config')
    root=config.config_file.parent.parent
    manifest=json.loads((root/'install-manifest.json').read_text())
    failures=[]
    for relative,expected in manifest['files'].items():
        path=root/relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ConfigError('Invalid file manifest path')
        if not path.is_file():failures.append({'path':relative,'error':'missing'})
        else:
            with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=expected:failures.append({'path':relative,'error':'hash-mismatch'})
    return {'checked':len(manifest['files']),'failures':failures,'passed':not failures}


def support_snapshot(config):
    result={'diagnostic':diagnose(config),'platform':{'system':platform.system(),'machine':platform.machine(),
                                                      'python':platform.python_version()},
            'scope':'Metadata only; no logs, input text, audio, raw licenses, activation or Anki collection'}
    if config.config_file:
        root=config.config_file.parent.parent
        manifest=root/'install-manifest.json'
        if manifest.is_file():
            data=json.loads(manifest.read_text())
            result['installation']={key:data.get(key) for key in ['schema_version','baseline_id','status','selected_voices']}
    replacements=[(str(config.app_dir),'[APP]'),(str(config.runtime_dir),'[RUNTIME]'),
                  (str(config.engine_prefix),'[ENGINE_PREFIX]'),(str(config.gui_prefix),'[GUI_PREFIX]'),
                  (str(config.cache_dir),'[CACHE]'),(str(config.log_dir),'[LOGS]'),(str(Path.home()),'[HOME]')]
    replacements.insert(0,(str(config.voice_registry),'[VOICE_REGISTRY]'))
    if config.config_file:
        replacements.insert(-1,(str(config.config_file.parent.parent),'[INSTALL]'))
    def redact(value):
        if isinstance(value,str):
            for source,target in replacements:
                if len(source)>1:value=value.replace(source,target)
            return value
        if isinstance(value,dict):return {key:redact(item) for key,item in value.items()}
        if isinstance(value,list):return [redact(item) for item in value]
        return value
    return redact(result)


def launch_gui(config):
    if config.config_file is None:
        raise ConfigError('GUI launcher cần config tường minh để dùng cùng app với backend')
    app = config.app_dir / 'aivoice.exe'
    if not app.is_file():
        raise ConfigError(f'Không có Editor tại {app}')
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    lease=acquire_runtime_lease(config)
    env = dict(os.environ, WINEPREFIX=str(config.gui_prefix), WINEDEBUG='-all',
               WINEDLLOVERRIDES='mscoree,mshtml=')
    # Preserve the desktop's selected input method instead of forcing fcitx.
    try:
        install_drive_aliases(config, config.gui_prefix)
        with (config.log_dir / 'gui.log').open('ab', buffering=0) as log:
            return subprocess.call(['wine', config.wine_path(app)], env=env,
                                   cwd=config.app_dir, stdout=log, stderr=subprocess.STDOUT)
    finally:
        if lease:lease.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--output',type=Path)
    parser.add_argument('command', choices=['show-config', 'diagnose', 'gui', 'render-service','verify-files','support-preview','export-support'])
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.command == 'gui':
            return launch_gui(config)
        if args.command == 'render-service':
            print(render_service(config), end='')
        elif args.command=='verify-files':
            result=verify_files(config);print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
        elif args.command in ('support-preview','export-support'):
            result=support_snapshot(config)
            if args.command=='support-preview':print(json.dumps(result,ensure_ascii=False,indent=2))
            else:
                if args.output is None:raise ConfigError('Chọn --output để lưu support ZIP cục bộ')
                if args.output.exists():raise ConfigError('Output đã tồn tại; chọn tên báo cáo mới')
                with zipfile.ZipFile(args.output,'x',zipfile.ZIP_DEFLATED) as bundle:
                    bundle.writestr('support-summary.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                print(args.output)
        else:
            result = diagnose(config) if args.command == 'diagnose' else config.as_dict()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if args.command == 'diagnose' and not result['files_ready']:
                return 1
        return 0
    except (ConfigError, OSError, ValueError) as error:
        print(f'A.I.VOICE2: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
