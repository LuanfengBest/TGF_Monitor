"""Verify an OnDemand-downloaded ZIP and safely extract this one v2 job."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

PHASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("download", type=Path); parser.add_argument("job_id"); parser.add_argument("remote_sha256")
args = parser.parse_args()
assert args.job_id.isdigit()
data = args.download.read_bytes(); actual = hashlib.sha256(data).hexdigest()
assert len(args.remote_sha256) == 64 and actual == args.remote_sha256, "Remote/local checksum differs"
destination = PHASE / ("cluster_results_" + args.job_id)
saved = PHASE / ("evidence_claim_results_" + args.job_id + ".zip")
assert not destination.exists() and not saved.exists(), "Never overwrite collected results"
with zipfile.ZipFile(args.download) as archive:
    assert archive.testzip() is None
    names = archive.namelist(); assert len(names) == len(set(names))
    for item in archive.infolist():
        name = PurePosixPath(item.filename)
        assert not name.is_absolute() and ".." not in name.parts and name.parts
        assert name.parts[0] in {"results", "admission", "submission_once", "project"}
        assert not stat.S_ISLNK(item.external_attr >> 16)
        if name.parts[0] == "project":
            assert name.parts[1] == PHASE.name
    with saved.open("xb") as output:
        output.write(data)
    destination.mkdir(); archive.extractall(destination)
receipt = {"collected_at_utc": datetime.now(timezone.utc).isoformat(), "job_id": args.job_id,
           "source": "Bouchet OnDemand browser download", "sha256": actual, "bytes": len(data),
           "archive_files": len(names), "zip_crc_verified": True, "safe_paths_verified": True,
           "extracted_root": str(destination)}
with (PHASE / "collection_receipt_LOCAL.json").open("x") as output:
    json.dump(receipt, output, indent=2); output.write("\n")
print(json.dumps(receipt, indent=2))
