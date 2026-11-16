"""Exact pinned Qwen tokenizer and conservative cross-tokenizer admission bounds."""
import argparse
from pathlib import Path
from .common import CONFIG, ROOT, canonical, digest, file_digest, load, save
from .public import load_cases
from .protocol import planner_prompt, judge_payload, judge_prompt, questions


class QwenCounter:
    def __init__(self, directory, config):
        from tokenizers import Tokenizer
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        directory = Path(directory)
        self.hashes = {name: file_digest(directory / name) for name in config["monitor"]["tokenizer_files"]}
        if self.hashes != config["monitor"]["tokenizer_files"]:
            raise ValueError("Pinned Qwen tokenizer/template mismatch")
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.template = load(directory / "tokenizer_config.json")["chat_template"]
        self.renderer = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True).from_string(self.template)

    def format(self, prompt):
        rendered = self.renderer.render(messages=[{"role": "user", "content": prompt}],
                                        tools=None, add_generation_prompt=True)
        # Exact branch of the frozen template used by every monitor call.
        expected = "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n"
        if rendered != expected:
            raise ValueError("Unexpected Qwen chat-template branch")
        return rendered

    def tokens(self, prompt):
        return self.tokenizer.encode(self.format(prompt), add_special_tokens=False).ids

    def count(self, prompt):
        return len(self.tokens(prompt))


def monitor_capacity(config, cases, counter):
    limits, rows = config["limits"], {}
    for cid, case in cases.items():
        # Planner selection ID can only come from this finite ledger. Bound its
        # largest actual templated payload, never a guessed character/token ratio.
        variants = [{"status": "no_question", "event_id": None, "question": None}]
        variants += [{"status": "selected", "event_id": e["event_id"], "question": "x"}
                     for e in case["ledger"] if e["question_candidate"]]
        ledger_base = max(counter.count(judge_prompt(judge_payload(case, "L", s))) for s in variants)
        # Qwen's byte BPE has at most one token per UTF-8 byte of added JSON. Both
        # question and answer are admitted by serialized UTF-8 length; no clipping.
        qa_reserve = limits["question_json_bytes"] + limits["answer_json_bytes"] + 256
        row = {"planner_input_tokens": counter.count(planner_prompt(case)),
               "passive_input_tokens": counter.count(judge_prompt(judge_payload(case, "P"))),
               "ledger_input_tokens_max": ledger_base,
               "qa_additional_token_upper_bound": qa_reserve}
        row["worst_total_tokens"] = max(row["planner_input_tokens"] + limits["planner_output"],
                                        row["passive_input_tokens"] + limits["judge_output"],
                                        ledger_base + qa_reserve + limits["judge_output"])
        row["eligible"] = row["worst_total_tokens"] <= config["monitor"]["context"]
        rows[cid] = row
    return {"config_sha256": digest(config), "tokenizer_files": counter.hashes,
            "method": "exact pinned byte-BPE/chat-template; bounded serialized QA, no truncation",
            "cases": rows, "monitor_capacity_passed": all(r["eligible"] for r in rows.values()),
            "actor_capacity_passed": False, "ready_for_gpu": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--qwen-tokenizer", required=True, type=Path)
    p.add_argument("--out", type=Path, default=ROOT / "project/matched_followup_v1/monitor_capacity.json")
    args = p.parse_args()
    config = load(CONFIG)
    result = monitor_capacity(config, load_cases(config), QwenCounter(args.qwen_tokenizer, config))
    save(args.out, result)
    print(canonical(result))
