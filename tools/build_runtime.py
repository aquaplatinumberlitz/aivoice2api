#!/usr/bin/env python3
"""Build a versioned, self-contained runtime without touching an installation."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output):
    version = (ROOT / 'VERSION').read_text().strip()
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain',
                                     '--untracked-files=all', '--', 'runtime', 'tools', 'VERSION'], text=True)
    if dirty:
        raise ValueError('Commit runtime/build changes before building a release')
    epoch = int(subprocess.check_output(['git', '-C', str(ROOT), 'show', '-s', '--format=%ct', 'HEAD']))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    name = 'aivoice2api-' + version
    destination = output / name
    archive = output / (name + '.tar.gz')
    if destination.exists() or archive.exists():
        raise ValueError('Output already exists; choose a fresh --output directory')
    with tempfile.TemporaryDirectory(prefix='.build-', dir=output) as directory:
        stage = Path(directory) / name
        shutil.copytree(ROOT / 'runtime', stage / 'runtime',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        runtime = stage / 'runtime'
        compiler = 'x86_64-w64-mingw32-gcc'
        subprocess.run([compiler, '-Wall', '-Wextra', '-Werror', '-O2',
                        '-Wl,--no-insert-timestamp', 'engine_worker.c', '-o', 'engine_worker.exe'],
                       cwd=runtime, check=True)
        worker = {'schema_version': 1, 'backend': 'aivoice2api', 'version': version,
                  'source_commit': commit, 'worker_protocol': 'vntext-pcm-metrics-v1',
                  'compiler': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
                  'worker_sha256': sha(runtime / 'engine_worker.exe'),
                  'files': {n: sha(runtime / n) for n in ['engine_worker.c', 'engine_api.h']}}
        (runtime / 'worker-manifest.json').write_text(json.dumps(worker, indent=2) + '\n')
        manifest = {'schema_version': 1, 'backend': 'aivoice2api', 'version': version,
                    'source_commit': commit,
                    'files': {p.relative_to(stage).as_posix(): sha(p)
                              for p in sorted(runtime.iterdir()) if p.is_file()}}
        (stage / 'backend-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        # Fixed tar/gzip metadata makes repeated builds with the same compiler comparable.
        with archive.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as tar:
                for path in sorted(stage.rglob('*')):
                    if not path.is_file():
                        continue
                    data = path.read_bytes()
                    item = tarfile.TarInfo(name + '/' + path.relative_to(stage).as_posix())
                    item.size, item.mtime, item.mode = len(data), epoch, 0o644
                    tar.addfile(item, io.BytesIO(data))
        stage.rename(destination)
    digest = sha(archive)
    (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
    print(json.dumps({'directory': str(destination), 'archive': str(archive),
                      'sha256': digest, 'version': version, 'source_commit': commit}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().output)
