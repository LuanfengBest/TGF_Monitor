#!/bin/bash
#SBATCH --job-name=tgf_pilot
#SBATCH --partition=gpu_h200
#SBATCH --gpus=h200:1
#SBATCH --mem=160G
#SBATCH --cpus-per-task=8
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.log
#SBATCH --mail-type=END,FAIL
# B1, B3, TGF plan -> agent answers (B2 + TGF) -> B2/TGF judge -> metrics.
# Needs tgf_runs/pilot/traces.jsonl (from tgf/gen_traces.sbatch or `python -m tgf.build`).
# Usage: RUN=aa_check sbatch tgf/run_pilot.sbatch   (reads tgf_runs/$RUN/traces.jsonl; MON=..., AGENT=... to override)
set -eo pipefail
module load miniconda
conda activate monitorbench
cd ~/MonitorBench
mkdir -p logs

RUN="tgf_runs/${RUN:-pilot}"
MON=${MON:-Qwen/Qwen3-32B}
AGENT=${AGENT:-openai/gpt-oss-120b}
K=${K:-3}
B3N=${B3N:-3}

echo "== pass1: B1 / B3 / TGF plan (+B0-oracle) with $MON =="
python -m tgf.monitor pass1 --run "$RUN" --model "$MON" --k "$K" --b3-n "$B3N" --oracle

echo "== agent answers follow-ups with $AGENT =="
(
  unset VLLM_ATTENTION_BACKEND
  export VLLM_USE_TRITON_FLASH_ATTN=0
  export VLLM_DISABLE_SINKS=1
  python -m tgf.answer --run "$RUN" --model "$AGENT"
)

echo "== judge: B2 / TGF with $MON =="
python -m tgf.monitor judge --run "$RUN" --model "$MON"

echo "== metrics =="
python -m tgf.metrics --run "$RUN"
