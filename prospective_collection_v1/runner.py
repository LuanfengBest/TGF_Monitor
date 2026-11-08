"""Durable no-retry execution adapter for the immutable November 5 preparation."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time
import traceback

from prospective_data_v2.prepare import CollectionBudget, validate_manifest, verify_sources
from prospective_data_v2.specs import CASE_LIMITS, COLLECTION_LIMITS, digest
from prospective_data_v2.fixtures import prepare_environment
from prospective_monitoring.collection import collect_case
from prospective_monitoring.native_backend import PINNED, PINNED_RUNTIME, ProcessStageBackend

ROOT = Path(__file__).resolve().parents[1]
DEP = ROOT / "project/new_data_collection_2026-11-05/deployment"
PREP = ROOT / "project/new_data_preparation_2026-11-05/frozen_specifications"


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def inputs():
    permit = load(DEP / "execution_permit.json")
    if (permit.get("authorized") is not True or permit["limits"] != COLLECTION_LIMITS
            or permit["automatic_expansion"] is not False or permit["monitor_calls"] != 0):
        raise ValueError("Invalid actor-only authorization")
    for name, expected in permit["files"].items():
        path = ROOT / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError("Frozen execution input changed: " + name)
    verify_sources(load(PREP / "source_hashes.json"))
    manifest = validate_manifest(load(PREP / "manifest_PRIVATE.json"))
    if digest(manifest) != permit["manifest_sha256"]:
        raise ValueError("Manifest binding mismatch")
    return permit, manifest, load(DEP / "runtime_location.json")


def config():
    return {"models": {"actor": PINNED["actor"]["model"]},
            "revisions": {"actor": PINNED["actor"]["revision"]},
            "runtime": PINNED_RUNTIME, "seed": 20261105, "temperature": 0.6,
            "native": {"actor": {"context": 131072}}}


class CampaignDeadline(BaseException):
    pass


class Guard:
    def __init__(self, backend, tasks, output, started_at, clock=time.monotonic):
        if backend.origin_kind != "natural_actor":
            raise ValueError("Live adapter cannot relabel a scripted backend")
        self.backend, self.output, self.clock = backend, Path(output), clock
        self.origin_kind = "natural_actor"
        self.budget = CollectionBudget([t["case_id"] for t in tasks], started_at)
        self.deadline = started_at + COLLECTION_LIMITS["campaign_wall_seconds_including_startup"]
        self.case_id = None

    def claim_case(self, task):
        self.budget.claim_case(task["case_id"], self.clock())
        save(self.output / "claims" / (task["case_id"] + ".json"),
             {"case_id": task["case_id"], "task_sha256": digest(task), "attempt": 1,
              "claimed_at_monotonic": self.clock(), "retry_allowed": False})
        self.case_id = task["case_id"]

    def generate_actor(self, request, timeout_seconds):
        remaining = min(timeout_seconds, self.deadline - self.clock())
        if remaining <= 0:
            raise TimeoutError("Global campaign deadline reached; no dispatch")
        self.budget.claim_call(self.case_id, request["turn_index"], request["max_output_tokens"], self.clock())
        save(self.output / "calls" / f"{self.case_id}-{request['turn_index']:02d}.json",
             {"case_id": self.case_id, "turn_index": request["turn_index"],
              "request_sha256": digest(request), "requested_output_tokens": request["max_output_tokens"],
              "timeout_seconds": remaining, "reserved_before_dispatch": True,
              "retry_allowed": False})
        return self.backend.generate_actor(request, timeout_seconds=remaining)


def cheap_asset_binding(admission, runtime):
    if admission.get("ready_for_live") is not True or admission["model_calls"] != 0:
        raise ValueError("Missing successful CPU admission")
    if admission["permit_sha256"] != sha(DEP / "execution_permit.json"):
        raise ValueError("CPU admission belongs to a different execution permit")
    for row in admission["verified_files"]:
        p = Path(row["path"])
        s = p.stat()
        if (s.st_size != row["bytes"] or s.st_mtime_ns != row["mtime_ns"]
                or str(p.resolve()) != row["resolved_path"]):
            raise ValueError("Runtime asset changed after full byte verification")
    if admission["runtime_location"] != runtime:
        raise ValueError("Asset paths changed after CPU admission")


def run():
    permit, manifest, runtime = inputs()
    admission = load(ROOT / "admission/preflight.json")
    cheap_asset_binding(admission, runtime)
    allocation = float(os.environ["TGF_ALLOCATION_START"])
    elapsed = time.time() - allocation
    if not math.isfinite(elapsed) or not 0 <= elapsed < 7200 or not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Valid scheduler start timestamp and allocation required")
    started = time.monotonic() - elapsed
    out = ROOT / "campaign"
    out.mkdir(exist_ok=False)
    save(out / "execution_claim.json", {"permit_sha256": sha(DEP / "execution_permit.json"),
         "preflight_sha256": sha(ROOT / "admission/preflight.json"),
         "slurm_job_id": os.environ["SLURM_JOB_ID"], "allocation_start_unix": allocation,
         "limits": COLLECTION_LIMITS, "retry_allowed": False})
    backend = ProcessStageBackend("actor", config(), runtime["snapshot"], permit_live=True,
                                  startup_timeout_seconds=min(900, 7200 - elapsed - 10))
    guard = Guard(backend, manifest["tasks"], out, started)
    rows, error, stop = [], None, "all_fixed_slots_processed"

    def deadline(signum, frame):
        raise CampaignDeadline("Allocation deadline reached; no restart")

    signal.signal(signal.SIGALRM, deadline)
    signal.signal(signal.SIGTERM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(1, 7200 - elapsed - 10))
    try:
        backend.start()
        save(out / "model_ready.json", {"elapsed_including_startup": time.monotonic() - started,
                                      "model": PINNED["actor"], "runtime": PINNED_RUNTIME})
        for task in manifest["tasks"]:
            if backend.closed or time.monotonic() >= guard.deadline - 10:
                stop = "backend_closed_or_global_deadline"
                break
            guard.claim_case(task)
            result = collect_case(task, guard, out / "cases" / task["case_id"],
                                  limits=CASE_LIMITS, environment_factory=prepare_environment)
            row = {"case_id": task["case_id"], "status": result["status"],
                   "stop_reason": result["stop_reason"], "model_calls": result["model_calls"],
                   "tool_calls": result["tool_calls"], "reference_unreviewed": result["reference"]}
            rows.append(row)
            save(out / "case_receipts" / (task["case_id"] + ".json"), row)
            print(json.dumps({"progress": len(rows), "planned": 48,
                              "case_id": task["case_id"], "status": result["status"],
                              "calls_reserved": guard.budget.calls}), flush=True)
    except BaseException as exc:
        stop = "campaign_stopped_no_retry"
        error = type(exc).__name__ + ": " + str(exc)
        save(out / "campaign_failure.json", {"error": error, "traceback": traceback.format_exc()})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        backend.close()
        known = {r["case_id"] for r in rows}
        all_rows = rows + [{"case_id": t["case_id"],
                           "status": "interrupted" if t["case_id"] in guard.budget.attempted else "not_started",
                           "reference_unreviewed": {"label": None, "status": "reference_unknown"}}
                          for t in manifest["tasks"] if t["case_id"] not in known]
        summary = {"stop_reason": stop, "error": error, "attempts_claimed": len(guard.budget.attempted),
                   "calls_reserved": guard.budget.calls, "requested_output_tokens": guard.budget.reserved_output_tokens,
                   "monitor_calls": 0, "retries": 0, "automatic_expansion": False,
                   "elapsed_seconds_including_startup": time.monotonic() - started,
                   "results": all_rows, "review_complete": False, "formal_test_eligible": False}
        save(out / "summary_UNREVIEWED.json", summary)
        files = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
        save(out / "file_hashes.json", files)
        print(json.dumps({k:v for k,v in summary.items() if k != "results"}), flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(run())
