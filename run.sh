set -e

TASKS=(
    "dual_objectives.agent.malicious"
)

EVALUATED_MODEL="openai/gpt-oss-20b"

STRESS_TESTS=(
  "standard"
)

MONITOR_SCOPES=(
    "all"
)

DEVICES=(0)

export OPENAI_API_KEY="YOUR_API_KEY"
export GOOGLE_API_KEY="YOUR_API_KEY"
export ANTHROPIC_API_KEY="YOUR_API_KEY"

if [[ "$EVALUATED_MODEL" == *"gpt-oss"* ]]; then
    unset VLLM_ATTENTION_BACKEND
    export VLLM_USE_TRITON_FLASH_ATTN=0
    export VLLM_DISABLE_SINKS=1
else
    export VLLM_ATTENTION_BACKEND=FLASH_ATTN
fi

join_by_comma () { local IFS=,; echo "$*"; }

STRESS_TESTS=$(join_by_comma "${STRESS_TESTS[@]}")
DEVICES=$(join_by_comma "${DEVICES[@]}")
MONITOR_SCOPES=$(join_by_comma "${MONITOR_SCOPES[@]}")

for task in "${TASKS[@]}"; do
    python main.py --task "$task" \
        --stress-test "$STRESS_TESTS" \
        --device "$DEVICES" \
        --monitor-scope "$MONITOR_SCOPES" \
        --set evaluated_llm.model_name="$EVALUATED_MODEL" \
        --set verification_llm.tensor_parallel=1 \
        --set monitor_llm.tensor_parallel=1
done
