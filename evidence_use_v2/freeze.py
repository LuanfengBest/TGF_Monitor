"""Validate and seal one new input/code bundle; labels stay local."""
from datetime import datetime, timezone
import json
import subprocess
import sys
import zipfile
from .prepare import ROOT, OUT, OLD, read, write
from .run import sha


def freeze():
    assert not (OUT / "manifest.json").exists(), "Never refreeze or overwrite a submitted bundle"
    tests = subprocess.run([sys.executable, "-m", "unittest", "evidence_use_v2.test_probe", "-v"],
                           cwd=ROOT, capture_output=True, text=True)
    (OUT / "local_test_report.txt").write_text(tests.stdout + tests.stderr)
    if tests.returncode:
        raise SystemExit(tests.stdout + tests.stderr)
    for name in ("cluster_python.sh", "run.sbatch"):
        subprocess.run(["bash", "-n", str(ROOT / "evidence_use_v2" / name)], check=True)
    shared = [name for name in read(OLD / "manifest.json")["files"]
              if not name.startswith(("evidence_use_v1/", "project/"))]
    shared += ["evidence_use_v1/" + n for n in ("__init__.py", "prepare.py", "protocol.py")]
    files = sorted(shared + [str(p.relative_to(ROOT)) for p in (ROOT / "evidence_use_v2").iterdir() if p.is_file()]
                   + [str((OUT / name).relative_to(ROOT)) for name in ("config.json", "contract.json", "requests.json")])
    manifest = {"scope": "posthoc-one-task-cumulative-claim-probe", "frozen_utc": datetime.now(timezone.utc).isoformat(),
                "offline_checks": {"meaningful_tests_passed": 5, "shell_syntax": "passed", "new_model_calls": 0},
                "files": {name: sha(ROOT / name) for name in files},
                "local_reference_files": {name: sha(OUT / name) for name in ("targets_LOCAL_ONLY.json", "input_review_LOCAL_ONLY.json")},
                "reference_labels_excluded_from_cluster_payload": True,
                "experimental_assertions_in_prompt": "Both true and false claims are experimental treatments, not evaluator gold labels.",
                "maximum_new_gpu_jobs": 1}
    write(OUT / "manifest.json", manifest)
    archive = OUT / "evidence_claim_20261107_v2.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in files:
            zipped.write(ROOT / name, name)
        zipped.write(OUT / "manifest.json", str((OUT / "manifest.json").relative_to(ROOT)))
    receipt = {"archive": str(archive), "archive_sha256": sha(archive), "archive_bytes": archive.stat().st_size,
               "manifest_sha256": sha(OUT / "manifest.json"), "files_in_archive": len(files) + 1,
               "destination_root": "/nfs/roberts/project/cpsc4880/cpsc4880_rz377/evidence_claim_20261107_v2",
               "submitted": False, "new_model_calls": 0}
    write(OUT / "bundle_receipt_LOCAL.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    freeze()
