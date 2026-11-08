"""Seal new inputs; retain all previous frozen experiments unchanged."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from .prepare import ROOT, OUT, OLD, read, write, sha


def freeze():
    assert not (OUT / "manifest.json").exists(), "Never overwrite a frozen package"
    old = read(OLD / "manifest.json")
    for path, digest in old["files"].items():
        assert sha(ROOT / path) == digest, "Prior frozen source changed: " + path
    reviews = read(OUT / "reference_reviews_LOCAL_ONLY.json")
    assert len(reviews) == 12 and all(r["author_review"] == "completed" for r in reviews)
    assert all(r["independent_human_review"] == "pending" for r in reviews)
    test = subprocess.run([sys.executable, "-m", "unittest", "closeout_validation_v1.test_validation", "-v"],
                          cwd=ROOT, capture_output=True, text=True)
    (OUT / "local_test_report.txt").write_text(test.stdout + test.stderr)
    if test.returncode:
        raise SystemExit(test.stdout + test.stderr)
    for name in ("run.sbatch", "cluster_python.sh"):
        subprocess.run(["bash", "-n", str(ROOT / "closeout_validation_v1" / name)], check=True)
    shared = [path for path in old["files"] if not path.startswith(("project/", "evidence_use_v1/", "evidence_use_v2/"))]
    runtime = ["run.py", "__init__.py", "cluster_python.sh", "cluster_bootstrap.py", "run.sbatch", "submit.py", "export.py"]
    files = sorted(shared + ["closeout_validation_v1/" + name for name in runtime] +
                   [str((OUT / name).relative_to(ROOT)) for name in ("config.json", "contract.json", "requests.json")])
    local_files = ["targets_LOCAL_ONLY.json", "reference_reviews_LOCAL_ONLY.json", "specifications_LOCAL_ONLY.json",
                   "public_records.json", "HUMAN_REVIEW.html", "human_review_template.json", "human_review_key_LOCAL_ONLY.json"]
    manifest = {"scope": "new-scripted-cumulative-task-blocks", "frozen_utc": datetime.now(timezone.utc).isoformat(),
                "files": {path: sha(ROOT / path) for path in files},
                "local_reference_files": {name: sha(OUT / name) for name in local_files},
                "preparation_code": {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "closeout_validation_v1").glob("*.py"))},
                "simulator_provenance": {str(p.relative_to(OUT)): sha(p) for p in sorted((OUT / "simulator_records").rglob("*.json"))},
                "maximum_new_gpu_jobs": 1, "reference_labels_excluded_from_cluster_payload": True,
                "checks": {"tests": 8, "shell_syntax": "passed", "new_model_calls": 0},
                "independent_human_review": "pending", "formal_claim_permitted": False}
    write(OUT / "manifest.json", manifest)
    archive = OUT / "closeout_validation_20261107_v1.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as out:
        for path in files:
            out.write(ROOT / path, path)
        out.write(OUT / "manifest.json", str((OUT / "manifest.json").relative_to(ROOT)))
    receipt = {"archive": str(archive), "sha256": sha(archive), "bytes": archive.stat().st_size,
               "manifest_sha256": sha(OUT / "manifest.json"), "files": len(files) + 1,
               "destination_root": "/nfs/roberts/project/cpsc4880/cpsc4880_rz377/closeout_validation_20261107_v1",
               "submitted": False, "model_calls": 0, "prior_frozen_inputs_unchanged": True}
    write(OUT / "bundle_receipt_LOCAL.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    freeze()
