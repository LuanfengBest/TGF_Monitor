"""Native structured evidence-ID output; follow-up actor is strictly tool-disabled."""
from copy import deepcopy
import os

from prospective_monitoring import native_backend as native
from prospective_monitoring.campaign import check_asset_inventory
from . import protocol as p


class Stage(native.NativeStageBackend):
    def generate_actor(self, request, timeout_seconds):
        raise PermissionError("Environment collection is disabled")

    def generate(self, request, timeout_seconds):
        if request["stage"] == "actor":
            return super().generate(request, timeout_seconds)
        stage = request["stage"]
        if self.which != "monitor" or stage not in {"review", "planner", "judge"}:
            raise ValueError("Wrong model or stage")
        if request["model"] != self.config["models"]["monitor"] or request["revision"] != self.config["revisions"]["monitor"]:
            raise ValueError("Wrong monitor identity")
        cap = request["max_output_tokens"]
        if type(cap) is not int or not 0 < cap <= self.config["stage_output_caps"][stage]:
            raise ValueError("Output cap changed")
        prompt = request["content"]["prompt"]
        return self._sample(self.codec.monitor_prompt(prompt), cap, request["seed"], timeout_seconds, p.output_schema(stage, prompt))


def worker(connection, which, config, snapshot, permit_live):
    if hasattr(os, "setsid"):
        os.setsid()
    backend = None
    try:
        if permit_live is not True:
            raise PermissionError("Explicit replay admission required")
        backend = Stage(which, config, snapshot, permit_live=True).start()
        connection.send({"kind": "ready"})
        while True:
            packet = connection.recv()
            if packet["method"] == "close":
                return
            if packet["method"] != "generate":
                raise PermissionError("Only tool-disabled comparison requests are allowed")
            try:
                result = backend.generate(packet["request"], packet["timeout_seconds"])
                connection.send({"kind": "result", "value": result})
            except Exception as exc:
                connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc),
                                 "dispatched": not isinstance(exc, native.CapacityError), "raw": getattr(exc, "raw", None)})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send({"kind": "error", "error_type": type(exc).__name__, "message": str(exc), "dispatched": False})
    finally:
        if backend is not None:
            backend.close()
        connection.close()


class ProcessStage(native.ProcessStageBackend):
    def __init__(self, which, config, snapshot, *, permit_live, startup_timeout_seconds):
        if permit_live is not True:
            raise PermissionError("Explicit replay admission required")
        super().__init__(which, config, snapshot, permit_live=True, startup_timeout_seconds=startup_timeout_seconds,
                         _worker_target=worker)
        self.offline, self.origin_kind = False, "natural_actor"

    def generate_actor(self, request, timeout_seconds):
        raise PermissionError("Environment collection is disabled")


class Factory:
    execution_mode = "live"

    def __init__(self, bundle, preflight, permit):
        from .campaign import validate_receipts
        self.config, _, _ = validate_receipts(bundle, preflight, permit)
        self.preflight = deepcopy(preflight)

    def __call__(self, which, remaining_seconds):
        check_asset_inventory(self.preflight, which, self.config["revisions"][which])
        backend = ProcessStage(which, self.config, self.preflight["snapshots"][which], permit_live=True,
                               startup_timeout_seconds=min(remaining_seconds, self.config["limits"]["model_startup_seconds"]))
        return backend.start()
