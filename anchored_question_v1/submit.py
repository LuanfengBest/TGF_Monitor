"""Consume the new submission claim before exactly one sbatch invocation."""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from .prepare import ROOT, OUTPUT, load_bundle, read, write, sha
from . import protocol as p

REMOTE_ROOT = Path("/nfs/roberts/project/cpsc4880/cpsc4880_rz377/anchored_question_20261106_v1")


def submit(bundle):
    if ROOT != REMOTE_ROOT or os.environ.get("USER") != "cpsc4880_rz377":
        raise PermissionError("Submit only through the authorized Bouchet account/root")
    cfg, _, _ = load_bundle(bundle)
    authority = read(Path(bundle) / "authorization.json")
    if authority.get("authorized") is not True or authority.get("scope") != cfg["scope"]:
        raise ValueError("Explicit new execution authorization required")
    permit = {"schema_version": "anchored-question-permit-v1", "scope": cfg["scope"],
        "bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"), "authorization_sha256": p.digest(authority),
        "authorized_limits": cfg["limits"], "resource_envelope": cfg["resource_envelope"],
        "new_environment_episodes": 0, "environment_tool_calls": 0,
        "single_use_claim_path": str(ROOT / "gpu_run_claim.json")}
    # The one claim is consumed even on a failed/ambiguous sbatch result.
    write(ROOT / "gpu_submission_claim.json", {"created_at_utc": datetime.now(timezone.utc).isoformat(),
        "permit_sha256": p.digest(permit), "max_submissions": 1, "resubmit_allowed": False})
    write(ROOT / "permit.json", permit)
    try:
        result = subprocess.run(["sbatch", "--parsable", "anchored_question_v1/run.sbatch"], cwd=ROOT,
            capture_output=True, text=True, timeout=30)
        receipt = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
            "resubmit_allowed": False, "created_at_utc": datetime.now(timezone.utc).isoformat()}
        if result.returncode == 0 and result.stdout.strip().split(";")[0].isdigit():
            receipt["job_id"] = result.stdout.strip().split(";")[0]
    except Exception as exc:
        receipt = {"status": "submission_outcome_unknown", "error": str(exc), "resubmit_allowed": False}
    write(ROOT / "gpu_submission.json", receipt)
    return receipt


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", type=Path, default=OUTPUT / "bundle")
    args = ap.parse_args()
    print(p.canonical(submit(args.bundle)))
