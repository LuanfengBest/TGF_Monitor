#!/bin/bash -l
#SBATCH --job-name=tgf-b1-8k
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/b1_8k_batch-%j.log

set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
ollama serve
trap 'ollama-down || true' EXIT
TGF_OUTPUT="results/b1_8k_${SLURM_JOB_ID}"
mkdir -p "$TGF_OUTPUT"
date -Is
hostname
printf 'job=%s output=%s\n' "$SLURM_JOB_ID" "$TGF_OUTPUT"
.venv/bin/python -c 'import sys; sys.path.insert(0,"scripts"); from ollama_client import Ollama; c=Ollama("'"$TGF_OUTPUT"'/identity"); tags=c.api("tags")["models"]; assert any(m["name"]=="qwen3:32b" and m["digest"]=="030ee887880fc378860c2dd35101da424377520441ae4bfe7be6deff8ade7840" for m in tags), "Cached monitor digest changed"'

for TGF_TRACE in ordinary_002 injected_001; do
    set +e
    .venv/bin/python scripts/run_b1.py \
        --view "results/bank_dev/$TGF_TRACE/monitor_view.json" \
        --config configs/bank_dev_v1_monitor8k.json \
        --output "$TGF_OUTPUT/$TGF_TRACE" \
        > "$TGF_OUTPUT/$TGF_TRACE.log" 2>&1
    TGF_RC=$?
    set -e
    printf '%s\n' "$TGF_RC" > "$TGF_OUTPUT/$TGF_TRACE.exit"
    printf '%s exit=%s\n' "$TGF_TRACE" "$TGF_RC"
    if [ "$TGF_RC" -ne 0 ]; then exit "$TGF_RC"; fi
done
date -Is
