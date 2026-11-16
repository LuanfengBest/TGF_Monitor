"""Atomic single submission; any ambiguous/error result forbids automatic retry."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
if str(root) != "/nfs/roberts/project/cpsc4880/cpsc4880_rz377/closeout_validation_20261107_v1":
    raise SystemExit("Wrong dedicated remote root")
os.chdir(root)
from closeout_validation_v1.run import verify_manifest
verify_manifest()
receipt_dir = root / "submission_once"
receipt_dir.mkdir(exist_ok=False)
(root / "logs").mkdir(exist_ok=True)
test = subprocess.run(["sbatch", "--test-only", "closeout_validation_v1/run.sbatch"], text=True, capture_output=True)
(receipt_dir / "scheduler_admission.json").write_text(json.dumps({"returncode": test.returncode, "stdout": test.stdout, "stderr": test.stderr}, indent=2))
if test.returncode:
    raise SystemExit("Scheduler admission failed; no job submitted")
result = subprocess.run(["sbatch", "--parsable", "closeout_validation_v1/run.sbatch"], text=True, capture_output=True)
receipt = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "automatic_retry_permitted": False}
(receipt_dir / "submission.json").write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt), flush=True)
if result.returncode or not result.stdout.strip().split(";")[0].isdigit():
    raise SystemExit("Submission result uncertain or failed; inspect scheduler, do not resubmit")
