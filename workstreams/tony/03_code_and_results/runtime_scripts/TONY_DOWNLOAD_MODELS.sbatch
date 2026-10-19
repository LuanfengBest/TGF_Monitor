#!/bin/bash
#SBATCH --job-name=tony_tgf_download
#SBATCH --account=cpsc4710
#SBATCH --partition=education
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=tony_models_%j.log

# CPU/network only. No installation, training, model construction, or deletion.
set -euo pipefail
: "${SLURM_JOB_ID:?Run as a Slurm job}"
cd "${SLURM_SUBMIT_DIR:?Submit from the package root}"
image=containers/vllm_0.13.0_1ae45c63e057.sif
[[ -f TONY_SOURCE_LOCK.json && -f "$image" ]] || { echo "Wrong directory or missing image"; exit 2; }
[[ ! -L models ]] || { echo "Refusing symlink models directory"; exit 2; }
mkdir -p models
[[ ! -L models/.download.lock ]] || { echo "Refusing symlink lock"; exit 2; }
exec 9>> models/.download.lock
flock -n 9 || { echo "Another download job holds this lock; stopping"; exit 2; }
apptainer exec --cleanenv --bind "$PWD:$PWD" --pwd "$PWD" \
    --env "SLURM_JOB_ID=$SLURM_JOB_ID" \
    --env "HF_HOME=$PWD/models/.hf_home" \
    --env HF_HUB_OFFLINE=0 --env TRANSFORMERS_OFFLINE=0 \
    --env HF_HUB_DISABLE_IMPLICIT_TOKEN=1 --env HF_HUB_DISABLE_XET=1 \
    --env HF_HUB_DOWNLOAD_TIMEOUT=60 --env HF_HUB_ETAG_TIMEOUT=30 \
    "$image" /usr/bin/python3 -I -u - <<'PY'
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
from typing import Any


SPECS = (
    {"role": "monitor", "repo": "Qwen/Qwen3-32B", "revision": "9216db5781bf21249d130ec9da846c4624c16137", "count": 17, "bytes": 65524328560, "model_type": "qwen3"},
    {"role": "actor_followup", "repo": "openai/gpt-oss-120b", "revision": "b5c939de8f754692c1647ca79fbf85e8c1e70f8a", "count": 15, "bytes": 65248893184, "model_type": "gpt_oss"},
)


def select_files(info: Any, spec: dict[str, Any]) -> list[Any]:
    if info.sha != spec["revision"]:
        raise ValueError("Server returned an unexpected model revision")
    files = sorted((s for s in info.siblings if "/" not in s.rfilename and "\\" not in s.rfilename
                    and (s.rfilename.endswith((".safetensors", ".json", ".txt", ".jinja", ".model", ".tiktoken"))
                         or s.rfilename in {"LICENSE", "README.md", "USAGE_POLICY"})), key=lambda s: s.rfilename)
    names = {s.rfilename for s in files}
    required = {"config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors.index.json"}
    if not required <= names or len(names) != len(files):
        raise ValueError("Missing required configuration/tokenizer/index or duplicate files")
    weights = [s for s in files if s.rfilename.endswith(".safetensors")]
    if len(weights) != spec["count"] or sum(s.size or 0 for s in weights) != spec["bytes"]:
        raise ValueError("Weight count/bytes differ from the approved fixed revision")
    for entry in files:
        if not isinstance(entry.size, int) or entry.size < 0:
            raise ValueError(f"Missing size: {entry.rfilename}")
        expected = entry.lfs.sha256 if entry.lfs else entry.blob_id
        length = 64 if entry.lfs else 40
        if not isinstance(expected, str) or len(expected) != length or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError(f"Missing integrity metadata: {entry.rfilename}")
    return files


def verify_file(path: Path, entry: Any) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size != entry.size:
        raise ValueError(f"Missing/wrong-sized/symlink file: {path.name}")
    digest = hashlib.sha256() if entry.lfs else hashlib.sha1()
    if not entry.lfs:
        digest.update(f"blob {entry.size}\0".encode())
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    expected = entry.lfs.sha256 if entry.lfs else entry.blob_id
    if actual != expected:
        raise ValueError(f"Integrity check failed: {path.name}; retained file, no automatic deletion")
    return actual


def main() -> None:
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoTokenizer

    job_id = os.environ["SLURM_JOB_ID"]
    root = (Path.cwd() / "models").resolve(strict=True)
    api = HfApi(endpoint="https://huggingface.co", token=False)
    plans = []
    for spec in SPECS:
        info = api.model_info(spec["repo"], revision=spec["revision"], files_metadata=True, timeout=30)
        files = select_files(info, spec)
        folder = root / (spec["repo"].replace("/", "--") + "--" + spec["revision"][:12])
        if folder.is_symlink() or folder.resolve().parent != root:
            raise ValueError("Model destination must stay within this project models directory")
        folder.mkdir(exist_ok=True)
        if any((folder / s.rfilename).is_symlink() for s in files):
            raise ValueError("Refusing pre-existing model file symlinks")
        remaining = sum(s.size for s in files if not (folder / s.rfilename).is_file()
                        or (folder / s.rfilename).stat().st_size != s.size)
        plans.append((spec, files, folder, remaining))
    remaining = sum(p[3] for p in plans)
    if shutil.disk_usage(root).free < remaining + 20 * 1024**3:
        raise RuntimeError("Need remaining download bytes plus 20 GiB free headroom")
    receipt = {"job_id": job_id, "status": "VERIFIED_WEIGHTS_NOT_MODEL_INFERENCE", "started_utc": datetime.now(timezone.utc).isoformat(),
               "huggingface_hub": version("huggingface-hub"), "transformers": version("transformers"), "models": []}
    print(f"DOWNLOAD_PLAN: {remaining / 1024**3:.2f} GiB remaining; two workers; public fixed revisions; no GPU", flush=True)
    for spec, files, folder, _ in plans:
        print(f"DOWNLOADING: {spec['repo']} revision={spec['revision']} destination={folder}", flush=True)
        snapshot_download(repo_id=spec["repo"], revision=spec["revision"], token=False,
                          local_dir=str(folder), allow_patterns=[s.rfilename for s in files], max_workers=2)
        verified = []
        for entry in files:
            print(f"VERIFYING: {spec['repo']} {entry.rfilename}", flush=True)
            verified.append({"file": entry.rfilename, "bytes": entry.size,
                             "algorithm": "sha256" if entry.lfs else "git_blob_sha1",
                             "digest": verify_file(folder / entry.rfilename, entry)})
        index = json.loads((folder / "model.safetensors.index.json").read_text(encoding="utf-8"))
        shards = {s.rfilename for s in files if s.rfilename.endswith(".safetensors")}
        if set(index["weight_map"].values()) != shards:
            raise ValueError("Weight index does not match the downloaded shards")
        config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        if config.get("model_type") != spec["model_type"]:
            raise ValueError("Unexpected model architecture")
        tokenizer = AutoTokenizer.from_pretrained(str(folder), local_files_only=True, trust_remote_code=False)
        encoded = tokenizer.encode("TGF runtime check", add_special_tokens=False)
        if not encoded:
            raise ValueError("Local tokenizer check returned no tokens")
        receipt["models"].append({**spec, "path": str(folder), "files": verified, "local_tokenizer": "ok"})
        print(f"MODEL_VERIFIED: {spec['repo']}; no weights loaded into RAM/GPU", flush=True)
    receipt["completed_utc"] = datetime.now(timezone.utc).isoformat()
    receipt_path = root / f"verified_models_{job_id}.json"
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print(f"MODEL_WEIGHTS_READY: {receipt_path}; model loading/kernels/long context remain unvalidated.", flush=True)


if __name__ == "__main__":
    main()
PY
