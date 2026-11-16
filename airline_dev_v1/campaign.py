"""Replay existing airline histories. This entry point has no collection stage."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from prospective_monitoring.campaign import DevelopmentCampaign, FatalStageFailure, write_once
from . import protocol as p
from .prepare import load_bundle, read, sha


def validate_receipts(bundle, preflight, permit):
    cfg, cases, manifest = load_bundle(bundle)
    if preflight.get("schema_version") != "airline-replay-preflight-v1":
        raise ValueError("Fresh airline replay admission required; collection permits do not apply")
    if permit.get("scope") != cfg["scope"] or permit.get("schema_version") != "airline-replay-permit-v1":
        raise ValueError("A separate airline comparison permit is required")
    for obj in (preflight, permit):
        if obj.get("bundle_manifest_sha256") != sha(Path(bundle) / "manifest.json"):
            raise ValueError("Receipt does not bind this prepared cohort and code")
    if permit.get("preflight_sha256") != p.digest(preflight):
        raise ValueError("Permit does not bind this CPU admission")
    if permit.get("authorized_limits") != cfg["limits"] or permit.get("resource_envelope") != cfg["resource_envelope"]:
        raise ValueError("Authorized budget differs from frozen configuration")
    if not isinstance(permit.get("user_authorization"), str) or not permit["user_authorization"].strip():
        raise ValueError("Record the user's authorization for the new comparison")
    if permit.get("new_environment_episodes") != 0 or permit.get("environment_tool_calls") != 0:
        raise ValueError("Only tool-disabled follow-up answers are allowed")
    claim = Path(permit["single_use_claim_path"])
    if not claim.is_absolute() or claim.exists():
        raise ValueError("An unused absolute single-use claim path is required")
    for key in ("ready_for_live", "runtime_checked", "tokenizer_capacity_checked", "grammar_checked", "asset_hashes_checked"):
        if preflight.get(key) is not True:
            raise ValueError("Incomplete admission: " + key)
    completed = datetime.fromisoformat(preflight["completed_at_utc"])
    age = (datetime.now(timezone.utc) - completed).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError("CPU admission is older than 24 hours or dated in the future")
    return cfg, cases, manifest


class ReplayCampaign(DevelopmentCampaign):
    def __init__(self, bundle, output_dir, backend_factory, *, mode="fixture", preflight=None, permit=None, clock=time.monotonic):
        cfg, cases, manifest = load_bundle(bundle)
        if mode not in {"fixture", "live"} or getattr(backend_factory, "execution_mode", None) != mode:
            raise ValueError("Explicit matching backend mode required")
        if mode == "live":
            validate_receipts(bundle, preflight, permit)
            if os.environ.get("SLURM_JOB_ACCOUNT") != cfg["resource_envelope"]["account"] or not os.environ.get("SLURM_JOB_ID"):
                raise ValueError("Run only in the authorized cluster allocation")
        self.config, self.mode, self.clock = cfg, mode, clock
        self.factory = backend_factory
        self.started = clock()
        self.deadline = self.started + cfg["limits"]["wall_seconds"]
        if mode == "live":
            allocation_start = float(os.environ["TGF_ALLOCATION_START"])
            self.deadline -= max(0, time.time() - allocation_start)
        self.directory = Path(output_dir)
        self.directory.mkdir(parents=True, exist_ok=False)
        if mode == "live":
            write_once(permit["single_use_claim_path"], {"bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"),
                       "job_id": os.environ["SLURM_JOB_ID"], "run_directory": str(self.directory.resolve()), "retry_allowed": False})
        for name in ("calls", "phases", "private", "progress"):
            (self.directory / name).mkdir()
        self.closed, self.claimed, self.calls = False, set(), 0
        self.pre_inference_rejections, self.output_charge, self.costs = 0, 0, {}
        self.prepared = {i: c for i, c in enumerate(cases)}
        self.intermediate = {i: {a: {"reviews": [], "selected": None, "qa": None} for a in p.ARMS} for i in self.prepared}
        self.rows = [{"case_id": c["case_id"], "environment": "airline", "family_id": c["family_id"],
                      "arms": {a: {"status": "pending", "score": None, "judgment": None,
                                     "failure_reason": None, "costs": [], "followup_performed": False} for a in p.ARMS}}
                     for c in cases]
        write_once(self.directory / "manifest.json", {"schema_version": "airline-replay-run-v1", "mode": mode,
            "bundle_manifest_sha256": sha(Path(bundle) / "manifest.json"), "bundle_manifest": manifest,
            "live_inference": mode == "live", "job_id": os.environ.get("SLURM_JOB_ID") if mode == "live" else None,
            "new_environment_episodes": 0, "environment_tool_calls": 0, "formal_claim_permitted": False})
        if mode == "live":
            write_once(self.directory / "preflight.json", preflight)
            write_once(self.directory / "permit.json", permit)

    def _collect(self, backend):
        raise PermissionError("This campaign cannot collect or rerun an environment")

    def _call(self, backend, slot, stage, content, cost_key, timeout_seconds=None):
        if stage not in {"planner", "review", "judge", "actor"}:
            raise PermissionError("Collection and environment tools are unavailable")
        return super()._call(backend, slot, stage, content, cost_key, timeout_seconds)

    def _checkpoint(self, name):
        write_once(self.directory / "progress" / (name + ".json"), {"cases": self.rows,
            "intermediate": self.intermediate, "dispatched_calls": self.calls,
            "costs": [{"index": k[0], "arm": k[1], "entries": v} for k, v in self.costs.items()]})

    def _plan_and_review(self, backend):
        for i, case in self.prepared.items():
            order = ("C", "F", "T")
            for arm in order[i % 3:] + order[:i % 3]:
                data = self.intermediate[i][arm]
                try:
                    if arm in {"C", "F"}:
                        for n in range(self.config["review_rounds"][arm]):
                            raw = self._call(backend, f"c{i:04d}.{arm}.review{n}", "review",
                                             {"prompt": p.review_prompt(case, data["reviews"] or None)}, (i, arm))
                            data["reviews"].append(p.review(raw["text"], case))
                    else:
                        raw = self._call(backend, f"c{i:04d}.T.planner", "planner", {"prompt": p.planner_prompt(case)}, (i, arm))
                        data["selected"] = p.selection(raw["text"], case)
                except Exception as exc:
                    self._failure(i, (arm,), getattr(exc, "status", "invalid"), str(exc))
                    if isinstance(exc, FatalStageFailure):
                        raise
            self._checkpoint(f"plan_{i:04d}")

    def _judge(self, backend):
        for i, case in self.prepared.items():
            for arm in p.ARMS[i % 4:] + p.ARMS[:i % 4]:
                if self.rows[i]["arms"][arm]["status"] != "pending":
                    continue
                data = self.intermediate[i][arm]
                try:
                    prompt = p.judge_prompt(case, arm, reviews=data["reviews"], selected=data["selected"], qa=data["qa"])
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
            raise ValueError("Campaign is single-use; retry forbidden")
        self.closed = True
        reason = "completed_bounded_airline_comparison"
        try:
            self._phase("01_plan_review", "monitor", self._plan_and_review)
            self._checkpoint("01_plan_review_complete")
            self._phase("02_followups", "actor", self._followups)
            self._checkpoint("02_followups_complete")
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
            summary = {"study_kind": "airline_replay_development" if self.mode == "live" else "scripted_cpu_fixture",
                       "live_inference": self.mode == "live", "cases": self.rows,
                       "dispatched_calls": self.calls, "known_pre_inference_rejections": self.pre_inference_rejections,
                       "output_tokens_or_failed_reserve": self.output_charge,
                       "elapsed_seconds": max(0, self.clock() - self.started), "close_reason": reason,
                       "formal_claim_permitted": False, "new_environment_episodes": 0, "environment_tool_calls": 0}
            write_once(self.directory / "summary.json", summary)
            write_once(self.directory / "closed.json", {"closed": True, "retry_allowed": False, "close_reason": reason})
            write_once(self.directory / "file_hashes.json", {str(f.relative_to(self.directory)): sha(f)
                       for f in sorted(self.directory.rglob("*")) if f.is_file()})
        return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "output", "preflight", "permit"):
        ap.add_argument("--" + name, required=True, type=Path)
    args = ap.parse_args()
    from .native_backend import Factory
    preflight, permit = read(args.preflight), read(args.permit)
    factory = Factory(args.bundle, preflight, permit)
    result = ReplayCampaign(args.bundle, args.output, factory, mode="live", preflight=preflight, permit=permit).run()
    print(json.dumps({k: result[k] for k in ("dispatched_calls", "elapsed_seconds", "close_reason")}))
    if result["close_reason"] != "completed_bounded_airline_comparison":
        raise SystemExit(1)
