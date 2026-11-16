"""Three isolated model stages inside one reserved, bounded Slurm allocation."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .budget import Budget
from .capacity import QwenCounter
from .common import CONFIG, ROOT, canonical, digest, file_digest, freeze_hashes, load, save
from .native import HarmonyCodec
from .preflight import runtime_check
from .protocol import judgment, judge_payload, judge_prompt, planner_prompt, questions, selection
from .public import load_cases
from .review import validate_reference


def check_receipt(receipt, config):
    if receipt.get("ready_for_gpu") is not True:
        raise ValueError("CPU admission has not passed")
    if receipt["config_sha256"] != digest(config) or receipt["code_hashes"] != freeze_hashes():
        raise ValueError("Preflight is stale")
    for path, expected in receipt["review_files"].items():
        if file_digest(path) != expected:
            raise ValueError("Reference changed after preflight")
    reviewed = validate_reference(list(receipt["review_files"]), config, load_cases(config))
    if digest(reviewed) != receipt["reference_sha256"]:
        raise ValueError("Reference receipt mismatch")
    if runtime_check(config) != receipt["runtime"]:
        raise ValueError("Runtime changed after CPU preflight")
    for asset in receipt["assets"].values():
        for name, meta in asset["files"].items():
            path = Path(asset["directory"]) / name
            if path.stat().st_size != meta["bytes"] or path.stat().st_mtime_ns != meta["mtime_ns"]:
                raise ValueError("Model file changed after CPU preflight")
            if name.endswith(".safetensors") and path.resolve().name != meta["sha256"]:
                raise ValueError("Weight snapshot link changed")


class VLLMBackend:
    def __init__(self, which, config, receipt):
        import torch
        from vllm import LLM
        if torch.cuda.device_count() != 1 or "H200" not in torch.cuda.get_device_name(0):
            raise ValueError("Frozen diagnostic requires exactly one H200")
        self.which, self.config = which, config
        spec = config[which]
        snapshot = receipt["assets"][which]["directory"]
        kwargs = {"model": snapshot, "tokenizer": snapshot, "revision": spec["revision"],
                  "tokenizer_revision": spec["revision"], "tensor_parallel_size": 1,
                  "gpu_memory_utilization": 0.90, "max_model_len": spec["context"],
                  "seed": config["seed"], "max_num_seqs": 1, "trust_remote_code": False}
        if which == "monitor":
            kwargs["hf_overrides"] = {"rope_parameters": {"rope_type": "yarn", "factor": spec["rope_factor"],
                                                         "original_max_position_embeddings": spec["original_context"]}}
            self.counter = QwenCounter(snapshot, config)
        else:
            kwargs["quantization"] = spec["quantization"]
            self.codec = HarmonyCodec()
        self.llm = LLM(**kwargs)

    def encode_monitor(self, text):
        tok = self.llm.get_tokenizer()
        rendered = tok.apply_chat_template([{"role": "user", "content": text}], tokenize=False,
                                           add_generation_prompt=True)
        ids = tok.encode(rendered, add_special_tokens=False)
        if rendered != self.counter.format(text) or ids != self.counter.tokens(text):
            raise ValueError("Live tokenizer/chat template differs from CPU admission")
        return ids

    def generate(self, ids, kind, seed):
        from vllm import SamplingParams
        kwargs = {"max_tokens": self.config["limits"][kind + "_output"],
                  "temperature": self.config["temperature"], "top_p": self.config[self.which]["top_p"], "seed": seed}
        if self.which == "actor":
            kwargs["stop_token_ids"] = self.codec.enc.stop_tokens_for_assistant_actions()
        outputs = self.llm.generate([{"prompt_token_ids": ids}], SamplingParams(**kwargs), use_tqdm=False)
        if len(outputs) != 1 or len(outputs[0].outputs) != 1:
            raise RuntimeError("Unexpected backend response count")
        result, output = outputs[0], outputs[0].outputs[0]
        if list(result.prompt_token_ids) != ids:
            raise RuntimeError("Backend prompt tokens changed")
        return {"text": output.text, "token_ids": list(output.token_ids),
                "prompt_tokens": len(ids), "completion_tokens": len(output.token_ids),
                "finish_reason": output.finish_reason, "stop_reason": output.stop_reason}


class Experiment:
    def __init__(self, config, cases, directory, backend):
        self.config, self.cases, self.directory, self.backend = config, cases, Path(directory), backend
        self.budget = Budget(directory, config)

    def call(self, slot, ids, input_record):
        spec = self.budget.state()["slots"][slot]
        # Actor input tokens encode private original instructions: keep their
        # artifacts in a separate path that monitor prompt construction never reads.
        group = "actor_private" if spec["kind"] == "actor" else "monitor_inputs"
        save(self.directory / group / (slot + ".json"), dict(input_record, prompt_token_ids=ids))
        item = self.budget.dispatch(slot, len(ids), digest(ids))
        # A backend exception deliberately leaves a dispatched, nonretryable slot.
        result = self.backend.generate(ids, item["kind"], item["seed"])
        save(self.directory / "raw_outputs" / (slot + ".json"), result)
        self.budget.complete(slot, result)
        if result["finish_reason"] not in {"stop", "length"}:
            raise RuntimeError("Service returned an unsuccessful finish reason")
        return result

    def judge(self, slot, case, payload):
        prompt = judge_prompt(payload)
        raw = self.call(slot, self.backend.encode_monitor(prompt), {"payload": payload, "prompt": prompt})
        try:
            result = {"status": "valid", "judgment": judgment(raw["text"], case, raw["finish_reason"])}
        except (ValueError, TypeError, KeyError) as exc:
            result = {"status": "unknown", "judgment": None, "error": str(exc)}
        save(self.directory / "judgments" / (slot + ".json"), result)

    def pass1(self, index):
        cid = self.config["cases"][index]
        case, prefix = self.cases[cid], f"c{index:02d}"
        prompt = planner_prompt(case)
        raw = self.call(prefix + ".planner", self.backend.encode_monitor(prompt), {"prompt": prompt})
        try:
            selected = selection(raw["text"], case, raw["finish_reason"])
        except (ValueError, TypeError, KeyError) as exc:
            selected = {"status": "invalid_planner", "event_id": None, "question": None, "error": str(exc)}
        save(self.directory / "selection" / (prefix + ".json"), selected)
        self.judge(prefix + ".P", case, judge_payload(case, "P"))
        payload = judge_payload(case, "L", selected)
        self.judge(prefix + ".L", case, payload)
        for seed in self.config["ledger_repeat_seeds"]:
            self.judge(f"{prefix}.L{seed}", case, payload)

    def actors(self, index):
        cid = self.config["cases"][index]
        case, prefix = self.cases[cid], f"c{index:02d}"
        selected = load(self.directory / "selection" / (prefix + ".json"))
        if selected["status"] != "selected":
            for arm in ("F", "T"):
                self.budget.skip(prefix + ".actor" + arm, selected["status"])
            return
        qs = questions(case, selected)
        codec, limits = self.backend.codec, self.config["limits"]
        # Validate BOTH arms before dispatching either. Never shorten a question.
        prompts = {arm: codec.prompt(case["conversation"], question) for arm, question in qs.items()}
        for arm, question in qs.items():
            if codec.count_question(question) > limits["question_actor_tokens"] or len(canonical(question).encode()) > limits["question_json_bytes"]:
                raise ValueError("Paired question capacity failed; no substitution or clipping")
            if len(prompts[arm]) + limits["actor_output"] > self.config["actor"]["context"]:
                raise ValueError("Native history exceeds actual actor capacity")
        save(self.directory / "questions" / (prefix + ".json"), qs)
        # Reverse F/T dispatch order for alternating cases to reduce order confounding.
        for arm in (("F", "T") if index % 2 == 0 else ("T", "F")):
            raw = self.call(prefix + ".actor" + arm, prompts[arm],
                            {"question": qs[arm], "frozen_conversation_sha256": case["conversation_sha256"]})
            try:
                parsed = codec.answer(raw["token_ids"], raw["finish_reason"])
                if len(canonical(parsed["answer"]).encode()) > limits["answer_json_bytes"]:
                    raise ValueError("Final answer exceeds shared JSON-byte admission limit")
                answer = {"status": "valid", **parsed}
            except (ValueError, TypeError, KeyError, RuntimeError) as exc:
                answer = {"status": "unknown", "answer": None, "error": str(exc)}
            save(self.directory / "answers" / (prefix + "." + arm + ".json"), answer)

    def pass2(self, index):
        cid = self.config["cases"][index]
        case, prefix = self.cases[cid], f"c{index:02d}"
        selected = load(self.directory / "selection" / (prefix + ".json"))
        if selected["status"] == "invalid_planner":
            for arm in ("F", "T"):
                self.budget.skip(prefix + "." + arm, "invalid_planner")
            return
        qs = questions(case, selected)
        for arm in (("T", "F") if index % 2 == 0 else ("F", "T")):
            qa = None
            if selected["status"] == "selected":
                answer = load(self.directory / "answers" / (prefix + "." + arm + ".json"))
                if answer["status"] != "valid":
                    self.budget.skip(prefix + "." + arm, "invalid_actor_answer")
                    continue
                # Only final answer reaches the judge; actor reasoning stays archived.
                qa = {"question": qs[arm], "answer": answer["answer"]}
            self.judge(prefix + "." + arm, case, judge_payload(case, arm, selected, qa))


def stage(name, directory):
    config = load(CONFIG)
    budget = Budget(directory, config)
    state = budget.state()
    if state["status"] == "closed":
        raise ValueError("Run is already closed; restart is disabled")
    receipt = state["preflight"]
    check_receipt(receipt, config)
    stages = ("pass1", "actors", "pass2")
    previous = stages.index(name) - 1
    if previous >= 0 and not (Path(directory) / (stages[previous] + ".complete")).exists():
        raise ValueError("Previous model stage has not completed")
    fd = os.open(Path(directory) / (name + ".started"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    which = "actor" if name == "actors" else "monitor"
    cases = load_cases(config)
    if which == "actor":
        codec = HarmonyCodec()
        for cid, case in cases.items():
            if digest(codec.prompt(case["conversation"], "")) != receipt["actor_capacity"][cid]["native_base_sha256"]:
                raise ValueError("Harmony tokenizer/history differs from CPU admission")
    backend = VLLMBackend(which, config, receipt)
    experiment = Experiment(config, cases, directory, backend)
    # First bank + first airline are the sentinel pair, inside the 72-call budget.
    order = [0, 4, 1, 2, 3, 5, 6, 7]
    for index in order:
        getattr(experiment, name)(index)
    (Path(directory) / (name + ".complete")).write_text("completed\n")


def run(preflight_path, directory):
    config, receipt = load(CONFIG), load(preflight_path)
    check_receipt(receipt, config)
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("TGF_ALLOCATION_START"):
        raise ValueError("Use the bounded Slurm entrypoint; direct unbounded launch is disabled")
    started = float(os.environ["TGF_ALLOCATION_START"])
    if not 0 <= time.time() - started < 300:
        raise ValueError("Invalid/stale allocation start time")
    claim = Path(str(preflight_path) + ".claimed")
    fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(canonical({"run": str(directory), "slurm_job_id": os.environ["SLURM_JOB_ID"]}))
    budget = Budget(directory, config)
    budget.initialize(receipt, now=started)
    save(Path(directory) / "frozen_config.json", config)
    reason = "completed"
    try:
        for number, name in enumerate(("pass1", "actors", "pass2")):
            if budget.remaining() < config["limits"]["stage_minimum_remaining_seconds"][number]:
                raise TimeoutError("Insufficient reserved time to start next model stage")
            process = subprocess.Popen([sys.executable, "-m", "matched_followup.runner", "stage",
                                        "--name", name, "--run", str(directory)], start_new_session=True)
            try:
                status = process.wait(timeout=max(1, budget.remaining() - 20))
            except BaseException:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
            if status:
                raise RuntimeError(f"Stage {name} failed with status {status}; no retry")
    except BaseException as exc:
        reason = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        budget.close(reason)
        from .report import report
        report(directory)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    live = sub.add_parser("run")
    live.add_argument("--preflight", required=True, type=Path)
    live.add_argument("--run", required=True, type=Path)
    child = sub.add_parser("stage")
    child.add_argument("--name", required=True, choices=("pass1", "actors", "pass2"))
    child.add_argument("--run", required=True, type=Path)
    args = p.parse_args()
    if args.command == "run":
        run(args.preflight, args.run)
    else:
        stage(args.name, args.run)
