"""Replay the supplied, unchanged Luanfeng v4 on development traces only."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_info(value: str | None) -> dict[str, str]:
    if not value:
        raise ValueError("Provide both local model snapshot directories; no downloads are performed by this launcher.")
    path = Path(value).expanduser().resolve(strict=True)
    config = path / "config.json"
    if not path.is_dir() or not config.is_file():
        raise ValueError(f"Not a model snapshot directory containing config.json: {path}")
    if not any(path.glob("*.safetensors")):
        raise ValueError(f"No safetensors model weights found in {path}")
    data = json.loads(config.read_text(encoding="utf-8"))
    return {"path": str(path), "config_sha256": digest(config), "model_type": str(data.get("model_type"))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="FAKE outputs, no model imports or GPU")
    parser.add_argument("--limit", type=int, default=2, help="First N development records; 2 for integration, 64 for full replay")
    parser.add_argument("--monitor-dir", default=os.environ.get("TGF_MONITOR_DIR"))
    parser.add_argument("--actor-dir", default=os.environ.get("TGF_ACTOR_DIR"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    source = ROOT / "inputs" / "dev64.jsonl"
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(records) != 64 or len({row["id"] for row in records}) != 64:
        parser.error("Expected the supplied 64 unique development trajectories")
    if not 1 <= args.limit <= len(records):
        parser.error("--limit must be between 1 and 64")
    versions: dict[str, str] = {}
    models: dict[str, dict[str, str]] = {}
    if not args.dry_run:
        if not os.environ.get("SLURM_JOB_ID"):
            parser.error("Real inference must run inside an allocated Slurm job, not on a login node")
        try:
            for name in ("vllm", "torch", "transformers", "openai-harmony"):
                versions[name] = metadata.version(name)
            models = {"monitor": model_info(args.monitor_dir), "actor": model_info(args.actor_dir)}
        except (ValueError, OSError, metadata.PackageNotFoundError) as exc:
            parser.error(str(exc))

    mode = "DRY_RUN_ONLY" if args.dry_run else "REAL_DEV_REPLAY"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = ROOT / "runs" / f"{mode}_{stamp}_{uuid.uuid4().hex[:8]}"
    run.mkdir(parents=True, exist_ok=False)
    selected = records[:args.limit]
    with (run / "traces.jsonl").open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "mode": mode, "data_role": "development_only_not_fresh_test",
        "method": "unchanged_legacy_v4_NOT_matched_B2_TGF",
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "seed": args.seed,
        "record_ids": [row["id"] for row in selected],
        "selection": "first_N_in_source_order_integration_not_representative_sampling",
        "source_sha256": digest(source), "selected_sha256": digest(run / "traces.jsonl"),
        "code_sha256": {path.name: digest(path) for path in sorted((ROOT / "tgf").glob("*.py"))},
        "versions": versions, "models": models, "completed_stages": [], "status": "STARTED",
    }
    manifest_path = run / "manifest.json"

    def save_manifest() -> None:
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    run_arg = ["--run", str(run)]
    seed_arg = ["--seed", str(args.seed)]
    fake_arg = ["--dry-run"] if args.dry_run else []
    monitor_model = args.monitor_dir or "Qwen/Qwen3-32B"
    actor_model = args.actor_dir or "openai/gpt-oss-120b"
    monitor_args = [*run_arg, "--model", monitor_model, "--scope", "all", "--rope-factor", "4",
                    "--max-model-len", "32768", "--max-new", "8192", *seed_arg, *fake_arg]
    commands = [
        ("pass1", ["tgf.monitor", "pass1", *monitor_args, "--k", "3", "--b3-n", "3"]),
        ("answers", ["tgf.answer", *run_arg, "--model", actor_model, "--b2-samples", "1",
                     "--max-model-len", "131072", "--max-new", "4096", *seed_arg, *fake_arg]),
        ("judge", ["tgf.monitor", "judge", *monitor_args]),
        ("metrics", ["tgf.metrics", *run_arg, "--boot", "100" if args.dry_run else "2000"]),
    ]
    print(f"MODE={mode}\nRUN_DIR={run}", flush=True)
    print("Legacy replay only: not a matched-method comparison or fresh test.", flush=True)
    save_manifest()
    try:
        for stage, command in commands:
            stage_env = env.copy()
            if stage == "answers":
                stage_env.pop("VLLM_ATTENTION_BACKEND", None)
                stage_env.update({"VLLM_USE_TRITON_FLASH_ATTN": "0", "VLLM_DISABLE_SINKS": "1"})
            print(f"STAGE={stage}", flush=True)
            subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", *command], cwd=ROOT, env=stage_env, check=True)
            manifest["completed_stages"].append(stage)
            save_manifest()
    except BaseException:
        manifest["status"] = "FAILED_OR_INTERRUPTED"
        save_manifest()
        raise
    manifest["status"] = "COMPLETED_FAKE_ONLY" if args.dry_run else "COMPLETED_DEV_REPLAY"
    save_manifest()


if __name__ == "__main__":
    main()
