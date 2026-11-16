"""Verify and extract the completed campaign for CPU-only read-only analysis."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

EXPECTED_SHA256 = 'bcfc9e2a9e382c128c3d8c22c6196b27a898e90d790d66108475143750d17053'
EXPECTED_BYTES = 14129265
EXPECTED_FILES = 1405
DEFAULT_ARCHIVE = Path(__file__).resolve().parents[1] / 'shared_evidence/tgf_prospective_results_31821684.tar.gz'


def unpack(archive, output):
    if sys.version_info < (3, 12):
        raise SystemExit('Use Python3.12+ for filtered archive extraction.')
    archive, output = archive.resolve(), output.resolve()
    if output.exists():
        raise SystemExit('Choose a new output directory; existing evidence is never overwritten.')
    if archive.stat().st_size != EXPECTED_BYTES or hashlib.sha256(archive.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise SystemExit('Archive size/hash does not match the retrieved campaign.')
    with tarfile.open(archive, 'r:gz') as bundle:
        for member in bundle.getmembers():
            parts = Path(member.name).parts
            if (not parts or parts[0] != 'results_31821684' or '..' in parts
                    or Path(member.name).is_absolute() or not (member.isfile() or member.isdir())):
                raise SystemExit('Unexpected archive member; no extraction performed.')
        output.mkdir(parents=True)
        bundle.extractall(output, filter='data')
    root = output / 'results_31821684'
    receipt = json.loads((root / 'result_retrieval_31821684.json').read_text())
    if receipt['job_id'] != '31821684' or len(receipt['files']) != EXPECTED_FILES:
        raise SystemExit('Unexpected retrieval manifest.')
    for entry in receipt['files']:
        path = root / entry['path']
        if root not in path.resolve().parents:
            raise SystemExit('Unexpected manifest path.')
        if path.stat().st_size != entry['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise SystemExit('Extracted file mismatch: ' + entry['path'])
    print(json.dumps({'job_id': '31821684', 'verified_files': EXPECTED_FILES,
                      'archive_sha256': EXPECTED_SHA256,
                      'run': str(root / 'runs/development_20261103'),
                      'model_calls_dispatched_by_this_script': 0}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    unpack(args.archive, args.out)
