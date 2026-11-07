"""Shared, versioned paths for the GUI and headless runtime.

Relative paths are relative to the config file, never to the current directory.
Import/load performs no writes and does not create a Wine prefix.
"""
from dataclasses import dataclass
import json
import hashlib
import fcntl
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_VOICE = 'KotonohaAkane_ns_48/KotonohaAkane_ns_48'


class ConfigError(ValueError):
    pass


def xdg(name, fallback):
    return Path(os.environ.get(name) or Path.home() / fallback).expanduser()


@dataclass(frozen=True)
class RuntimeConfig:
    app_dir: Path
    runtime_dir: Path
    engine_prefix: Path
    gui_prefix: Path
    cache_dir: Path
    log_dir: Path
    voice_registry: Path
    port: int = 17862
    default_voice: str = DEFAULT_VOICE
    config_file: Path | None = None
    development_fallback: bool = False

    @property
    def api_url(self):
        return f'http://127.0.0.1:{self.port}'

    @property
    def instance_id(self):
        return hashlib.sha256(str(self.app_dir.resolve()).encode()).hexdigest()[:12]

    @property
    def worker(self):
        return self.runtime_dir / 'engine_worker.exe'

    def as_dict(self):
        return {'schema_version': 1, **{name: str(getattr(self, name)) for name in (
            'app_dir', 'runtime_dir', 'engine_prefix', 'gui_prefix', 'cache_dir',
            'log_dir', 'voice_registry')}, 'port': self.port,
            'default_voice': self.default_voice, 'api_url': self.api_url,
            'development_fallback': self.development_fallback}

    def wine_path(self, path):
        """Use ASCII drive aliases even when the Linux install path has accents."""
        resolved = Path(path).resolve()
        for drive, base in self.drives().items():
            try:
                relative = resolved.relative_to(base.resolve())
            except ValueError:
                continue
            return drive.upper() + ':\\' + str(relative).replace('/', '\\')
        raise ConfigError(f'Path is outside configured app/runtime/cache directories: {path}')

    def drives(self):
        return {'v': self.app_dir, 'r': self.runtime_dir, 'o': self.cache_dir}


def load_config(path=None):
    explicit = path or os.environ.get('AIVOICE2_CONFIG')
    config_file = Path(explicit).expanduser() if explicit else (
        xdg('XDG_CONFIG_HOME', '.config') / 'aivoice2-local/runtime.json')
    if not config_file.is_file():
        # Backward compatibility for the existing research service. Release
        # launchers always supply an explicit config; never depend on this.
        if not explicit and (ROOT / 'AIVoice2Editor').is_dir():
            return RuntimeConfig(ROOT / 'AIVoice2Editor', HERE / 'build',
                                 ROOT / 'wineprefix', ROOT / 'cache/free-client-review/prefix',
                                 ROOT / 'cache/tts', ROOT / 'cache',
                                 HERE / 'voice_registry.json', development_fallback=True)
        raise ConfigError(f'Không tìm thấy cấu hình runtime: {config_file}. Chạy trình thiết lập trước.')
    config_file = config_file.resolve()
    try:
        data = json.loads(config_file.read_text())
    except (ValueError, OSError) as error:
        raise ConfigError(f'Không đọc được cấu hình runtime: {error}') from error
    fields = {'schema_version', 'app_dir', 'runtime_dir', 'engine_prefix', 'gui_prefix',
              'cache_dir', 'log_dir', 'voice_registry', 'port', 'default_voice'}
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        raise ConfigError('Cấu hình cần schema_version = 1')
    if set(data) - fields:
        raise ConfigError(f'Trường cấu hình không hỗ trợ: {sorted(set(data) - fields)}')

    def location(name, default=None):
        value = data.get(name, default)
        if not isinstance(value, str) or not value.strip() or '\x00' in value:
            raise ConfigError(f'Cấu hình thiếu hoặc sai đường dẫn {name}')
        result = Path(value).expanduser()
        return (result if result.is_absolute() else config_file.parent / result).resolve()

    state = xdg('XDG_STATE_HOME', '.local/state') / 'aivoice2-local'
    port = data.get('port', 17862)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ConfigError('port phải là số nguyên từ 1024 đến 65535; chỉ dùng loopback')
    default_voice = data.get('default_voice', DEFAULT_VOICE)
    if not isinstance(default_voice, str) or len(default_voice.split('/')) != 2 or any(
            part in ('', '.', '..') or '\\' in part or '\x00' in part
            for part in default_voice.split('/')):
        raise ConfigError('default_voice phải có dạng thư-mục/tên-giọng')
    config = RuntimeConfig(
        app_dir=location('app_dir'), runtime_dir=location('runtime_dir'),
        engine_prefix=location('engine_prefix', str(state / 'prefixes/engine')),
        gui_prefix=location('gui_prefix', str(state / 'prefixes/gui')),
        cache_dir=location('cache_dir', str(xdg('XDG_CACHE_HOME', '.cache') / 'aivoice2-local/tts')),
        log_dir=location('log_dir', str(state / 'logs')),
        voice_registry=location('voice_registry', str(HERE / 'voice_registry.json')),
        port=port, default_voice=default_voice, config_file=config_file)
    if config.engine_prefix == config.gui_prefix:
        raise ConfigError('GUI và engine cần prefix riêng để giữ settings độc lập')
    return config


def load_voice_registry(path):
    try:
        data = json.loads(Path(path).read_text())
        if data['schema_version'] != 1 or not isinstance(data['voices'], dict):
            raise ValueError('schema')
        for name, entry in data['voices'].items():
            if not isinstance(entry, dict) or entry.get('language') not in ('standard', 'kansai'):
                raise ValueError(f'Invalid dialect for {name}')
        return data['voices']
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ConfigError(f'Không đọc được registry giọng {path}: {error}') from error


def install_drive_aliases(config, prefix):
    """Only add our aliases to an already initialized, explicitly owned prefix."""
    prefix = Path(prefix)
    if not (prefix / 'system.reg').is_file() or not (prefix / 'dosdevices').is_dir():
        raise ConfigError(f'Wine prefix chưa được thiết lập: {prefix}. Không clone prefix cá nhân.')
    # Check all aliases first so a conflict cannot leave a half-updated prefix.
    for drive, target in config.drives().items():
        link = prefix / 'dosdevices' / (drive + ':')
        if os.path.lexists(link) and (not link.is_symlink() or link.resolve() != target.resolve()):
            raise ConfigError(f'Wine drive {drive.upper()}: đã trỏ nơi khác trong {prefix}')
    for drive, target in config.drives().items():
        link = prefix / 'dosdevices' / (drive + ':')
        if not os.path.lexists(link):
            link.symlink_to(target.resolve(), target_is_directory=True)


def acquire_runtime_lease(config):
    """Managed installs coordinate GUI/engine readers with voice maintenance."""
    if config.config_file is None:
        return None
    managed=config.config_file.parent.parent
    if not (managed/'install-manifest.json').is_file():
        return None
    lease=(managed/'.runtime.lock').open('a+b')
    try:
        fcntl.flock(lease,fcntl.LOCK_SH|fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close()
        raise ConfigError('Bản cài đang được cập nhật giọng. Đợi hoàn tất rồi mở lại.')
    return lease
