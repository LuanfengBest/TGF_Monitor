"""Export only this diagnostic's receipts/results, including on failure."""
import os
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
job = os.environ.get("SLURM_JOB_ID", "unallocated")
path = root / ("closeout_validation_results_" + job + ".zip")
with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as out:
    for directory in ("results", "admission", "submission_once"):
        for file in sorted((root / directory).rglob("*")):
            if file.is_file():
                out.write(file, str(file.relative_to(root)))
    for name in ("manifest.json", "config.json", "contract.json"):
        file = root / "project/closeout_2026-11-07/validation" / name
        out.write(file, str(file.relative_to(root)))
print("EXPORTED", path, path.stat().st_size, flush=True)
