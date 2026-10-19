"""Receive one hashed handoff snapshot into a new directory; never merge or run it."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile


def receive(archive, expected_sha, destination):
    archive, destination = Path(archive), Path(destination)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected_sha or destination.exists():
        raise ValueError('Archive hash mismatch or destination already exists')
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len(names) > 100:
            raise ValueError('Duplicate or excessive archive members')
        if sum(i.file_size for i in infos) > 50_000_000:
            raise ValueError('Unpacked size exceeds frozen handoff limit')
        for i in infos:
            p = PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or i.is_dir() or stat.S_ISLNK(i.external_attr >> 16):
                raise ValueError('Unsafe archive member')
        manifest = json.loads(package.read('HANDOFF_MANIFEST.json'))
        hashes = manifest['sha256']
        if set(names) != set(hashes) | {'HANDOFF_MANIFEST.json'}:
            raise ValueError('Archive does not match manifest')
        contents = {n: package.read(n) for n in hashes}
        for n, content in contents.items():
            if hashlib.sha256(content).hexdigest() != hashes[n]:
                raise ValueError('Member hash mismatch: ' + n)
        destination.mkdir(parents=True, exist_ok=False)
        for n, content in contents.items():
            target = destination / n
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(content)
        (destination / 'HANDOFF_MANIFEST.json').write_bytes(package.read('HANDOFF_MANIFEST.json'))
    for n, expected in hashes.items():
        if hashlib.sha256((destination / n).read_bytes()).hexdigest() != expected:
            raise ValueError('Written file verification failed: ' + n)
    receipt = {'status': 'snapshot_hash_verified_not_remote_tests_or_training',
               'archive_sha256': digest, 'files_verified': len(hashes),
               'destination': str(destination), 'model_calls': 0,
               'gpu_jobs': 0, 'training_runs': 0, 'existing_files_overwritten': 0}
    with (destination / 'RECEIPT.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    receive(*sys.argv[1:])
