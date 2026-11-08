"""One allocation, three shared model phases, 48 paired replicas; never collect."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from prospective_monitoring.campaign import DevelopmentCampaign, FatalStageFailure, CampaignFailure, write_once
from . import protocol as p
from .prepare import load_bundle, read, sha


def validate_receipts(bundle, preflight, permit):
    cfg, cases, manifest = load_bundle(bundle)
    if permit.get("schema_version") != "anchored-question-permit-v1" or permit.get("scope") != cfg["scope"]:
        raise ValueError("New-scope permit required; old permits cannot authorize this run")
    expected = sha(Path(bundle) / "manifest.json")
    if permit.get("bundle_manifest_sha256") != expected or preflight.get("bundle_manifest_sha256") != expected:
        raise ValueError("Receipt/bundle mismatch")
    if permit.get("authorized_limits") != cfg["limits"] or permit.get("resource_envelope") != cfg["resource_envelope"]:
        raise ValueError("Resource authorization changed")
    if permit.get("new_environment_episodes") != 0 or permit.get("environment_tool_calls") != 0:
        raise ValueError("Only tool-disabled followups authorized")
    if permit.get("authorization_sha256") != p.digest(read(Path(bundle) / "authorization.json")):
        raise ValueError("Authorization no longer bound")
    claim = Path(permit["single_use_claim_path"])
    if not claim.is_absolute() or claim.exists():
        raise ValueError("Unused absolute execution claim required")
    for key in ("ready_for_live", "runtime_checked", "tokenizer_capacity_checked", "grammar_checked", "asset_hashes_checked"):
        if preflight.get(key) is not True:
            raise ValueError("Admission incomplete: " + key)
    if preflight.get("schema_version") != "anchored-question-preflight-v1":
        raise ValueError("Fresh admission required")
    if preflight.get("job_id") != os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Admission must occur inside this same sole GPU allocation")
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(preflight["completed_at_utc"])).total_seconds()
    if not 0 <= age <= 7200:
        raise ValueError("Stale admission")
    return cfg, cases, manifest


class Campaign(DevelopmentCampaign):
    def __init__(self, bundle, output_dir, backend_factory, *, mode="fixture", preflight=None, permit=None, clock=time.monotonic):
        cfg, cases, manifest = load_bundle(bundle)
        if mode not in {"fixture", "live"} or getattr(backend_factory, "execution_mode", None) != mode:
            raise ValueError("Explicit matching factory mode required")
        if mode == "live":
            validate_receipts(bundle, preflight, permit)
            if os.environ.get("SLURM_JOB_ACCOUNT") != cfg["resource_envelope"]["account"] or not os.environ.get("SLURM_JOB_ID"):
                raise ValueError("Authorized allocation required")
        self.config, self.mode, self.clock, self.factory = cfg, mode, clock, backend_factory
        self.started = clock()
        self.allocation_elapsed_before_campaign = max(0, time.time() - float(os.environ["TGF_ALLOCATION_START"])) if mode == "live" else 0
        self.deadline = self.started + cfg["limits"]["wall_seconds"] - self.allocation_elapsed_before_campaign
        self.directory = Path(output_dir)
        self.directory.mkdir(parents=True, exist_ok=False)
        if mode == "live":
            write_once(permit["single_use_claim_path"], {"bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"),
                "job_id": os.environ["SLURM_JOB_ID"], "retry_allowed": False})
        for name in ("calls", "phases", "private", "progress"):
            (self.directory / name).mkdir()
        self.closed, self.claimed, self.calls = False, set(), 0
        self.pre_inference_rejections, self.output_charge, self.costs = 0, 0, {}
        self.prepared, self.rows = {}, []
        # Each original case has two prespecified replicas. Keep the original ID;
        # seed is a separate factor, not an invented independent subject.
        for seed in p.SEEDS:
            for original_index, case in enumerate(cases):
                i = len(self.rows)
                self.prepared[i] = case
                self.rows.append({"case_id": case["case_id"], "original_index": original_index, "seed": seed,
                    "environment": "airline", "family_id": case["family_id"], "anchor": p.anchor(case),
                    "arms": {a: {"status": "pending", "score": None, "judgment": None, "failure_reason": None,
                                 "costs": [], "followup_performed": False} for a in p.ARMS}})
        self.intermediate = {i: {a: {"notes": [], "qa": None} for a in p.ARMS} for i in self.prepared}
        write_once(self.directory / "manifest.json", {"schema_version": "anchored-question-run-v1", "mode": mode,
            "bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"), "bundle_manifest": manifest,
            "live_inference": mode == "live", "job_id": os.environ.get("SLURM_JOB_ID") if mode == "live" else None,
            "expected_final_positions": 144, "new_environment_episodes": 0, "environment_tool_calls": 0,
            "formal_claim_permitted": False})
        if mode == "live":
            write_once(self.directory / "preflight.json", preflight)
            write_once(self.directory / "permit.json", permit)

    def _call(self, backend, slot, stage, content, cost_key, timeout_seconds=None):
        if stage not in {"review", "actor", "judge"}:
            raise PermissionError("No collection, planner or environment tools")
        seed = self.rows[cost_key[0]]["seed"]
        if seed not in p.SEEDS:
            raise ValueError("Unplanned replicate")
        # Calls are strictly serial. The inherited budget/logger reads this seed
        # into the archived request and the actual native sampling request.
        original = self.config["seed"]
        try:
            self.config["seed"] = seed
            return super()._call(backend, slot, stage, content, cost_key, timeout_seconds)
        finally:
            self.config["seed"] = original

    def _collect(self, backend):
        raise PermissionError("Collection forbidden")

    def _phase(self, name, which, action):
        start, backend = self.clock(), None
        record = {"phase": name, "model_kind": which, "started_elapsed": start - self.started}
        try:
            remaining = self.deadline - start
            if remaining <= 0:
                raise CampaignFailure("timeout", "Allocation deadline before model phase")
            backend = self.factory(which, remaining)
            ready = self.clock()
            record["startup_seconds"] = ready - start
            expected = "natural_actor" if self.mode == "live" else "scripted_cpu_fixture"
            if getattr(backend, "origin_kind", None) != expected:
                raise CampaignFailure("invalid", "Backend provenance mismatch")
            action(backend)
            record.update(status="completed", inference_and_bookkeeping_seconds=self.clock() - ready)
        except Exception as exc:
            record.update(status=getattr(exc, "status", "error"), error=type(exc).__name__ + ": " + str(exc))
            raise
        finally:
            closing, cleanup_error = self.clock(), None
            if backend is not None:
                try:
                    backend.close()
                except Exception as exc:
                    record.update(status="error", close_error=str(exc))
                    cleanup_error = exc
            record.update(cleanup_seconds=self.clock() - closing, elapsed_seconds=self.clock() - start)
            write_once(self.directory / "phases" / (name + ".json"), record)
            if cleanup_error is not None:
                raise CampaignFailure("error", "Cleanup failed; no next model load") from cleanup_error

    def _checkpoint(self, name):
        write_once(self.directory / "progress" / (name + ".json"), {
            "cases": self.rows, "intermediate": self.intermediate, "dispatched_calls": self.calls,
            "costs": [{"index": k[0], "arm": k[1], "entries": v} for k, v in self.costs.items()]})

    def _reviews(self, backend):
        for i, case in self.prepared.items():
            try:
                raw = self._call(backend, f"c{i:04d}.A.review", "review", {"prompt": p.review_prompt(case)}, (i, "A"))
                self.intermediate[i]["A"]["notes"] = [p.review(raw["text"], case)]
            except Exception as exc:
                self._failure(i, ("A",), getattr(exc, "status", "invalid"), str(exc))
                if isinstance(exc, FatalStageFailure):
                    raise
            self._checkpoint(f"review_{i:04d}")

    def _followups(self, backend):
        for i, case in self.prepared.items():
            # Counterbalance order across original cases and across replicates.
            parity = self.rows[i]["original_index"] + p.SEEDS.index(self.rows[i]["seed"])
            for arm in (("B", "C") if parity % 2 == 0 else ("C", "B")):
                try:
                    question = p.question(case, arm)
                    raw = self._call(backend, f"c{i:04d}.{arm}.actor", "actor", p.actor_request(case, question), (i, arm))
                    if raw.get("channel") != "final" or raw.get("tool_calls") or not raw.get("text", "").strip():
                        raise ValueError("Followup needs one final tool-free answer")
                    self.intermediate[i][arm]["qa"] = {"question": question, "answer": raw["text"]}
                    self.rows[i]["arms"][arm]["followup_performed"] = True
                except Exception as exc:
                    self._failure(i, (arm,), getattr(exc, "status", "invalid"), str(exc))
                    if isinstance(exc, FatalStageFailure):
                        raise
            self._checkpoint(f"followup_{i:04d}")

    def _judge(self, backend):
        for i, case in self.prepared.items():
            shift = (self.rows[i]["original_index"] + p.SEEDS.index(self.rows[i]["seed"])) % 3
            for arm in p.ARMS[shift:] + p.ARMS[:shift]:
                if self.rows[i]["arms"][arm]["status"] != "pending":
                    continue
                data = self.intermediate[i][arm]
                try:
                    prompt = p.judge_prompt(case, arm, notes=data["notes"], qa=data["qa"])
                    raw = self._call(backend, f"c{i:04d}.{arm}.judge", "judge", {"prompt": prompt}, (i, arm))
                    judged = p.judgment(raw["text"], case)
                    self.rows[i]["arms"][arm].update(status="unknown" if judged["score"] is None else "ok",
                        score=judged["score"], judgment=judged, failure_reason=None)
                except Exception as exc:
                    self._failure(i, (arm,), getattr(exc, "status", "invalid"), str(exc))
                    if isinstance(exc, FatalStageFailure):
                        raise
            self._checkpoint(f"judge_{i:04d}")

    def run(self):
        if self.closed:
            raise ValueError("Single use; rerun forbidden")
        self.closed = True
        reason = "completed_bounded_anchored_question_diagnostic"
        try:
            self._phase("01_reviews", "monitor", self._reviews)
            self._phase("02_followups", "actor", self._followups)
            self._phase("03_judgments", "monitor", self._judge)
        except Exception as exc:
            reason = type(exc).__name__ + ": " + str(exc)
        finally:
            for i, row in enumerate(self.rows):
                for arm, output in row["arms"].items():
                    if output["status"] == "pending":
                        self._failure(i, (arm,), "missing", "Not reached: " + reason)
                    output["costs"] = deepcopy(self.costs.get((i, arm), []))
                write_once(self.directory / f"c{i:04d}.result.json", row)
            write_once(self.directory / "private/intermediate.json", self.intermediate)
            summary = {"study_kind": "anchored_question_development" if self.mode == "live" else "scripted_cpu_fixture",
                "live_inference": self.mode == "live", "cases": self.rows, "dispatched_calls": self.calls,
                "known_pre_inference_rejections": self.pre_inference_rejections,
                "output_tokens_or_failed_reserve": self.output_charge,
                "elapsed_seconds": max(0, self.clock() - self.started),
                "pre_campaign_allocation_seconds": self.allocation_elapsed_before_campaign,
                "allocation_elapsed_seconds": max(0, self.clock() - self.started) + self.allocation_elapsed_before_campaign,
                "close_reason": reason, "formal_claim_permitted": False,
                "new_environment_episodes": 0, "environment_tool_calls": 0}
            write_once(self.directory / "summary.json", summary)
            write_once(self.directory / "closed.json", {"closed": True, "retry_allowed": False, "close_reason": reason})
            write_once(self.directory / "file_hashes.json", {str(f.relative_to(self.directory)): sha(f)
                for f in sorted(self.directory.rglob("*")) if f.is_file()})
        return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "output", "preflight", "permit"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    from .native_backend import Factory
    preflight, permit = read(args.preflight), read(args.permit)
    factory = Factory(args.bundle, preflight, permit)
    result = Campaign(args.bundle, args.output, factory, mode="live", preflight=preflight, permit=permit).run()
    print(p.canonical({k: result[k] for k in ("dispatched_calls", "allocation_elapsed_seconds", "close_reason")}))
    if result["close_reason"] != "completed_bounded_anchored_question_diagnostic":
        raise SystemExit(1)
