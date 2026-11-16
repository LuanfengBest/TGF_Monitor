"""Cluster CPU admission: declared reference, exact tokenizers, pinned runtime/assets."""
import argparse
import hashlib
from importlib.metadata import version
from pathlib import Path
import platform
from .capacity import QwenCounter, monitor_capacity
from .common import CONFIG, digest, file_digest, freeze_hashes, load, save
from .native import HarmonyCodec
from .public import load_cases
from .review import validate_reference


def runtime_check(config):
    found = {"python": platform.python_version()}
    found.update({key: version(key) for key in config["runtime"] if key != "python"})
    if found != config["runtime"]:
        raise ValueError(f"Pinned runtime mismatch: {found}")
    found["PyYAML"] = version("PyYAML")
    return found


def snapshot_inventory(path, spec):
    path = Path(path).absolute()
    if path.name != spec["revision"] or path.parent.name != "snapshots":
        raise ValueError("Use the exact pinned Hugging Face cache snapshot directory")
    config_path = path / "config.json"
    index = load(path / "model.safetensors.index.json")
    names = sorted(set(index["weight_map"].values()))
    files = {}
    for name in ["config.json", "model.safetensors.index.json"] + names:
        file = path / name
        if not file.is_file() or file.stat().st_size == 0:
            raise ValueError("Missing local model file: " + name)
        # Hugging Face LFS blobs use their SHA-256 as the resolved filename.
        # Verify bytes once on the CPU before reserving a GPU, not just the path.
        sha = hashlib.sha256()
        with file.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                sha.update(block)
        checksum = sha.hexdigest()
        if name in names and file.resolve().name != checksum:
            raise ValueError("Weight blob is not content-addressed as recorded by the HF cache: " + name)
        files[name] = {"bytes": file.stat().st_size, "sha256": checksum, "mtime_ns": file.stat().st_mtime_ns}
    model_config = load(config_path)
    if spec.get("quantization") and model_config.get("quantization_config", {}).get("quant_method") != spec["quantization"]:
        raise ValueError("Actor quantization mismatch")
    return {"directory": str(path), "revision": spec["revision"], "files": files}


def preflight(qwen, actor, review_paths, output):
    config, receipt = load(CONFIG), {"ready_for_gpu": False}
    try:
        cases = load_cases(config)
        reviewed = validate_reference(review_paths, config, cases)
        receipt["reference_mode"] = reviewed["reference_mode"]
        receipt["human_review_complete"] = reviewed["human_review_complete"]
        receipt["reference_sha256"] = digest(reviewed)
        receipt["review_files"] = {str(Path(p).absolute()): file_digest(p) for p in review_paths}
        receipt["runtime"] = runtime_check(config)
        counter = QwenCounter(qwen, config)
        receipt["monitor_capacity"] = monitor_capacity(config, cases, counter)
        if not receipt["monitor_capacity"]["monitor_capacity_passed"]:
            raise ValueError("Monitor worst-case capacity failed")
        codec = HarmonyCodec()
        actor_counts = {}
        for cid, case in cases.items():
            base_ids = codec.prompt(case["conversation"], "")
            base = len(base_ids)
            # Question is a separately encoded Harmony message content segment;
            # 16 tokens cover any boundary variation, verified again per actual call.
            total = base + config["limits"]["question_actor_tokens"] + config["limits"]["actor_output"] + 16
            actor_counts[cid] = {"native_base_tokens": base, "native_base_sha256": digest(base_ids), "worst_total_tokens": total,
                                 "eligible": total <= config["actor"]["context"]}
        receipt["actor_capacity"] = actor_counts
        if not all(r["eligible"] for r in actor_counts.values()):
            raise ValueError("Native Harmony capacity failed")
        receipt["assets"] = {"monitor": snapshot_inventory(qwen, config["monitor"]),
                             "actor": snapshot_inventory(actor, config["actor"])}
        receipt.update(config_sha256=digest(config), code_hashes=freeze_hashes(), ready_for_gpu=True,
                       case_public_hashes={cid: c["public_sha256"] for cid, c in cases.items()})
    except Exception as exc:
        receipt["blocked_reason"] = f"{type(exc).__name__}: {exc}"
        save(output, receipt)
        raise
    save(output, receipt)
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--qwen-snapshot", required=True, type=Path)
    p.add_argument("--actor-snapshot", required=True, type=Path)
    p.add_argument("--reviews", nargs="+", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    preflight(args.qwen_snapshot, args.actor_snapshot, args.reviews, args.out)
