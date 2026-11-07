"""Behavior checks for install relocation, unsafe config and missing voice data."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from runtime_config import ConfigError, install_drive_aliases, load_config
from runtime_cli import diagnose, render_service
from server import voices


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aivoice2-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Người mới có dấu và khoảng trắng'
        self.root.mkdir()
        self.path = self.root / 'runtime.json'
        self.data = dict(schema_version=1, app_dir='app', runtime_dir='runtime',
                         engine_prefix='prefix/engine', gui_prefix='prefix/gui',
                         cache_dir='cache', log_dir='logs', voice_registry='voices.json')
        self.path.write_text(json.dumps(self.data))
        self.registry = self.root / 'voices.json'
        self.registry.write_text(json.dumps({'schema_version': 1, 'voices': {
            'aoi': {'language': 'standard'}, 'akane': {'language': 'kansai'}}}))

    def load(self, **changes):
        self.path.write_text(json.dumps({**self.data, **changes}))
        return load_config(self.path)

    def voice(self, name):
        folder = self.root / 'app/Voice' / name
        folder.mkdir(parents=True)
        (folder / (name + '.aivdic')).write_bytes(b'fixture')
        (folder / 'voice.lic').write_bytes(b'fixture')
        return folder

    def lang(self, name):
        p = self.root / 'app/Lang' / name / (name + '.aildic')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'fixture')

    def test_relative_paths_and_read_only_loading(self):
        before = sorted(self.root.rglob('*'))
        config = self.load()
        self.assertEqual(config.app_dir, self.root / 'app')
        self.assertEqual(sorted(self.root.rglob('*')), before)
        self.assertEqual(config.wine_path(config.app_dir / 'Voice/aoi/aoi.aivdic'),
                         r'V:\Voice\aoi\aoi.aivdic')
        with self.assertRaises(ConfigError):
            config.wine_path(self.root / 'unconfigured/file')

    def test_explicit_missing_never_falls_back(self):
        with self.assertRaises(ConfigError):
            load_config(self.root / 'missing.json')

    def test_invalid_schema_fields_port_and_prefixes(self):
        for changes in [dict(schema_version=2), dict(port=True), dict(port=80),
                        dict(host='0.0.0.0'), dict(app_dir=''),
                        dict(gui_prefix='prefix/engine'), dict(default_voice='../voice')]:
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                self.load(**changes)

    def test_default_xdg_paths(self):
        self.path.write_text(json.dumps({'schema_version':1, 'app_dir':'app', 'runtime_dir':'runtime'}))
        with patch.dict(os.environ, {'XDG_STATE_HOME':str(self.root/'state'),
                                     'XDG_CACHE_HOME':str(self.root/'xdg-cache')}):
            config = load_config(self.path)
        self.assertEqual(config.cache_dir, self.root/'xdg-cache/aivoice2-local/tts')

    def test_alias_conflict_has_no_partial_writes(self):
        config = self.load()
        prefix = config.engine_prefix
        (prefix / 'dosdevices').mkdir(parents=True)
        (prefix / 'system.reg').write_text('fixture')
        conflict = prefix / 'dosdevices/r:'
        conflict.symlink_to(self.root / 'different')
        with self.assertRaises(ConfigError):
            install_drive_aliases(config, prefix)
        self.assertFalse((prefix / 'dosdevices/v:').exists())
        conflict.unlink()
        install_drive_aliases(config, prefix)
        install_drive_aliases(config, prefix)
        self.assertEqual(os.readlink(prefix / 'dosdevices/v:'), str(config.app_dir))

    def test_registry_dialects_missing_language_and_unknown_voice(self):
        self.voice('aoi'); self.voice('akane'); self.voice('unknown')
        self.lang('standard')
        config = self.load()
        self.assertEqual(list(voices(config)), ['aoi/aoi'])
        self.lang('kansai')
        self.assertEqual(voices(config)['akane/akane']['language'], 'kansai')
        result = diagnose(config)
        self.assertEqual(result['unregistered_voices'], ['unknown'])
        (self.root / 'app/Voice/aoi/voice.lic').unlink()
        self.assertNotIn('aoi/aoi', voices(config))
        self.assertIn('aoi', diagnose(config)['incomplete_voices'])

    def test_service_escaping_and_shared_config(self):
        unit = render_service(self.load())
        self.assertIn(str(self.path), unit)
        self.assertIn('--config', unit)
        self.assertNotIn('WorkingDirectory=', unit)
        from runtime_cli import systemd_quote
        self.assertEqual(systemd_quote('x%y$z"'), '"x%%y$$z\\""')
        with self.assertRaises(ConfigError):
            systemd_quote('path\nline')

    def test_support_snapshot_does_not_read_private_content(self):
        from runtime_cli import support_snapshot
        config=self.load()
        config.log_dir.mkdir()
        (config.log_dir/'gui.log').write_text('PRIVATE_SENTENCE_DO_NOT_EXPORT')
        (self.root/'collection.anki2').write_text('PRIVATE_COLLECTION_DO_NOT_EXPORT')
        result=json.dumps(support_snapshot(config))
        self.assertNotIn('PRIVATE_',result)
        self.assertNotIn(str(self.root),result)
        self.assertIn('[APP]',result)


if __name__ == '__main__':
    unittest.main()
