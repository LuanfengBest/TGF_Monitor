#!/bin/bash
#SBATCH --job-name=tgf_pilot
#SBATCH --partition=gpu_h200
#SBATCH --gpus=h200:1
#SBATCH --mem=160G
#SBATCH --cpus-per-task=8
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x_%j.log
#SBATCH --mail-type=END,FAIL
# B1, B3, TGF plan -> agent answers (B2 + TGF) -> B2/TGF judge -> metrics.
# Needs tgf_runs/$RUN/traces.jsonl (from tgf/gen_traces.sbatch or `python -m tgf.build`).
# Usage: RUN=both_n8_ctx128k sbatch tgf/run_pilot.sbatch   (MON=..., AGENT=..., ROPE=..., TOOL_LIMIT=2000 to override)
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
ROPE=${ROPE:-4}             # monitor window = 32768 x ROPE (4 -> 131072, Qwen3 maximum)
AGENT_CTX=${AGENT_CTX:-131072}
TL=${TOOL_LIMIT:+--tool-limit $TOOL_LIMIT}   # TOOL_LIMIT=2000 reproduces MonitorBench's per-tool-output clip; empty = full
echo "run=$RUN monitor=$MON (rope x$ROPE) agent=$AGENT (ctx $AGENT_CTX) k=$K b3n=$B3N tool_limit=${TOOL_LIMIT:-full}"

echo "== pass1: B1 / B3 / TGF plan (+B0-oracle) with $MON =="
python -m tgf.monitor pass1 --run "$RUN" --model "$MON" --k "$K" --b3-n "$B3N" --rope-factor "$ROPE" $TL --oracle

echo "== agent answers follow-ups with $AGENT =="
(
  unset VLLM_ATTENTION_BACKEND
  export VLLM_USE_TRITON_FLASH_ATTN=0
  export VLLM_DISABLE_SINKS=1
  python -m tgf.answer --run "$RUN" --model "$AGENT" --max-model-len "$AGENT_CTX"
)

echo "== judge: B2 / TGF with $MON =="
python -m tgf.monitor judge --run "$RUN" --model "$MON" --rope-factor "$ROPE" $TL

echo "== metrics =="
python -m tgf.metrics --run "$RUN"
python -m tgf.metrics --run "$RUN" --exclude refused,overflow --out metrics_clean.md > /dev/null
echo "also wrote $RUN/metrics_clean.md (refusals and overflowed runs removed)"
