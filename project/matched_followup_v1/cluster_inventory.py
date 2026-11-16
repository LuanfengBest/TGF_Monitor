"""Read-only cluster inventory; no models, downloads or Slurm submissions."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def command(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return {"exit_code": p.returncode, "stdout": p.stdout[:16000], "stderr": p.stderr[:4000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def inventory(roots):
    identity = command(["id", "-un"])
    user = identity.get("stdout", "").strip()
    checks = {"identity": identity, "hostname": command(["hostname"]),
              "jobs": command(["squeue", "--me", "--format=%i|%j|%T|%P|%R"]),
              "h200_partition": command(["sinfo", "-p", "gpu_h200", "-o", "%P|%a|%l|%D|%G"]),
              "storage": command(["mydirectories"])}
    if user:
        checks["associations"] = command(["sacctmgr", "-n", "-P", "show", "assoc", "where",
                                          "user=" + user, "format=Cluster,Account,Partition,QOS,DefaultQOS"])
    versions = {}
    for package in ("vllm", "torch", "transformers", "openai-harmony", "PyYAML"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    paths, visited, deadline = [], 0, time.monotonic() + 20
    skip = {".git", "__pycache__", "node_modules", "blobs", "site-packages"}
    complete = True
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            paths.append({"root": str(root), "exists": False})
            continue
        for current, dirs, files in os.walk(root, followlinks=False):
            visited += 1
            if visited > 20000 or time.monotonic() > deadline:
                complete = False
                break
            depth = len(Path(current).relative_to(root).parts)
            dirs[:] = [d for d in dirs if d not in skip] if depth < 9 else []
            for name in files:
                if name.endswith(".sif") or name in {"model.safetensors.index.json", "verified_models_30028199.json"}:
                    paths.append({"candidate_asset": str(Path(current) / name)})
            if Path(current).name == "bin" and "python" in files:
                paths.append({"candidate_python": str(Path(current) / "python")})
        if not complete:
            break
    return {"purpose": "read-only inventory, not a passed preflight", "checks": checks,
            "python": {"executable": sys.executable, "version": sys.version, "packages": versions},
            "executables": {p: shutil.which(p) for p in ("apptainer", "singularity", "python3", "sbatch")},
            "asset_roots": [str(p) for p in roots], "candidates": paths,
            "scan_complete": complete, "directories_visited": visited,
            "gpu_jobs_submitted": 0, "model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", action="append", type=Path)
    args = parser.parse_args()
    roots = args.asset_root or [Path("/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf"),
                               Path("/nfs/roberts/scratch/hpcllm/hpcllm_rz377")]
    print(json.dumps(inventory(roots), ensure_ascii=False, indent=2))
