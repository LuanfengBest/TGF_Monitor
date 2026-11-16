"""Run the four saved-result verifiers; never dispatch an experiment launcher."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = (
    "project/closeout_2026-11-07/verify_all_results.py",
    "project/research_update_2026-11-12/verify_saved_results.py",
    "project/authorization_timing_jev_2026-11-12/verify_completed_recovery.py",
    "project/final_report_2026-11-13/verify_integration.py",
)


def main():
    for relative in CHECKS:
        print(f"Checking saved evidence: {relative}", flush=True)
        result = subprocess.run([sys.executable, "-B", str(ROOT / relative)], cwd=ROOT)
        if result.returncode:
            print(f"Verification failed: {relative}", file=sys.stderr)
            return result.returncode if result.returncode > 0 else 1
    print("All four offline verifiers passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
