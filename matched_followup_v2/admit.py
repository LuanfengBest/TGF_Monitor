"""Freeze capacity-eligible cases before any v2 generation; log all exclusions."""
import argparse
from pathlib import Path
from .common import CONFIG, load, save, digest
from .public import load_cases
from .capacity import QwenCounter, monitor_capacity
from .native import HarmonyCodec


def admit(qwen, output):
    c = load(CONFIG)
    cases = load_cases(c)
    monitor = monitor_capacity(c, cases, QwenCounter(qwen, c))
    codec = HarmonyCodec()
    rows = {}
    for cid, case in cases.items():
        total = len(codec.prompt(case["conversation"], "")) + c["limits"]["question_actor_tokens"] + c["limits"]["actor_output"] + 16
        rows[cid] = {"monitor": monitor["cases"][cid], "actor_worst_tokens": total,
                     "eligible": monitor["cases"][cid]["eligible"] and total <= c["actor"]["context"]}
    if not all(rows[cid]["eligible"] for cid in c["pilot_cases"]):
        raise ValueError("Fixed pilot ineligible; no replacement allowed")
    original = c["cases"]
    c["cases"] = [cid for cid in original if rows[cid]["eligible"]]
    save(output, {"original_denominator": len(original), "admitted_denominator": len(c["cases"]),
                  "excluded": [cid for cid in original if not rows[cid]["eligible"]],
                  "cases": rows, "selection_rule": "source binding and token capacity only, before inference",
                  "config_sha256": digest(c)})
    save(CONFIG, c)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--qwen-snapshot", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    admit(a.qwen_snapshot, a.out)
