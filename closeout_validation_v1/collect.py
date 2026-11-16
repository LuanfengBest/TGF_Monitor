"""Collect only an OnDemand-downloaded result ZIP after a remote UI checksum."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import stat
import zipfile
from .prepare import OUT, write


def collect(download, job, remote_sha):
    assert job.isdigit() and len(remote_sha) == 64
    data = download.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    assert actual == remote_sha, "Remote UI/local checksum mismatch"
    target = OUT / ("cluster_results_" + job)
    saved = OUT / ("closeout_validation_results_" + job + ".zip")
    assert not target.exists() and not saved.exists(), "Reuse existing collected results; never overwrite"
    with zipfile.ZipFile(download) as archive:
        assert archive.testzip() is None
        entries = archive.infolist()
        assert len({e.filename for e in entries}) == len(entries)
        assert sum(e.file_size for e in entries) < 250_000_000
        for entry in entries:
            path = PurePosixPath(entry.filename)
            assert path.parts and not path.is_absolute() and ".." not in path.parts
            assert "\\" not in entry.filename and not stat.S_ISLNK(entry.external_attr >> 16)
            assert path.parts[0] in {"results", "admission", "submission_once", "project"}
            if path.parts[0] == "project":
                assert path.parts[:3] == ("project", "closeout_2026-11-07", "validation")
        with saved.open("xb") as stream:
            stream.write(data)
        target.mkdir()
        archive.extractall(target)
    receipt = {"time_utc": datetime.now(timezone.utc).isoformat(), "job_id": job,
               "source": "CUA Chrome / Bouchet OnDemand file download", "remote_ui_sha256": remote_sha,
               "local_sha256": actual, "bytes": len(data), "files": len(entries), "extracted_root": str(target)}
    write(OUT / ("collection_receipt_" + job + ".json"), receipt)
    return receipt


if __name__ == "__main__":
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("download", type=Path); parser.add_argument("job_id"); parser.add_argument("remote_sha256")
    args = parser.parse_args()
    print(json.dumps(collect(args.download, args.job_id, args.remote_sha256), indent=2))
