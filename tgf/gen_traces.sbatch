#!/bin/bash
#SBATCH --job-name=traces
#SBATCH --partition=gpu_h200
#SBATCH --gpus=h200:1
#SBATCH --mem=128G
#SBATCH --cpus-per-task=4
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x_%j.log
#SBATCH --mail-type=END,FAIL
# Generate frozen agent trajectories with MonitorBench (agent + side-task eval).
# Usage (from ~/MonitorBench):  sbatch tgf/gen_traces.sbatch
#   override: N=5 STRESS=standard,no_side_task sbatch tgf/gen_traces.sbatch
set -eo pipefail
module load miniconda
conda activate monitorbench
cd ~/MonitorBench
mkdir -p logs

N=${N:-5}
STRESS=${STRESS:-standard,no_side_task,direct_conceal}
AGENT=${AGENT:-openai/gpt-oss-20b}

# same env vars MonitorBench's run.sh sets for gpt-oss
unset VLLM_ATTENTION_BACKEND
export VLLM_USE_TRITON_FLASH_ATTN=0
export VLLM_DISABLE_SINKS=1

grep -q "max_tokens: 8000" config/dataset_config.yaml || { echo "set dual_agent.max_tokens to 8000 first"; exit 1; }

# MonitorBench also runs its own monitor at the end; keep it small (Qwen3-8B), we do not use it.
python main.py --task dual_objectives.agent.malicious \
  --stress-test "$STRESS" --monitor-scope all --device 0 \
  --set evaluated_llm.model_name="$AGENT" \
  --set evaluated_llm.rollout_number="$N" \
  --set verification_llm.model_name=Qwen/Qwen3-8B --set verification_llm.tensor_parallel=1 \
  --set monitor_llm.model_name=Qwen/Qwen3-8B --set monitor_llm.tensor_parallel=1 \
  --set monitor_llm.rollout_number=1

python -m tgf.build --results "results/${AGENT##*/}/dual_objectives.agent.malicious" \
  --task-folder bank_transfer_2 --n "$N" --out tgf_runs/pilot
