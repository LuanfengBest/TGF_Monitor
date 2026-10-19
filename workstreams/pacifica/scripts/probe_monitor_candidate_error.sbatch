#!/bin/bash -l
#SBATCH --job-name=monitor-candidate-error-probe
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:02:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_candidate_error_probe-%j.log
set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
unset REAL_OLLAMA_BIN
candidate_log_root="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"
candidate_gpu_tag="${CUDA_VISIBLE_DEVICES:-na}"
candidate_gpu_tag="${candidate_gpu_tag//,/_}"
candidate_server_log="${candidate_log_root}/ollama_${USER}_${SLURM_JOB_ID}_gpu${candidate_gpu_tag}/ollama-serve.log"
trap 'ollama-down || true; cp "$candidate_server_log" "logs/monitor_candidate_server_${SLURM_JOB_ID}.log" || true' EXIT
ollama serve
timeout --signal=TERM --kill-after=5s 100s .venv/bin/python scripts/probe_monitor_candidate_error.py
