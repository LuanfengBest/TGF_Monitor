"""Validate an observed remote export completely before importing any result."""
import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

BUNDLE = Path(__file__).resolve().parents[1]
PREFIX = 'project/jev_tgf_mainline_2026-11-12/results/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--observed-sha256', required=True)
    parser.add_argument('--observed-uncompressed-bytes', required=True, type=int)
    args = parser.parse_args()
    assert digest(args.archive.read_bytes()) == args.observed_sha256, 'ZIP hash mismatch'
    with zipfile.ZipFile(args.archive) as z:
        names = z.namelist()
        assert len(names) == len(set(names)), 'Repeated ZIP entries'
        expanded_bytes = sum(i.file_size for i in z.infolist())
        assert expanded_bytes == args.observed_uncompressed_bytes, 'Expanded size differs from cluster receipt'
        assert 0 < expanded_bytes <= 2*1024**3, 'Unexpected export size'
        manifest = json.loads(z.read('RESULT_FILES.json'))
        assert set(names) == set(manifest) | {'RESULT_FILES.json'}, 'Unmanifested/missing entries'
        targets = []
        for name, expected in manifest.items():
            p = PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts
            assert name.startswith(PREFIX) or p.parts[0] in ('logs', 'submissions')
            data = z.read(name)
            assert digest(data) == expected, 'Entry hash mismatch: '+name
            if name.startswith(PREFIX):
                destination = BUNDLE/'results'/name[len(PREFIX):]
            else:
                destination = BUNDLE/'deployment'/'cluster_outputs'/name
            assert BUNDLE in destination.resolve().parents
            assert not destination.is_symlink()
            if destination.exists():
                assert digest(destination.read_bytes()) == expected, 'Conflicting local result: '+name
            targets.append((destination, name))
        added = reused = 0
        for destination, name in targets:
            if destination.exists():
                reused += 1
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as f:
                f.write(z.read(name))
                f.flush()
                os.fsync(f.fileno())
            added += 1
    receipt = {'archive': str(args.archive.resolve()), 'archive_sha256': args.observed_sha256,
        'entries_verified': len(manifest), 'uncompressed_bytes': expanded_bytes,
        'new_files': added, 'identical_files_reused': reused,
        'unequal_files_overwritten': 0, 'result_file_hashes': manifest}
    destination = BUNDLE/'deployment'/'IMPORT_RECEIPT.json'
    with destination.open('x') as f:
        json.dump(receipt, f, sort_keys=True, indent=2)
        f.write('\n')
    print({k: v for k, v in receipt.items() if k != 'result_file_hashes'})


if __name__ == '__main__':
    main()
