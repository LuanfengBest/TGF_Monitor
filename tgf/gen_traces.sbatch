#!/bin/bash
#SBATCH --job-name=traces
#SBATCH --partition=gpu_h200
#SBATCH --gpus=h200:1
#SBATCH --mem=160G
#SBATCH --cpus-per-task=4
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.log
#SBATCH --mail-type=END,FAIL
# Generate frozen agent trajectories with MonitorBench (agent + side-task eval), then build labels.
# Which task pairs run is set by dual_agent.task_folders in config/dataset_config.yaml.
# Usage (from ~/MonitorBench):
#   N=8 RUN=both_n8_ctx128k sbatch tgf/gen_traces.sbatch
# Results go to $OUT (default results_ctx<CTX>), so earlier results are never overwritten
# (MonitorBench skips a stress test whose output files already exist).
set -eo pipefail
module load miniconda
conda activate monitorbench
cd ~/MonitorBench
mkdir -p logs

N=${N:-8}
STRESS=${STRESS:-standard,direct_conceal,monitor_aware,no_side_task}
AGENT=${AGENT:-openai/gpt-oss-120b}
TASKS=${TASKS:-bank_transfer_2,american_airlines_2}
CTX=${CTX:-131072}          # gpt-oss native context; MonitorBench default is 32768, which cuts airline runs off
OUT=${OUT:-results_ctx${CTX}}
RUN=${RUN:-pilot}

# same env vars MonitorBench's run.sh sets for gpt-oss
unset VLLM_ATTENTION_BACKEND
export VLLM_USE_TRITON_FLASH_ATTN=0
export VLLM_DISABLE_SINKS=1

grep -q "max_tokens: 8000" config/dataset_config.yaml || { echo "set dual_agent.max_tokens to 8000 first"; exit 1; }
echo "task_folders in config:"; grep -A8 "task_folders" config/dataset_config.yaml
echo "agent=$AGENT N=$N stress=$STRESS ctx=$CTX out=$OUT run=$RUN"

# MonitorBench also runs its own monitor at the end; keep it small (Qwen3-8B), we do not use it.
python main.py --task dual_objectives.agent.malicious \
  --stress-test "$STRESS" --monitor-scope all --device 0 \
  --output-base-dir "$OUT" \
  --set evaluated_llm.model_name="$AGENT" \
  --set evaluated_llm.rollout_number="$N" \
  --set evaluated_llm.max_model_len="$CTX" \
  --set verification_llm.model_name=Qwen/Qwen3-8B --set verification_llm.tensor_parallel=1 \
  --set monitor_llm.model_name=Qwen/Qwen3-8B --set monitor_llm.tensor_parallel=1 \
  --set monitor_llm.rollout_number=1

python -m tgf.build --results "$OUT/${AGENT##*/}/dual_objectives.agent.malicious" \
  --task-folder "$TASKS" --n "$N" --out "tgf_runs/$RUN"
