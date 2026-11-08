"""Verify a browser-downloaded result ZIP and safely extract it locally."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

P = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('download', type=Path)
parser.add_argument('remote_sha256')
args = parser.parse_args()
data = args.download.read_bytes()
actual = hashlib.sha256(data).hexdigest()
assert len(args.remote_sha256) == 64 and actual == args.remote_sha256, 'Remote/local ZIP checksum differs'
destination = P / 'cluster_results_32425664'
archive_path = P / 'evidence_use_results_32425664.zip'
assert not destination.exists() and not archive_path.exists(), 'Never overwrite a collected run'
with zipfile.ZipFile(args.download) as archive:
    assert archive.testzip() is None, 'ZIP CRC failed'
    names = archive.namelist()
    assert len(names) == len(set(names)), 'Duplicate archive paths'
    for item in archive.infolist():
        name = PurePosixPath(item.filename)
        assert not name.is_absolute() and '..' not in name.parts and name.parts
        assert name.parts[0] in {'results', 'admission', 'submission_once', 'project'}
        assert not stat.S_ISLNK(item.external_attr >> 16), 'Unexpected symlink'
        if name.parts[0] == 'project':
            assert name.parts[1] == 'evidence_use_diagnostic_2026-11-07'
    with archive_path.open('xb') as stream:
        stream.write(data)
    destination.mkdir()
    archive.extractall(destination)
receipt = {'collected_at_utc': datetime.now(timezone.utc).isoformat(), 'job_id': '32425664',
           'source': 'Bouchet OnDemand browser download', 'sha256': actual, 'bytes': len(data),
           'archive_files': len(names), 'zip_crc_verified': True, 'safe_paths_verified': True,
           'extracted_root': str(destination)}
with (P/'collection_receipt_LOCAL.json').open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps(receipt, indent=2))
