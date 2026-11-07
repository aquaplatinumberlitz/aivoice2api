#!/usr/bin/env python3
"""Build/run the auth probe against this copied installation and isolated prefix.

Reads the existing engine license with its shipped decoder; does not change
license contents, expiry, activation, or the engine's authentication checks.
License code stays in child environment and is never printed or saved.
"""
import hashlib
import argparse
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DAEMON = Path(__file__).resolve().parent
EDITOR = ROOT / 'AIVoice2Editor'
ENGINE_SHA256 = '711aa449c58754bd89402093e077695e8e6175159623c8cf063b979aa3515c17'
LICENSE_SHA256 = 'c7a013e6dabbc143b1fe5352ad38b5f9bd117b7b22abe46911c21b49bfe7004b'


def credentials(license_path):
    # Constants/packing observed in this exact engine at 1800CB023, 1800C6F70,
    # 1800C6AE0. Restrict to inspected artifacts rather than guessing formats.
    data = license_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != LICENSE_SHA256:
        raise ValueError('License differs from the inspected artifact')
    exponent = pow(179, -1, math.lcm(67 - 1, 137 - 1))
    decoded = bytes(pow(int.from_bytes(data[i:i + 2], 'big'), exponent,
                        67 * 137) & 255 for i in range(0, len(data) - 1, 2))
    fields = []
    pos = 0
    for _ in range(2):
        size = int(decoded[pos:pos + 2])
        pos += 2
        field = decoded[pos:pos + size].decode('ascii')
        if len(field) != size or not field or '\x00' in field:
            raise ValueError('Invalid license identity field')
        fields.append(field)
        pos += size
    return fields  # productName, licenseCode


def windows_path(path):
    return 'Z:' + str(path.resolve()).replace('/', '\\')


def main():
    # Lazy import keeps credentials() usable in standalone clean-namespace tools.
    from runtime_config import load_config, install_drive_aliases, load_voice_registry
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dictionaries', action='store_true')
    mode.add_argument('--synthesize', action='store_true')
    parser.add_argument('--voice', default='KotonohaAkane_ns_48')
    parser.add_argument('--probe-exe', type=Path, help='Use a prebuilt auth_probe.exe instead of compiling')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    editor = config.app_dir
    engine = editor / 'aitalk_engine.dll'
    license_path = editor / 'Lib' / 'AITalk' / 'aitalk.lic'
    if hashlib.sha256(engine.read_bytes()).hexdigest() != ENGINE_SHA256:
        raise ValueError('Engine differs from the inspected artifact')
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    install_drive_aliases(config, config.engine_prefix)
    product, code = credentials(license_path)
    build = config.runtime_dir
    build.mkdir(parents=True, exist_ok=True)
    exe = args.probe_exe or build / 'auth_probe.exe'
    if args.probe_exe is None:
        subprocess.run(['x86_64-w64-mingw32-gcc', '-Wall', '-Wextra', '-Werror',
                        '-O2', str(DAEMON / 'auth_probe.c'), '-o', str(exe)], check=True)
    env = os.environ.copy()
    env.update(WINEPREFIX=str(config.engine_prefix), WINEDEBUG='-all',
               AITALK_PRODUCT_NAME=product, AITALK_LICENSE_CODE=code)
    command = ['wine', config.wine_path(exe), config.wine_path(engine), config.wine_path(license_path)]
    if args.dictionaries or args.synthesize:
        registry = load_voice_registry(config.voice_registry)
        if args.voice not in registry:
            raise ValueError('Voice dialect is not registered')
        language = registry[args.voice]['language']
        voice = editor / 'Voice' / args.voice
        command += [config.wine_path(editor / 'Lang' / language / (language + '.aildic')),
                    config.wine_path(voice / (args.voice + '.aivdic')),
                    config.wine_path(voice / 'voice.lic')]
        if args.synthesize:
            command.append(config.wine_path(config.cache_dir / 'probe.wav'))
    result = subprocess.run(command, env=env, cwd=config.cache_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=120)
    output = result.stdout.decode('utf-8', errors='replace')
    print(output, end='')
    evidence = args.output_dir or (ROOT / 'notes/evidence' if config.development_fallback
                                   else config.log_dir / 'probes')
    evidence.mkdir(parents=True, exist_ok=True)
    filename = 'synthesis-probe.txt' if args.synthesize else (
        'dictionary-probe.txt' if args.dictionaries else 'auth-probe.txt')
    (evidence / filename).write_text(
        output + f'\nprocess_exit={result.returncode}\n', encoding='utf-8')
    return result.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'Probe failed: {error}', file=sys.stderr)
        sys.exit(1)
