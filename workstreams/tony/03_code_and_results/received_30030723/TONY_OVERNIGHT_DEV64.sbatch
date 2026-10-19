#!/bin/bash
#SBATCH --job-name=tony_tgf_overnight
#SBATCH --account=cpsc4710
#SBATCH --partition=gpu_h200
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=160G
#SBATCH --gpus=h200:1
#SBATCH --time=04:00:00
#SBATCH --output=tony_overnight_%j.log

# Fixed sequence: two-record gate, then 64 existing development records once.
# Unchanged v4. No retry, training, new data generation, or final-test claim.
set -euo pipefail
: "${SLURM_JOB_ID:?Run as a Slurm job}"
: "${CUDA_VISIBLE_DEVICES:?Slurm GPU visibility is missing}"
cd "${SLURM_SUBMIT_DIR:?Submit from the extracted package root}"
image=containers/vllm_0.13.0_1ae45c63e057.sif
[[ -f "$image" && -f run_replay.py && -f models/verified_models_30028199.json ]] || { echo "Missing image/launcher/verified model receipt"; exit 2; }
[[ ! -L runtime_cache ]] || { echo "Refusing symlink cache directory"; exit 2; }
[[ ! -L .tony_overnight.lock ]] || { echo "Refusing symlink lock"; exit 2; }
exec 9>> .tony_overnight.lock
flock -n 9 || { echo "Another overnight run holds this lock; stopping"; exit 2; }
mkdir -p "runtime_cache/replay_$SLURM_JOB_ID/harmony" "runtime_cache/replay_$SLURM_JOB_ID/triton" "runtime_cache/replay_$SLURM_JOB_ID/vllm"
cache="$PWD/runtime_cache/replay_$SLURM_JOB_ID"
hostname
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
apptainer exec --nv --cleanenv --bind "$PWD:$PWD" --pwd "$PWD" \
    --env "SLURM_JOB_ID=$SLURM_JOB_ID" --env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES" \
    --env "HF_HOME=$PWD/models/.hf_home" --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    --env "TIKTOKEN_RS_CACHE_DIR=$cache/harmony" \
    --env "TRITON_CACHE_DIR=$cache/triton" --env "VLLM_CACHE_ROOT=$cache/vllm" \
    --env OMP_NUM_THREADS=8 --env TOKENIZERS_PARALLELISM=false --env PYTHONUNBUFFERED=1 \
    "$image" /usr/bin/python3 -B -X utf8 -u - <<'PY'
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone


EXPECTED = {
    "monitor": ("Qwen/Qwen3-32B", "9216db5781bf21249d130ec9da846c4624c16137", 17, 65524328560),
    "actor_followup": ("openai/gpt-oss-120b", "b5c939de8f754692c1647ca79fbf85e8c1e70f8a", 15, 65248893184),
}


def checked_models(root: Path) -> dict[str, str]:
    receipt = json.loads((root / "models/verified_models_30028199.json").read_text(encoding="utf-8"))
    if receipt.get("status") != "VERIFIED_WEIGHTS_NOT_MODEL_INFERENCE":
        raise ValueError("Model download receipt was not successful")
    rows = receipt["models"]
    if len(rows) != 2 or {r["role"] for r in rows} != set(EXPECTED):
        raise ValueError("Expected exactly the two verified model roles")
    result = {}
    for row in rows:
        repo, revision, count, weight_bytes = EXPECTED[row["role"]]
        if (row["repo"], row["revision"]) != (repo, revision):
            raise ValueError("Model revision differs from this launch plan")
        folder = root / "models" / (repo.replace("/", "--") + "--" + revision[:12])
        if folder.is_symlink() or Path(row["path"]).resolve() != folder.resolve():
            raise ValueError("Unexpected model directory")
        weights = [r for r in row["files"] if r["file"].endswith(".safetensors")]
        if len(weights) != count or sum(r["bytes"] for r in weights) != weight_bytes:
            raise ValueError("Verified weight count/bytes do not match")
        for entry in row["files"]:
            name = entry["file"]
            if not name or "/" in name or "\\" in name or name in {".", ".."}:
                raise ValueError("Unsafe filename in verification receipt")
            path = folder / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["bytes"]:
                raise ValueError(f"Missing or resized verified model file: {name}")
        # Reuse the completed full checksum verification; do not hash 122 GiB on a GPU slot.
        result[row["role"]] = str(folder.resolve())
    return result


def prepare_harmony() -> None:
    # One small public tokenizer asset, not model weights. TLS verification stays on.
    url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
    expected = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
    asset = Path(os.environ["TIKTOKEN_RS_CACHE_DIR"]) / hashlib.sha1(url.encode()).hexdigest()
    if asset.is_symlink():
        raise ValueError("Refusing symlink tokenizer asset")
    if not asset.exists():
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(16 * 1024**2 + 1)
        if len(data) > 16 * 1024**2 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Public tokenizer asset failed size/checksum check")
        with asset.open("xb") as handle:
            handle.write(data)
    elif hashlib.sha256(asset.read_bytes()).hexdigest() != expected:
        raise ValueError("Cached tokenizer asset checksum mismatch; retained without overwrite")
    from openai_harmony import HarmonyEncodingName, load_harmony_encoding
    encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    if not encoding.stop_tokens_for_assistant_actions():
        raise ValueError("Harmony encoding did not provide expected stop tokens")
    print("HARMONY_READY: public encoding asset checked before loading models", flush=True)


def inspect_run(run: Path, limit: int) -> dict:
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "COMPLETED_DEV_REPLAY" or manifest.get("completed_stages") != ["pass1", "answers", "judge", "metrics"]:
        raise ValueError("Replay did not finish all four real stages")
    ids = manifest["record_ids"]
    if len(ids) != limit or len(set(ids)) != limit:
        raise ValueError("Unexpected selected record IDs/count")
    flags = {"score_parse_failures": 0, "plan_parse_failures": 0, "bad_b3_samples": 0,
             "skipped_answers": 0, "empty_answers": 0, "attempted_tool_calls": 0}
    def rows(name: str) -> list[dict]:
        return [json.loads(line) for line in (run / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    def score_ok(value) -> bool:
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100
    plans = []
    for name in ("b1.jsonl", "b3.jsonl", "tgf_plan.jsonl", "b2.jsonl", "tgf.jsonl"):
        data = rows(name)
        if len(data) != limit or {r["id"] for r in data} != set(ids):
            raise ValueError(f"Missing/duplicate/mismatched rows in {name}")
        flags["score_parse_failures"] += sum(not score_ok(r.get("score")) for r in data)
        if name == "tgf_plan.jsonl":
            plans = data
            flags["plan_parse_failures"] = sum(r.get("parse_ok") is not True for r in data)
        if name == "b3.jsonl":
            flags["bad_b3_samples"] = sum(len(r.get("samples", [])) != 3 or not all(score_ok(v) for v in r.get("samples", [])) for r in data)
    answers = rows("answers.jsonl")
    expected = {(i, "b2", 0) for i in ids}
    expected.update((p["id"], "tgf", j) for p in plans for j, _ in enumerate(p["questions"]))
    keys = [(r["id"], r["method"], r["q_idx"]) for r in answers]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError("Follow-up answers missing, duplicated, or mismatched")
    for answer in answers:
        flags["skipped_answers"] += bool(answer.get("skipped"))
        flags["empty_answers"] += not str(answer.get("answer", "")).strip()
        flags["attempted_tool_calls"] += bool(answer.get("tried_tool_call"))
    if not (run / "metrics.md").is_file():
        raise ValueError("Metrics report is missing")
    return {"run": str(run), "records": limit, "quality_flags": flags,
            "warning": "Previously tuned development data and unchanged unmatched legacy comparison; not a final test."}


def main() -> None:
    root = Path.cwd().resolve()
    job_id = os.environ["SLURM_JOB_ID"]
    runs = root / "runs"
    runs.mkdir(exist_ok=True)
    summary_path = runs / f"overnight_{job_id}.json"
    if summary_path.exists():
        raise ValueError("This job already has a summary; refusing to overwrite/retry")
    summary = {"job_id": job_id, "status": "STARTED", "data_role": "development_only_not_fresh_test",
               "limits": [2, 64], "seed": 42, "max_gpu_hours": 4,
               "started_utc": datetime.now(timezone.utc).isoformat(), "runs": []}
    def save() -> None:
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    save()
    try:
        models = checked_models(root)
        prepare_harmony()
        for limit in (2, 64):
            print(f"OVERNIGHT_BATCH: {limit} development records; fixed seed42; unchanged v4", flush=True)
            before = set(runs.glob("REAL_DEV_REPLAY_*"))
            subprocess.run([sys.executable, "-B", "-X", "utf8", str(root / "run_replay.py"),
                            "--limit", str(limit), "--seed", "42", "--monitor-dir", models["monitor"],
                            "--actor-dir", models["actor_followup"]], cwd=root, check=True)
            # Identify our run by both new directory and Slurm job ID, not recency.
            created = []
            for path in set(runs.glob("REAL_DEV_REPLAY_*")) - before:
                metadata = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
                if metadata.get("slurm_job_id") == job_id:
                    created.append(path)
            if len(created) != 1:
                raise ValueError("Cannot unambiguously identify this batch output")
            result = inspect_run(created[0], limit)
            summary["runs"].append(result)
            save()
            if limit == 2 and any(result["quality_flags"].values()):
                raise ValueError("Two-record quality gate failed; full batch was NOT started")
            if limit == 2:
                print("TWO_RECORD_GATE_PASSED: starting the single 64-record batch", flush=True)
        summary["status"] = "COMPLETED_WITH_QUALITY_FLAGS" if any(summary["runs"][-1]["quality_flags"].values()) else "COMPLETED_DEV_REPLAY"
        summary["completed_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        print(f"OVERNIGHT_DEV64_FINISHED: {summary_path}; inspect quality flags before interpretation", flush=True)
    except BaseException as exc:
        summary["status"] = "FAILED_OR_INTERRUPTED"
        summary["error_type"] = type(exc).__name__
        summary["error"] = str(exc)
        save()
        raise


if __name__ == "__main__":
    main()
PY
echo "OVERNIGHT_JOB_FINISHED: development replay only; quality flags are recorded, not hidden."
