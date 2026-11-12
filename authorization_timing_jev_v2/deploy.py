"""One-use Bouchet transfer admission, submission, status, and result export."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

NAME = "authorization_timing_jev_v02_run01_20261112"
BASE = Path("/nfs/roberts/project/cpsc4880/cpsc4880_rz377")
ROOT = BASE / NAME
REL = Path("project/authorization_timing_jev_2026-11-12/run_01")
BUNDLE = ROOT / REL
ASSETS = BASE / "authorization_cpsc4880_20261105_879a8821d635/runtime_assets"
DEPS = BASE / "new_data_20261105_v1/python_dependencies"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    with path.open("x") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def call(argv, timeout=30):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    value = {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode:
        raise RuntimeError(json.dumps(value))
    return value


def frozen(seal):
    assert sha(BUNDLE / "manifest.json") == seal, "Manifest differs"
    for name, expected in read(BUNDLE / "manifest.json")["files"].items():
        assert sha(ROOT / name) == expected, name
    receipt = read(BUNDLE / "results/jev_smoke_passed.json")
    assert receipt["manifest_sha256"] == seal and len(receipt["result_hashes"]) == 4
    for rid, expected in receipt["result_hashes"].items():
        assert sha(BUNDLE / "results" / rid / "result.json") == expected
    assert not (BUNDLE / "results/STOP.json").exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("prepare", "submit", "status", "export"))
    ap.add_argument("--seal")
    ap.add_argument("--archive-sha256")
    args = ap.parse_args()
    assert os.environ.get("USER") == "cpsc4880_rz377"
    if args.action == "prepare":
        archive = Path.home() / (NAME + ".zip")
        assert args.archive_sha256 and sha(archive) == args.archive_sha256
        ROOT.mkdir(exist_ok=False)
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                path = Path(entry.filename)
                assert not path.is_absolute() and ".." not in path.parts and path.parts[0] == NAME
                target = ROOT.joinpath(*path.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as f:
                    f.write(z.read(entry))
        frozen(args.seal)
        queue = call(["squeue", "-h", "-u", os.environ["USER"]])
        assert not queue["stdout"].strip(), "Existing job needs review"
        associations = call(["sacctmgr", "-nP", "show", "assoc", "where", "user="+os.environ["USER"], "format=User,Account,Partition,QOS"])
        assert "cpsc4880_rz377|cpsc4880|" in associations["stdout"] and "normal" in associations["stdout"]
        image = ASSETS / "vllm_0.13.0.sif"
        assert image.is_file() and DEPS.is_dir()
        cfg, inventory = read(BUNDLE / "config.json"), read(BUNDLE / "qwen_assets.json")
        snapshot = Path(cfg["qwen"]["snapshot"])
        for name, expected in inventory["files"].items():
            assert (snapshot/name).stat().st_size == expected["bytes"], name
        code = ("import json; from pathlib import Path; from prospective_monitoring import native_backend as n; "
                "p=Path('project/authorization_timing_jev_2026-11-12/run_01'); c=json.loads((p/'config.json').read_text()); "
                "print(json.dumps({'runtime':n.runtime_check(c['qwen']),'snapshot':str(n.snapshot_check(c['qwen']['snapshot'],'monitor'))}))")
        runtime = call(["apptainer", "exec", "--cleanenv", "--bind", f"{ROOT}:{ROOT}", "--bind", f"{ASSETS}:{ASSETS}:ro", "--bind", f"{DEPS}:{DEPS}:ro",
                        "--pwd", str(ROOT), "--env", f"PYTHONPATH={ROOT}:{DEPS}", "--env", "HF_HUB_OFFLINE=1", "--env", "TRANSFORMERS_OFFLINE=1", str(image), "/usr/bin/python3", "-c", code], 120)
        (ROOT / "logs").mkdir()
        admission = call(["sbatch", "--test-only", "--chdir="+str(ROOT), str(ROOT / "authorization_timing_jev_v2/run.sbatch")])
        receipt = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "manifest_sha256": args.seal,
                   "archive_sha256": args.archive_sha256, "queue": queue, "associations": associations, "runtime": runtime,
                   "asset_sizes_match": True, "scheduler_admission": admission, "new_allocations": 0}
        save(ROOT / "cluster_admission.json", receipt)
        print(json.dumps(receipt), flush=True)
    elif args.action == "submit":
        seal = read(ROOT / "cluster_admission.json")["manifest_sha256"]
        frozen(seal)
        assert not call(["squeue", "-h", "-u", os.environ["USER"]])["stdout"].strip()
        save(ROOT / "submission_claim.json", {"manifest_sha256": seal, "at_utc": datetime.now(timezone.utc).isoformat()})
        result = call(["sbatch", "--parsable", "--chdir="+str(ROOT), str(ROOT / "authorization_timing_jev_v2/run.sbatch")])
        job = result["stdout"].strip().split(";")[0]
        assert job.isdigit(), "Unclear submission outcome; no retry"
        receipt = {"job_id": job, "submission": result, "manifest_sha256": seal, "gpu_count": 1, "wall_limit_minutes": 30}
        save(ROOT / "submission_receipt.json", receipt)
        print(json.dumps(receipt), flush=True)
    else:
        job = read(ROOT / "submission_receipt.json")["job_id"]
        queue = call(["squeue", "-h", "-j", job, "-o", "%.18i %.12P %.20j %.8T %.10M %R"])
        account = call(["sacct", "-j", job, "--parsable2", "--noheader", "--format=JobID,State,ExitCode,Elapsed,AllocTRES"])
        status = {"queue": queue, "accounting": account,
                  "qwen_results": len(list((BUNDLE / "results").glob("qwen.*/result.json"))),
                  "qwen_ready": (BUNDLE / "results/qwen_ready.json").exists(),
                  "qwen_finished": (BUNDLE / "results/qwen_all_finished.json").exists(),
                  "stop": read(BUNDLE / "results/STOP.json") if (BUNDLE / "results/STOP.json").exists() else None}
        print(json.dumps(status), flush=True)
        if args.action == "status":
            logs = sorted((ROOT / "logs").glob("*.log"))
            if logs:
                print(logs[-1].read_text(errors="replace")[-3000:])
        else:
            assert not queue["stdout"].strip(), "Allocation is still live"
            save(ROOT / "accounting_final.json", status)
            output = Path.home() / (NAME + "_results.zip")
            files = list((BUNDLE / "results").rglob("*.json")) + list((ROOT / "logs").glob("*.log"))
            files += [ROOT / n for n in ("submission_claim.json", "submission_receipt.json", "cluster_admission.json", "accounting_final.json")]
            hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
            save(ROOT / "result_hashes.json", hashes)
            with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as z:
                for p in files+[ROOT / "result_hashes.json"]:
                    z.write(p, str(p.relative_to(ROOT)))
            print(json.dumps({"export_file": str(output), "sha256": sha(output), "files": len(files)+1}), flush=True)


if __name__ == "__main__":
    main()
