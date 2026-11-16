"""Exact local Qwen token counts with the unchanged pinned tokenizer assets."""
import argparse
import hashlib
import json
from pathlib import Path
from . import core
from .run import DEFAULT, planned
from prospective_monitoring.native_backend import TOKENIZER_HASHES


def check(bundle):
    from tokenizers import Tokenizer
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    hashes = {}
    for name, expected in TOKENIZER_HASHES.items():
        actual = hashlib.sha256((bundle / "tokenizer" / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Pinned tokenizer changed")
        hashes[name] = actual
    tokenizer = Tokenizer.from_file(str(bundle / "tokenizer/tokenizer.json"))
    config = json.loads((bundle / "tokenizer/tokenizer_config.json").read_text())
    template = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True).from_string(config["chat_template"])
    capacity = []
    for req in planned(bundle):
        if req["model"] != "qwen":
            continue
        prompt = core.qwen_prompt(req["state"])
        rendered = template.render(messages=[{"role":"user", "content":prompt}], add_generation_prompt=True, enable_thinking=False)
        expected = "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        if rendered != expected:
            raise ValueError("Chat template differs from pinned backend")
        ids = tokenizer.encode(rendered, add_special_tokens=False).ids
        if len(ids) + 2048 > 32768:
            raise ValueError("Input plus output reserve exceeds Qwen context")
        capacity.append({"request_id":req["request_id"], "input_tokens":len(ids), "output_reserve":2048,
                         "prompt_sha256":hashlib.sha256(core.canonical(ids).encode()).hexdigest()})
    return {"qwen_tokenizer_hashes": hashes, "model_calls":0, "qwen_requests":len(capacity),
            "max_qwen_input_tokens":max(r["input_tokens"] for r in capacity),
            "total_qwen_input_tokens":sum(r["input_tokens"] for r in capacity),
            "qwen_context":32768, "all_qwen_inputs_fit":True, "requests":capacity,
            "jev_exact_tokenizer_check":"pending provider interface; no compatible tokenizer published in the checked documentation",
            "jev_max_serialized_request_bytes":max(len(core.canonical(core.jev_body(r["state"])).encode()) for r in planned(bundle) if r["model"]=="jev"),
            "jev_cost_reserve":"124 requests × 32000 input tokens × $0.042/M = $0.166656; cap $0.20, zero retries"}


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--bundle",type=Path,default=DEFAULT)
    args=ap.parse_args()
    result=check(args.bundle)
    with (args.bundle / "capacity_LOCAL.json").open("x") as f:
        json.dump(result,f,indent=2)
    print(core.canonical({k:v for k,v in result.items() if k!="requests"}))
