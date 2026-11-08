"""One explicit GPU submission after CPU admission; no polling, resubmission or expansion."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from . import protocol as p
from .campaign import validate_receipts
from .prepare import ROOT, load_bundle, read, write, sha


def submit(bundle, authorization):
    cfg, _, _ = load_bundle(bundle)
    preflight = read(ROOT / "admission/preflight.json")
    authority = read(authorization)
    if authority.get("scope") != cfg["scope"] or authority.get("authorized") is not True:
        raise ValueError("New comparison authorization must be recorded")
    permit = {"schema_version": "airline-replay-permit-v1", "scope": cfg["scope"],
              "bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"), "preflight_sha256": p.digest(preflight),
              "authorized_limits": cfg["limits"], "resource_envelope": cfg["resource_envelope"],
              "user_authorization": authority["user_message"], "authorization_record_sha256": sha(authorization),
              "new_environment_episodes": 0, "environment_tool_calls": 0,
              "single_use_claim_path": str(ROOT / "gpu_run_claim.json")}
    validate_receipts(bundle, preflight, permit)
    write(ROOT / "permit.json", permit)
    write(ROOT / "gpu_submission_claim.json", {"created_at_utc": datetime.now(timezone.utc).isoformat(),
          "permit_sha256": p.digest(permit), "max_submissions": 1, "resubmit_allowed": False})
    try:
        result = subprocess.run(["sbatch", "--parsable", "airline_dev_v1/run.sbatch"], cwd=ROOT,
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
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--authorization", type=Path, required=True)
    args = ap.parse_args()
    print(p.canonical(submit(args.bundle, args.authorization)))
