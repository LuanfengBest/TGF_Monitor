"""Durable, single-use call slots; no retry after dispatch, including crashes."""
import os
import time
from pathlib import Path
from .common import digest, freeze_hashes, load, save


def slots(config):
    result = {}
    for index, cid in enumerate(config["cases"]):
        prefix = f"c{index:02d}"
        result[prefix + ".planner"] = {"case": cid, "kind": "planner", "seed": config["seed"]}
        for arm in ("P", "L", "F", "T"):
            result[prefix + "." + arm] = {"case": cid, "kind": "judge", "seed": config["seed"], "arm": arm}
        for seed in config["ledger_repeat_seeds"]:
            result[f"{prefix}.L{seed}"] = {"case": cid, "kind": "judge", "seed": seed, "arm": "L"}
        for arm in ("F", "T"):
            result[prefix + ".actor" + arm] = {"case": cid, "kind": "actor", "seed": config["seed"], "arm": arm}
    return result


class Budget:
    def __init__(self, directory, config):
        self.directory, self.config = Path(directory), config
        self.path = self.directory / "call_manifest.json"

    def initialize(self, receipt, now=None):
        # mkdir is the single reservation: an existing run may never be restarted.
        self.directory.mkdir(parents=True, exist_ok=False)
        started = time.time() if now is None else now
        table = slots(self.config)
        caps = self.config["limits"]
        if len(self.config["cases"]) > 64 or caps["calls"] > 600 or caps["wall_seconds"] > 14400 or caps["gpus"] != 1 or caps["retries"] != 0:
            raise ValueError("Exceeds user-authorized campaign budget")
        if len(table) > caps["calls"] or sum(caps[v["kind"] + "_output"] for v in table.values()) > caps["output_tokens"]:
            raise ValueError("Plan exceeds frozen budget")
        state = {"schema_version": "single-reservation-v1", "config_sha256": digest(self.config),
                 "code_hashes": freeze_hashes(), "started_at_unix": started,
                 "deadline_unix": started + caps["wall_seconds"], "status": "reserved",
                 "preflight": receipt, "slots": {k: dict(v, status="pending") for k, v in table.items()}}
        save(self.path, state)

    def state(self):
        state = load(self.path)
        if state["config_sha256"] != digest(self.config) or state["code_hashes"] != freeze_hashes():
            raise ValueError("Configuration/code changed after reservation")
        return state

    def remaining(self):
        return self.state()["deadline_unix"] - time.time()

    def dispatch(self, slot, prompt_tokens, prompt_sha256):
        # Keep lock across generation. Crash leaves the lock and dispatched slot;
        # neither is automatically cleared or retried.
        fd = os.open(self.directory / "generation.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            state = self.state()
            item = state["slots"][slot]
            if item["status"] != "pending":
                raise ValueError("Call slot already consumed")
            if time.time() >= state["deadline_unix"] - 30:
                raise TimeoutError("Insufficient budget for another call")
            limit = self.config["limits"][item["kind"] + "_output"]
            model = "actor" if item["kind"] == "actor" else "monitor"
            if prompt_tokens + limit > self.config[model]["context"]:
                raise ValueError("Actual prompt exceeds capacity")
            item.update(status="dispatched", prompt_tokens=prompt_tokens,
                        prompt_sha256=prompt_sha256, output_token_reservation=limit,
                        dispatched_at_unix=time.time())
            state["status"] = "running"
            save(self.path, state)
            return item
        except BaseException:
            (self.directory / "generation.lock").unlink()
            raise

    def complete(self, slot, output):
        state = self.state()
        item = state["slots"][slot]
        if item["status"] != "dispatched":
            raise ValueError("Call not dispatched")
        if output["completion_tokens"] > item["output_token_reservation"]:
            raise ValueError("Backend exceeded output-token reservation")
        item.update(status="completed", completion_tokens=output["completion_tokens"],
                    finish_reason=output["finish_reason"], completed_at_unix=time.time())
        save(self.path, state)
        (self.directory / "generation.lock").unlink()

    def skip(self, slot, reason):
        state = self.state()
        if state["slots"][slot]["status"] != "pending":
            raise ValueError("Only a pending slot can be skipped")
        state["slots"][slot].update(status="not_dispatched", reason=reason)
        save(self.path, state)

    def close(self, reason):
        state = self.state()
        for item in state["slots"].values():
            if item["status"] == "pending":
                item.update(status="not_dispatched", reason=reason)
        state.update(status="closed", closed_at_unix=time.time(), close_reason=reason)
        save(self.path, state)
