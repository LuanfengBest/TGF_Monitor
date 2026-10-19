#!/bin/bash
#SBATCH --job-name=tony_tgf_gpu_check
#SBATCH --account=cpsc4710
#SBATCH --partition=gpu_h200
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gpus=h200:1
#SBATCH --time=00:05:00
#SBATCH --output=tony_gpu_check_%j.log

# Basic runtime check only: no model loading, downloads, or inference results.
set -euo pipefail
: "${SLURM_JOB_ID:?Run as a Slurm job}"
: "${CUDA_VISIBLE_DEVICES:?Slurm GPU visibility is missing}"
cd "${SLURM_SUBMIT_DIR:?Submit from the package root}"
image=containers/vllm_0.13.0_1ae45c63e057.sif
[[ -f "$image" && ! -L "$image" ]] || { echo "Missing regular container image"; exit 2; }
hostname
apptainer exec --nv --cleanenv \
    --env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES" \
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    "$image" /usr/bin/python3 -I - <<'PY'
import json
from importlib.metadata import version
import torch

assert torch.cuda.is_available(), "CUDA unavailable inside the saved container"
assert torch.cuda.device_count() == 1, "Expected exactly one allocated visible GPU"
device = torch.cuda.get_device_properties(0)
assert "H200" in device.name, f"Expected H200, got {device.name}"
a = torch.ones((32, 32), dtype=torch.bfloat16, device="cuda")
value = (a @ a)[0, 0].item()
torch.cuda.synchronize()
assert value == 32.0, f"CUDA matrix check failed: {value}"
from vllm import LLM  # Import only: do not construct/download a model.

print(json.dumps({
    "check": "basic_gpu_runtime_only_not_model_validation",
    "gpu": device.name,
    "gpu_memory_gib": round(device.total_memory / 1024**3, 2),
    "torch": torch.__version__,
    "cuda_runtime": torch.version.cuda,
    "vllm": version("vllm"),
    "bf16_matmul": "ok",
    "vllm_import": "ok",
}, indent=2), flush=True)
print("GPU_RUNTIME_OK: no model loaded; model kernels and long context remain unvalidated.", flush=True)
PY
