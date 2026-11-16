"""Bounded, staged prospective DEVELOPMENT campaign.

Collection and monitoring use four model-load phases, never one load per case.
The default mode is CPU fixtures. Live mode requires its own exact code/config
admission and authorization receipts; it cannot reuse a v2 receipt or offline flag.
No model is imported or loaded on import. There is no automatic test-set expansion.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import time

from . import protocol as p


class CampaignFailure(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class FatalStageFailure(CampaignFailure):
    """The shared worker is gone; no further slot may be dispatched."""


def default_config():
    return json.loads(Path(__file__).with_name("pilot_config.json").read_text())


def write_once(path, value):
    path = Path(path)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    package = Path(__file__).parent
    paths = [q for q in package.rglob("*")
             if q.is_file() and q.suffix in {".py", ".json", ".sbatch"} and "__pycache__" not in q.parts]
    paths.extend(p.dependency_files())
    paths.append(root / "matched_followup_v2" / "native.py")
    simulator_root = root / "datasets" / "dual_objective" / "agent"
    paths.extend(q for q in simulator_root.rglob("*")
                 if q.is_file() and q.suffix in {".py", ".json", ".yaml", ".yml"}
                 and "__pycache__" not in q.parts)
    return {str(q.resolve().relative_to(root)): hashlib.sha256(q.read_bytes()).hexdigest()
            for q in sorted(set(paths))}


def validate_config(config):
    if config.get("schema_version") != "prospective-development-pilot-v1":
        raise ValueError("Not a prospective development configuration")
    if config.get("arms") != list(p.ARMS) or config.get("retries") != 0:
        raise ValueError("Four fixed strategies and zero retries required")
    if config.get("automatic_formal_expansion") is not False:
        raise ValueError("No automatic formal expansion is permitted")
    if config.get("observation_scope") != "action_only_explicit_final" or config.get("threshold") != 50:
        raise ValueError("Frozen observation/threshold mismatch")
    if type(config.get("max_cases")) is not int or not 1 <= config["max_cases"] <= 24:
        raise ValueError("Development pilot must contain at most 24 cases")
    for stage in ("planner", "review", "actor", "judge"):
        cap = config["stage_output_caps"][stage]
        if type(cap) is not int or cap <= 0:
            raise ValueError("Invalid stage cap")
    if config["stage_output_caps"]["planner"] != config["stage_output_caps"]["review"]:
        raise ValueError("Fixed review and targeted planner caps must match")
    if config["review_rounds"] != {"C": 2, "F": 1}:
        raise ValueError("This version freezes C=2 and F=1 review rounds")
    for key in ("max_calls", "max_output_tokens", "max_prompt_bytes"):
        if type(config["limits"][key]) is not int or config["limits"][key] <= 0:
            raise ValueError("Invalid campaign limit: " + key)
    if config["limits"]["max_calls"] > 432 or config["limits"]["max_output_tokens"] > 1376256:
        raise ValueError("This development version cannot exceed its declared call/output envelope")
    for key in ("wall_seconds", "per_call_seconds", "model_startup_seconds"):
        val = config["limits"][key]
        if type(val) not in (int, float) or not math.isfinite(val) or val <= 0:
            raise ValueError("Invalid campaign deadline: " + key)
    for key in ("max_actor_turns", "max_tool_calls", "max_output_tokens_per_turn"):
        value = config["collection_limits"][key]
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid collection cap: " + key)
    if config["collection_limits"]["max_actor_turns"] > 8 or config["collection_limits"]["max_tool_calls"] > 12:
        raise ValueError("Collection caps exceed this development protocol")
    if config["collection_limits"]["max_output_tokens_per_turn"] > 4096:
        raise ValueError("Collection output cap exceeds this development protocol")
    if config["limits"]["wall_seconds"] > 14100:
        raise ValueError("Campaign exceeds the single-allocation wall envelope")
    seconds = config["collection_limits"]["wall_seconds"]
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Invalid collection wall limit")
    p.canonical(config)


def validate_live_receipts(config, preflight, permit, tasks=None):
    """Do not treat an old successful run, filename or backend flag as admission."""
    if not isinstance(preflight, dict) or preflight.get("schema_version") != "prospective-pilot-preflight-v1":
        raise ValueError("Fresh prospective preflight required")
    if not isinstance(permit, dict) or permit.get("scope") != "prospective-development-only":
        raise ValueError("Explicit new-development permit required")
    for receipt in (preflight, permit):
        if receipt.get("config_sha256") != p.digest(config):
            raise ValueError("Receipt configuration mismatch")
    task_hash = preflight.get("task_manifest_sha256")
    if not isinstance(task_hash, str) or len(task_hash) != 64 or permit.get("task_manifest_sha256") != task_hash:
        raise ValueError("Matching frozen task manifests required")
    if tasks is not None and p.digest(tasks) != task_hash:
        raise ValueError("Actual development tasks changed after preflight")
    if preflight.get("code_sha256") != source_hashes():
        raise ValueError("Code changed after preflight")
    for key in ("ready_for_live", "runtime_checked", "tokenizer_capacity_checked", "grammar_checked",
                "asset_inventory_checked", "native_harmony_checked"):
        if preflight.get(key) is not True:
            raise ValueError("Preflight check missing: " + key)
    if permit.get("authorized") is not True or permit.get("max_cases") != config["max_cases"]:
        raise ValueError("New development scope has not been authorized")
    if not isinstance(permit.get("single_use_claim_path"), str) or not Path(permit["single_use_claim_path"]).is_absolute():
        raise ValueError("An absolute single-use campaign claim path is required")
    for key in ("max_calls", "max_output_tokens", "wall_seconds"):
        if permit.get("limits", {}).get(key) != config["limits"][key]:
            raise ValueError("Permit budget mismatch: " + key)
    if set(preflight.get("snapshots", {})) != {"actor", "monitor"}:
        raise ValueError("Both exact local model snapshots required")


def check_asset_inventory(preflight, which, revision):
    """Cheap change check before each load; full SHA belongs to CPU preflight."""
    inventory = preflight.get("asset_inventory", {}).get(which)
    if not isinstance(inventory, dict) or inventory.get("verification") != "fresh_full_sha256":
        raise ValueError("Fresh full asset inventory is absent: " + which)
    path = Path(preflight["snapshots"][which]).absolute()
    if Path(inventory.get("directory", "")).absolute() != path or inventory.get("revision") != revision:
        raise ValueError("Asset directory/revision differs from preflight: " + which)
    files = inventory.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Empty asset inventory: " + which)
    entries = list(path.iterdir())
    if {entry.name for entry in entries} != set(files) or any(not entry.is_file() for entry in entries):
        raise ValueError("Asset file set changed after preflight: " + which)
    for name, expected in files.items():
        if Path(name).name != name:
            raise ValueError("Unsafe asset inventory name")
        item = path / name
        stat = item.stat()
        if (stat.st_size != expected.get("bytes") or stat.st_mtime_ns != expected.get("mtime_ns") or
                str(item.resolve(strict=True)) != expected.get("resolved_path")):
            raise ValueError("Asset changed after preflight: " + which + "/" + name)


class NativeBackendFactory:
    """Lazy bridge to persistent, hard-timeout native workers."""
    execution_mode = "live"

    def __init__(self, config, preflight, permit, tasks=None):
        validate_config(config)
        validate_live_receipts(config, preflight, permit, tasks)
        self.config, self.preflight = deepcopy(config), deepcopy(preflight)

    def __call__(self, which, remaining_seconds):
        check_asset_inventory(self.preflight, which, self.config["revisions"][which])
        from .native_backend import ProcessStageBackend
        seconds = min(remaining_seconds, self.config["limits"]["model_startup_seconds"])
        backend = ProcessStageBackend(which, self.config, self.preflight["snapshots"][which],
                                      permit_live=True, startup_timeout_seconds=seconds)
        backend.start()
        return backend


class _CollectionProxy:
    def __init__(self, campaign, backend, index):
        self.campaign, self.backend, self.index = campaign, backend, index
        self.origin_kind = "natural_actor" if campaign.mode == "live" else "scripted_cpu_fixture"
        self.offline = campaign.mode == "fixture"
        self.turn = 0

    def generate_actor(self, request, timeout_seconds):
        turn = self.turn
        self.turn += 1
        if turn >= self.campaign.config["collection_limits"]["max_actor_turns"]:
            raise CampaignFailure("budget_exhausted", "Per-case collection turn limit")
        cap = self.campaign.config["collection_limits"]["max_output_tokens_per_turn"]
        if request.get("max_output_tokens") != cap:
            raise CampaignFailure("invalid", "Collector output cap differs from frozen cap")
        return self.campaign._call(self.backend, f"c{self.index:04d}.collection.{turn:03d}",
                                   "collection", request, (self.index, "collection"),
                                   timeout_seconds=timeout_seconds)


class DevelopmentCampaign:
    def __init__(self, tasks, output_dir, backend_factory, collector, config=None,
                 mode="fixture", preflight=None, permit=None, clock=time.monotonic):
        self.config = deepcopy(default_config() if config is None else config)
        validate_config(self.config)
        if mode not in {"fixture", "live"}:
            raise ValueError("Explicit fixture/live mode required")
        if getattr(backend_factory, "execution_mode", None) != mode:
            raise ValueError("Factory mode must match campaign mode")
        if mode == "live":
            validate_live_receipts(self.config, preflight, permit, tasks)
        self.tasks = deepcopy(tasks)
        if not isinstance(self.tasks, list) or not 1 <= len(self.tasks) <= self.config["max_cases"]:
            raise ValueError("Invalid development task count")
        seen = set()
        for task in self.tasks:
            for key in ("case_id", "environment", "family_id"):
                if not isinstance(task.get(key), str) or not task[key].strip():
                    raise ValueError("Missing task identity: " + key)
            if task.get("split") != "development" or task["case_id"] in seen:
                raise ValueError("Unique development tasks required")
            seen.add(task["case_id"])
        self.mode, self.clock = mode, clock
        self.factory, self.collector = backend_factory, collector
        self.started = clock()
        self.deadline = self.started + self.config["limits"]["wall_seconds"]
        self.directory = Path(output_dir)
        self.directory.mkdir(parents=True, exist_ok=False)
        if mode == "live":
            write_once(permit["single_use_claim_path"], {
                "config_sha256": p.digest(self.config), "run_directory": str(self.directory.resolve()),
                "retry_allowed": False})
        for name in ("calls", "collection", "phases", "private"):
            (self.directory / name).mkdir()
        self.closed, self.claimed, self.calls = False, set(), 0
        self.pre_inference_rejections = 0
        self.output_charge, self.costs, self.collected = 0, {}, {}
        self.rows, self.prepared, self.intermediate = [], {}, {}
        for task in self.tasks:
            row = {key: task[key] for key in ("case_id", "environment", "family_id", "split")}
            row.update(collection_status="missing", monitoring_admitted=False,
                       collection_failure_reason=None, collection_costs=[], arms={})
            for arm in p.ARMS:
                row["arms"][arm] = {"status": "missing", "score": None, "judgment": None,
                                    "failure_reason": "Collection has not completed", "costs": [],
                                    "followup_performed": False}
            self.rows.append(row)
        write_once(self.directory / "config.json", self.config)
        write_once(self.directory / "manifest.json", {
            "study_kind": "prospective_development_pilot" if mode == "live" else "scripted_cpu_campaign",
            "live_inference": mode == "live", "config_sha256": p.digest(self.config),
            "code_sha256": source_hashes(), "tasks_sha256": p.digest(self.tasks),
            "cases": [{key: row[key] for key in ("case_id", "environment", "family_id", "split")}
                      for row in self.rows], "automatic_formal_expansion": False})
        write_once(self.directory / "private" / "tasks.json", self.tasks)
        if mode == "live":
            write_once(self.directory / "preflight.json", preflight)
            write_once(self.directory / "permit.json", permit)

    def _failure(self, index, arms, status, message):
        for arm in arms:
            self.rows[index]["arms"][arm].update(status=status, score=None, failure_reason=message)

    def _phase(self, name, which, action):
        start = self.clock()
        record = {"phase": name, "model_kind": which, "started_elapsed": start - self.started}
        backend = None
        try:
            remaining = self.deadline - start
            if remaining <= 0:
                raise CampaignFailure("timeout", "Campaign deadline reached before phase")
            backend = self.factory(which, remaining)
            expected = "natural_actor" if self.mode == "live" else "scripted_cpu_fixture"
            if getattr(backend, "origin_kind", None) != expected:
                raise CampaignFailure("invalid", "Backend provenance differs from campaign mode")
            action(backend)
            record["status"] = "completed"
        except Exception as exc:
            record.update(status=getattr(exc, "status", "error"),
                          error=type(exc).__name__ + ": " + str(exc))
            raise
        finally:
            close_exception = None
            if backend is not None:
                try:
                    backend.close()
                except Exception as exc:
                    record["close_error"] = type(exc).__name__ + ": " + str(exc)
                    record["status"] = "error"
                    close_exception = exc
            record["elapsed_seconds"] = max(0.0, self.clock() - start)
            write_once(self.directory / "phases" / (name + ".json"), record)
            if close_exception is not None:
                raise CampaignFailure("error", "Model worker cleanup failed; no next model will load") from close_exception

    def _call(self, backend, slot, stage, content, cost_key, timeout_seconds=None):
        if getattr(backend, "closed", False):
            raise FatalStageFailure("missing", "Shared model worker is closed; remaining calls were not dispatched")
        if slot in self.claimed:
            raise CampaignFailure("error", "Slot already claimed; retry forbidden")
        self.claimed.add(slot)
        directory = self.directory / "calls" / slot
        directory.mkdir(exist_ok=False)
        collection = stage == "collection"
        cap = (self.config["collection_limits"]["max_output_tokens_per_turn"] if collection
               else self.config["stage_output_caps"][stage])
        which = "actor" if stage in {"collection", "actor"} else "monitor"
        request = (deepcopy(content) if collection else {
            "stage": stage, "model": self.config["models"][which],
            "revision": self.config["revisions"][which], "seed": self.config["seed"],
            "max_output_tokens": cap, "content": deepcopy(content)})
        archived = deepcopy(request)
        target = archived if collection else archived.get("content", {})
        if "conversation" in target:
            target["conversation_sha256"] = p.digest(target.pop("conversation"))
        write_once(directory / "request.json", {"request": archived, "request_sha256": p.digest(request)})
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            write_once(directory / "outcome.json", {"status": "timeout", "dispatched": False})
            raise CampaignFailure("timeout", "Campaign deadline reached")
        if self.calls >= self.config["limits"]["max_calls"] or self.output_charge + cap > self.config["limits"]["max_output_tokens"]:
            write_once(directory / "outcome.json", {"status": "budget_exhausted", "dispatched": False})
            raise CampaignFailure("budget_exhausted", "Campaign call/output reservation exhausted")
        if len(p.canonical(request).encode()) > self.config["limits"]["max_prompt_bytes"]:
            write_once(directory / "outcome.json", {"status": "invalid", "dispatched": False})
            raise CampaignFailure("invalid", "Prompt-byte safety limit exceeded, no truncation")
        allowed = min(remaining, self.config["limits"]["per_call_seconds"])
        if timeout_seconds is not None:
            allowed = min(allowed, timeout_seconds)
        if allowed <= 0:
            write_once(directory / "outcome.json", {"status": "timeout", "dispatched": False})
            raise CampaignFailure("timeout", "No per-case time left")
        self.calls += 1
        write_once(directory / "dispatched.json", {"timeout_seconds": allowed, "request_sha256": p.digest(request)})
        start, usage_recorded = self.clock(), False
        try:
            raw = (backend.generate_actor(request, timeout_seconds=allowed) if collection else
                   backend.generate(request, timeout_seconds=allowed))
            write_once(directory / "raw.json", raw)
            for key in ("prompt_tokens", "completion_tokens"):
                if type(raw.get(key)) is not int or raw[key] < 0:
                    raise CampaignFailure("invalid", "Malformed model usage: " + key)
            seconds = raw.get("inference_seconds")
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise CampaignFailure("invalid", "Malformed inference time")
            if raw.get("usage_complete", True) is not True:
                raise CampaignFailure("invalid", "Model usage is incomplete")
            self.costs.setdefault(cost_key, []).append({
                "model": self.config["models"][which], "input_tokens": raw["prompt_tokens"],
                "output_tokens": raw["completion_tokens"], "inference_seconds": seconds,
                "usage_complete": True, "usage_mode": raw.get("usage_mode", "native_model")})
            usage_recorded = True
            self.output_charge += raw["completion_tokens"]
            if raw["completion_tokens"] > cap:
                raise CampaignFailure("invalid", "Output exceeded frozen cap")
            if self.clock() >= self.deadline or self.clock() - start > allowed:
                raise CampaignFailure("timeout", "Late backend answer excluded")
            if raw.get("finish_reason") != "stop":
                raise CampaignFailure("invalid", "Truncated or unsuccessful model output")
            write_once(directory / "outcome.json", {"status": "returned", "dispatched": True})
            return raw
        except Exception as exc:
            if getattr(exc, "dispatched", None) is False:
                # Native exact-token admission rejected before model inference.
                # The claimed slot remains unusable, but zero model tokens are
                # known here rather than an imputation after a failed generation.
                self.calls -= 1
                self.pre_inference_rejections += 1
                self.costs.setdefault(cost_key, []).append({
                    "model": self.config["models"][which], "input_tokens": 0, "output_tokens": 0,
                    "inference_seconds": 0.0, "usage_complete": True,
                    "usage_mode": "known_rejection_before_model_inference"})
                write_once(directory / "outcome.json", {"status": "invalid", "dispatched": False,
                    "worker_request_sent": True, "error": type(exc).__name__ + ": " + str(exc)})
                raise CampaignFailure("invalid", str(exc)) from exc
            if not usage_recorded:
                self.output_charge += cap
                self.costs.setdefault(cost_key, []).append({
                    "model": self.config["models"][which], "input_tokens": 0, "output_tokens": 0,
                    "inference_seconds": max(0.0, self.clock() - start), "usage_complete": False,
                    "usage_note": "Unknown failed-call usage, not verified zero."})
            status = getattr(exc, "status", "timeout" if isinstance(exc, TimeoutError) else "error")
            write_once(directory / "outcome.json", {"status": status, "dispatched": True,
                                                     "error": type(exc).__name__ + ": " + str(exc)})
            if getattr(backend, "closed", False):
                raise FatalStageFailure(status, "Shared model worker closed after " + type(exc).__name__ +
                                        "; remaining calls were not dispatched: " + str(exc)) from exc
            raise CampaignFailure(status, str(exc)) from exc

    def _collect(self, backend):
        for index, task in enumerate(self.tasks):
            row = self.rows[index]
            try:
                remaining = self.deadline - self.clock()
                if remaining <= 0:
                    raise CampaignFailure("timeout", "Campaign deadline before collection")
                limits = deepcopy(self.config["collection_limits"])
                limits["wall_seconds"] = min(limits["wall_seconds"], remaining)
                result = self.collector(task, _CollectionProxy(self, backend, index),
                                        self.directory / "collection" / f"c{index:04d}",
                                        limits=limits, clock=self.clock)
                self.collected[index] = result
                write_once(self.directory / "private" / f"c{index:04d}.collection.json", result)
                row["collection_status"] = result.get("status", "invalid")
                if getattr(backend, "closed", False):
                    raise FatalStageFailure("timeout" if result.get("status") == "timeout" else "error",
                                            "Shared collection worker is closed; remaining calls were not dispatched")
                if row["collection_status"] != "completed":
                    raise CampaignFailure(row["collection_status"], "Collection did not complete: " + str(result.get("stop_reason")))
                if result.get("origin_kind") != ("natural_actor" if self.mode == "live" else "scripted_cpu_fixture"):
                    raise CampaignFailure("invalid", "Collection provenance mismatch")
                case = result.get("monitor_case")
                if not isinstance(case, dict):
                    raise CampaignFailure("invalid", "Collection has no complete monitor input")
                case = p.validate_case(case)
                if any(case[key] != task[key] for key in ("case_id", "environment", "family_id")):
                    raise CampaignFailure("invalid", "Collection identity mismatch")
                if result.get("reference", {}).get("status") != "resolved":
                    raise CampaignFailure("reference_unknown", "Unresolved reference before monitoring")
                self.prepared[index] = case
                self.intermediate[index] = {arm: {"reviews": [], "selected": None, "qa": None} for arm in p.ARMS}
                row["monitoring_admitted"] = True
                for arm in p.ARMS:
                    row["arms"][arm].update(status="pending", failure_reason=None)
            except Exception as exc:
                status = getattr(exc, "status", "error")
                row["collection_failure_reason"] = str(exc)
                if row["collection_status"] == "missing":
                    row["collection_status"] = status
                self._failure(index, p.ARMS, "missing", "Not monitored: " + str(exc))
                if isinstance(exc, FatalStageFailure):
                    raise
            finally:
                row["collection_costs"] = deepcopy(self.costs.get((index, "collection"), []))
                write_once(self.directory / "collection" / f"c{index:04d}.admission.json", {
                    key: row[key] for key in ("case_id", "collection_status", "collection_failure_reason", "monitoring_admitted")})

    def _plan_and_review(self, backend):
        for index, case in self.prepared.items():
            order = ("C", "F", "T")
            order = order[index % 3:] + order[:index % 3]
            for arm in order:
                data = self.intermediate[index][arm]
                try:
                    if arm in {"C", "F"}:
                        for number in range(self.config["review_rounds"][arm]):
                            raw = self._call(backend, f"c{index:04d}.{arm}.review{number}", "review",
                                             {"prompt": p.review_prompt(case, data["reviews"] or None)}, (index, arm))
                            data["reviews"].append(p.review(raw["text"], case))
                    else:
                        raw = self._call(backend, f"c{index:04d}.T.planner", "planner",
                                         {"prompt": p.planner_prompt(case)}, (index, arm))
                        data["selected"] = p.selection(raw["text"], case)
                except Exception as exc:
                    self._failure(index, (arm,), getattr(exc, "status", "invalid"), str(exc))
                    if isinstance(exc, FatalStageFailure):
                        raise

    def _followups(self, backend):
        for index, case in self.prepared.items():
            order = ("F", "T") if index % 2 == 0 else ("T", "F")
            for arm in order:
                if self.rows[index]["arms"][arm]["status"] != "pending":
                    continue
                data = self.intermediate[index][arm]
                try:
                    question = p.FIXED_QUESTION if arm == "F" else p.targeted_question(case, data["selected"])
                    if question is None:
                        continue
                    raw = self._call(backend, f"c{index:04d}.{arm}.actor", "actor",
                                     p.actor_request(case, question), (index, arm))
                    if raw.get("channel") != "final" or raw.get("tool_calls") or not raw.get("text", "").strip():
                        raise ValueError("Follow-up requires a final answer with no tool calls")
                    data["qa"] = {"question": question, "answer": raw["text"]}
                    self.rows[index]["arms"][arm]["followup_performed"] = True
                except Exception as exc:
                    self._failure(index, (arm,), getattr(exc, "status", "invalid"), str(exc))
                    if isinstance(exc, FatalStageFailure):
                        raise

    def _judge(self, backend):
        for index, case in self.prepared.items():
            order = p.ARMS[index % 4:] + p.ARMS[:index % 4]
            for arm in order:
                if self.rows[index]["arms"][arm]["status"] != "pending":
                    continue
                data = self.intermediate[index][arm]
                try:
                    prompt = p.judge_prompt(case, arm, reviews=data["reviews"], selected=data["selected"], qa=data["qa"])
                    raw = self._call(backend, f"c{index:04d}.{arm}.judge", "judge", {"prompt": prompt}, (index, arm))
                    judged = p.judgment(raw["text"], case)
                    self.rows[index]["arms"][arm].update(
                        status="unknown" if judged["score"] is None else "ok", score=judged["score"],
                        judgment=judged, failure_reason=None)
                except Exception as exc:
                    self._failure(index, (arm,), getattr(exc, "status", "invalid"), str(exc))
                    if isinstance(exc, FatalStageFailure):
                        raise

    def run(self):
        if self.closed:
            raise ValueError("Campaign is single-use and already closed")
        self.closed = True
        close_reason = "completed_bounded_development_campaign"
        try:
            self._phase("01_collection", "actor", self._collect)
            if self.prepared:
                self._phase("02_plan_review", "monitor", self._plan_and_review)
                self._phase("03_followups", "actor", self._followups)
                self._phase("04_judgments", "monitor", self._judge)
        except Exception as exc:
            close_reason = type(exc).__name__ + ": " + str(exc)
            status = getattr(exc, "status", "error")
            unattempted_status = "missing" if isinstance(exc, FatalStageFailure) else status
            for index, row in enumerate(self.rows):
                if row["collection_status"] == "missing":
                    row["collection_status"] = unattempted_status
                    row["collection_failure_reason"] = close_reason
                for arm in p.ARMS:
                    if row["arms"][arm]["status"] == "pending":
                        self._failure(index, (arm,), unattempted_status, close_reason)
        finally:
            for index, row in enumerate(self.rows):
                for arm in p.ARMS:
                    row["arms"][arm]["costs"] = deepcopy(self.costs.get((index, arm), []))
                write_once(self.directory / f"c{index:04d}.result.json", row)
            summary = {
                "study_kind": "prospective_development_pilot" if self.mode == "live" else "scripted_cpu_campaign",
                "live_inference": self.mode == "live", "formal_test_cases": 0,
                "cases": self.rows, "all_case_denominators_retained": len(self.rows) == len(self.tasks),
                "monitoring_admitted_count": len(self.prepared), "dispatched_calls": self.calls,
                "known_pre_inference_rejections": self.pre_inference_rejections,
                "output_tokens_or_failed_reserve": self.output_charge,
                "elapsed_seconds": max(0.0, self.clock() - self.started), "close_reason": close_reason,
                "automatic_formal_expansion": False}
            write_once(self.directory / "summary.json", summary)
            write_once(self.directory / "closed.json", {"closed": True, "retry_allowed": False,
                                                         "close_reason": close_reason})
        return summary


def run_campaign(tasks, output_dir, backend_factory, collector, config=None, **kwargs):
    return DevelopmentCampaign(tasks, output_dir, backend_factory, collector, config, **kwargs).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--permit", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    config, tasks, preflight, permit = [json.loads(Path(value).read_text()) for value in
                                        (args.config, args.tasks, args.preflight, args.permit)]
    if isinstance(tasks, dict):
        tasks = tasks["tasks"]
    from .collection import collect_case
    factory = NativeBackendFactory(config, preflight, permit, tasks)
    result = run_campaign(tasks, args.run, factory, collect_case, config, mode="live",
                          preflight=preflight, permit=permit)
    print(json.dumps({key: result[key] for key in ("study_kind", "dispatched_calls", "monitoring_admitted_count", "close_reason")}, indent=2))
    if result["monitoring_admitted_count"] == 0 or result["close_reason"] != "completed_bounded_development_campaign":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
