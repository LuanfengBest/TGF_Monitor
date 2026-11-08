"""CPU-only native tokenizer, grammar and existing weight-byte checks. No inference."""
import argparse
import os
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import time

from prospective_monitoring import native_backend as native
from prospective_monitoring.preflight import verify_asset_inventory, check_actor_examples
from . import protocol as p
from .prepare import load_bundle, read, write, sha


def examples(cases, cfg):
    actor, monitor = [], []
    for case in cases:
        def mon(stage, prompt):
            monitor.append({"case_id": case["case_id"], "stage": stage, "prompt": prompt,
                            "max_output_tokens": cfg["stage_output_caps"][stage]})
        mon("review", p.review_prompt(case))
        unit = p.evidence_units(case)[0]
        note = p.review(p.canonical({"notes": [{"claim": "CPU schema check only.", "evidence_id": unit["evidence_id"]}]}), case)
        mon("judge", p.judge_prompt(case, "A", notes=[note]))
        for arm in ("B", "C"):
            question = p.question(case, arm)
            actor.append({"case_id": case["case_id"], "kind": arm + "_followup", "conversation": case["conversation"],
                          "tools": [], "question": question, "max_output_tokens": cfg["stage_output_caps"]["actor"]})
            mon("judge", p.judge_prompt(case, arm, qa={"question": question,
                "answer": "CPU placeholder only; not new permission. " * 40}))
    return actor, monitor


def run(bundle, output, snapshots, prior_assets, max_seconds=1800):
    cfg, cases, _ = load_bundle(bundle)
    if type(max_seconds) is not int or not 1 <= max_seconds <= 3600:
        raise ValueError("Bounded CPU preflight requires 1-3600 seconds")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + max_seconds
    def expired(*_):
        raise TimeoutError("CPU admission deadline; no inference or retry")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(max_seconds)
    receipt = {"schema_version": "anchored-question-preflight-v1", "ready_for_live": False, "job_id": os.environ.get("SLURM_JOB_ID"),
               "bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"), "snapshots": snapshots,
               "model_inference_performed": False, "model_calls": 0, "new_environment_episodes": 0,
               "future_dynamic_prompt_admission": "exact_native_token_count_required_per_dispatch"}
    try:
        receipt["runtime"] = native.runtime_check(cfg)
        receipt["runtime_checked"] = True
        inventory = {}
        for which in ("monitor", "actor"):
            inventory[which] = verify_asset_inventory(snapshots[which], which, prior_assets[which], deadline)
            write(output / (which + "_asset_inventory.json"), inventory[which])
        receipt.update(asset_inventory=inventory, asset_hashes_checked=True)
        actor, monitor = examples(cases, cfg)
        checked_actor = check_actor_examples(snapshots["actor"], actor, deadline)
        write(output / "actor_capacity.json", checked_actor)
        codec = native.NativeCodec("monitor", snapshots["monitor"])
        import xgrammar
        compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(codec.tokenizer))
        checked_monitor = []
        for item in monitor:
            if time.monotonic() >= deadline:
                expired()
            schema = p.output_schema(item["stage"], item["prompt"])
            compiler.compile_json_schema(schema)
            ids = codec.monitor_prompt(item["prompt"])
            if len(ids) + item["max_output_tokens"] > native.PINNED["monitor"]["context"]:
                raise native.CapacityError("Frozen public prompt exceeds monitor context")
            checked_monitor.append({"case_id": item["case_id"], "stage": item["stage"], "prompt_tokens": len(ids),
                                    "reserved_output_tokens": item["max_output_tokens"], "schema_sha256": p.digest(schema)})
        write(output / "monitor_capacity.json", checked_monitor)
        receipt.update(tokenizer_capacity_checked=True, grammar_checked=True, ready_for_live=True,
                       actor_examples=len(actor), monitor_examples=len(monitor),
                       max_actor_prompt_tokens=max(x["prompt_tokens"] for x in checked_actor["examples"]),
                       max_monitor_example_prompt_tokens=max(x["prompt_tokens"] for x in checked_monitor),
                       example_scope="all original histories, all possible target questions; synthetic notes/answers, not future generated text")
    except Exception as exc:
        receipt["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        receipt.update(elapsed_seconds=time.monotonic() - started, completed_at_utc=datetime.now(timezone.utc).isoformat())
        write(output / "preflight.json", receipt)
    return receipt


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "output", "actor-snapshot", "monitor-snapshot", "prior-assets"):
        ap.add_argument("--" + name, required=True, type=Path)
    ap.add_argument("--max-seconds", default=1800, type=int)
    args = ap.parse_args()
    prior = read(args.prior_assets)
    result = run(args.bundle, args.output, {"actor": str(args.actor_snapshot), "monitor": str(args.monitor_snapshot)},
                 prior.get("assets", prior), args.max_seconds)
    print(json.dumps({k: result.get(k) for k in ("ready_for_live", "model_calls", "elapsed_seconds", "error")}))
    if not result["ready_for_live"]:
        raise SystemExit(1)
