#!/usr/bin/env python3
"""Generate and verify metadata for the exact Linux CLI artifact bytes."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(path):
    return json.loads(Path(path).read_text())


def artifact_path(directory, version):
    file = Path(directory) / f't3-{version}-linux-x64.tar.gz'
    if not file.is_file():
        raise ValueError(f'Archive absent: {file}')
    return file


def create(path, source, output):
    v = manifest(path)
    file = artifact_path(output, v['version'])
    patched_sha = subprocess.check_output(['git', '-C', source, 'rev-parse', 'HEAD'], text=True).strip()
    data = {
        'version': v['version'],
        'upstreamSha': v['upstreamSha'],
        'patchManifestSha256': digest(path),
        'managedToolsPatchSha256': digest(Path(path).parent / 'patches/managed-device-tools.patch'),
        'patchedSha': patched_sha,
        'archiveSha256': digest(file),
    }
    (Path(output) / 'build-manifest.json').write_text(json.dumps(data, indent=2) + '\n')


def verify(path, output):
    v = manifest(path)
    built = manifest(Path(output) / 'build-manifest.json')
    file = artifact_path(output, v['version'])
    expected = {
        'version': v['version'],
        'upstreamSha': v['upstreamSha'],
        'patchManifestSha256': digest(path),
        'managedToolsPatchSha256': digest(Path(path).parent / 'patches/managed-device-tools.patch'),
        'archiveSha256': digest(file),
    }
    for k, expected_value in expected.items():
        if built.get(k) != expected_value:
            raise ValueError(f'Artifact provenance mismatch for {k}')
    if not re.fullmatch(r'[0-9a-f]{40}', built.get('patchedSha', '')):
        raise ValueError('Invalid patched source commit')
    print('Artifact provenance verified')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--verify'] and len(sys.argv) == 4:
        verify(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4:
        create(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        raise SystemExit('Usage: provenance.py manifest.json SRC OUT | --verify manifest.json OUT')
