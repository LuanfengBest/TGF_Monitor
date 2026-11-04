"""CPU-only recorder around the repository's original simulator/tool runtime.

No LLM client or job submission is constructed here. The dependency-heavy original
runtime is imported only by load_original_environment(). Projection and recording
use only the standard library. This adapter covers Venmo/Zelle principal transfers,
flight purchase (including upgrades bought with the ticket), and cancellation.
Other write tools are deliberately unresolved, never silently valid negatives.
"""
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import importlib
import json
from pathlib import Path
import sys


SUPPORTED_TOOLS = {
    "bank": ("send_money_venmo", "send_money_zelle"),
    "airline": ("buy_flight_ticket", "cancel_flight_booking"),
}
DIAGNOSTIC_TOOLS = {
    "bank": ("schedule_transaction",),
    "airline": ("purchase_flight_upgrades",),
}


class SnapshotError(ValueError):
    """The original state cannot be faithfully projected into the narrow reference."""


def _plain(value):
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return _plain(value.value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise SnapshotError("Unsupported snapshot value: " + type(value).__name__)


def canonical(value):
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _money(value):
    # Original simulator uses float. Decimal(str(...)) preserves its exposed value;
    # we reject sub-cent/non-finite amounts rather than silently rounding evidence.
    if type(value) is bool:
        raise SnapshotError("Boolean money")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SnapshotError("Invalid original amount") from exc
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise SnapshotError("Original amount is negative, non-finite or not exact cents")
    return format(amount, ".2f")


def snapshot_original(environment):
    """Copy the full original simulator state, not just its tool success strings."""
    result = _plain(environment)
    if not isinstance(result, dict):
        raise SnapshotError("Original environment snapshot is not an object")
    canonical(result)
    return result


def project_state(raw, domain):
    """Normalize actual persisted state, with stable source-derived record IDs."""
    if domain == "bank":
        transfers = []
        for service in ("venmo", "zelle"):
            try:
                history = raw[service]["transaction_history"]
            except (KeyError, TypeError) as exc:
                raise SnapshotError("Missing " + service + " transaction history") from exc
            for index, tx in enumerate(history):
                if tx.get("type") != "send":
                    continue
                if service == "zelle" and tx.get("status") != "completed":
                    raise SnapshotError("Zelle send has unresolved completion status")
                recipient = tx.get("recipient" if service == "venmo" else "recipient_email")
                if not isinstance(recipient, str) or not recipient.strip():
                    raise SnapshotError("Persisted transfer lacks exact recipient")
                transfers.append({"transaction_id": service + ":" + str(index),
                                  "recipient": service + ":" + recipient, "amount": _money(tx["amount"])})
        return {"transfers": transfers}
    if domain != "airline":
        raise SnapshotError("Unsupported environment")
    try:
        flights = raw["flights"]["flight_list"]
        tickets = raw["ticket_manager"]["tickets"]
        total_spent = raw["total_spent"]
    except (KeyError, TypeError) as exc:
        raise SnapshotError("Missing persisted flight state") from exc
    flights_by_number = {}
    for flight in flights:
        number = flight["flight_number"]
        if number in flights_by_number:
            raise SnapshotError("Flight catalog contains duplicate flight number")
        flights_by_number[number] = flight
    bookings = []
    for confirmation, ticket in sorted(tickets.items()):
        flight = flights_by_number.get(ticket["flight_number"])
        if flight is None:
            raise SnapshotError("Persisted ticket is absent from flight catalog")
        price = _money(ticket["price"])
        spent_key = ticket["passenger_name"] + ":" + ticket["flight_number"]
        if spent_key not in total_spent or _money(total_spent[spent_key]) != price:
            raise SnapshotError("Ticket price and actual spending disagree; post-booking upgrade unsupported")
        upgrades = ticket.get("upgrades") or []
        if not isinstance(upgrades, list) or any(not isinstance(x, str) for x in upgrades):
            raise SnapshotError("Invalid persisted upgrade list")
        normalized = [x.lower().replace(" ", "_") for x in upgrades]
        if len(set(normalized)) != len(normalized):
            raise SnapshotError("Duplicate persisted upgrades require separate policy")
        departure = str(flight["departure_time"])
        try:
            day = datetime.fromisoformat(departure).date().isoformat()
        except ValueError as exc:
            raise SnapshotError("Missing exact flight date") from exc
        bookings.append({"booking_id": confirmation, "passenger": ticket["passenger_name"],
                         "origin": flight["departure_city"], "destination": flight["arrival_city"],
                         "date": day, "price": price, "upgrades": normalized})
    return {"bookings": bookings}


def load_original_environment(domain):
    """Load existing environment and functions without touching model infrastructure.

    Run in a dedicated CPU process: the upstream project uses top-level `utils`,
    `tools` and `environment_classes` module names. No substitute dependencies or
    mocked simulator implementation are used when imports fail.
    """
    if domain not in SUPPORTED_TOOLS:
        raise ValueError("Unknown domain")
    root = Path(__file__).resolve().parents[1] / "datasets/dual_objective/agent"
    for package in ("utils", "tools", "environment_classes", "environments"):
        loaded = sys.modules.get(package)
        path = getattr(loaded, "__file__", None)
        if path and root not in Path(path).resolve().parents:
            raise RuntimeError("Conflicting upstream module namespace: " + package)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    importlib.import_module("utils.path_utils").set_project_root(root)
    name = "banking_environment" if domain == "bank" else "travel_environment"
    cls = "BankingEnvironment" if domain == "bank" else "TravelEnvironment"
    environment = getattr(importlib.import_module("environments." + name), cls).create()
    runtime = importlib.import_module("utils.functions_runtime").FunctionsRuntime()
    wanted = set(SUPPORTED_TOOLS[domain]) | set(DIAGNOSTIC_TOOLS[domain])
    for function in environment.available_tools:
        if function.__name__ in wanted:
            runtime.register_function(function)
    if set(runtime.functions) != wanted:
        raise RuntimeError("Original runtime omitted expected fixture tools")
    return environment, runtime


class RecordedSimulator:
    """Record every invoked write, including partial effects before an exception.

    `runtime` is the original FunctionsRuntime in real CPU acceptance tests. Unit
    tests may deliberately inject broken runtimes; such tests are not trajectories.
    The recorder cannot certify calls that bypass it; continuity checks detect state
    changes between recorded calls, and callers must route all covered writes here.
    """

    def __init__(self, environment, runtime, domain, scenario_id):
        self.environment, self.runtime = environment, runtime
        self.domain, self.scenario_id = domain, scenario_id
        self.events, self.receipts, self.issues = [], [], []
        self._raw_last = snapshot_original(environment)
        self.initial_state = project_state(self._raw_last, domain)
        self._last = deepcopy(self.initial_state)

    def _issue(self, text):
        if text not in self.issues:
            self.issues.append(text)

    def execute(self, function, args):
        sequence = len(self.events) + 1
        before_raw = snapshot_original(self.environment)
        if before_raw != self._raw_last:
            self._issue("State changed outside the recorded tool calls")
        before = None
        try:
            before = project_state(before_raw, self.domain)
        except (SnapshotError, KeyError, TypeError) as exc:
            self._issue(str(exc))
        try:
            output, error = self.runtime.run_function(self.environment, function, deepcopy(args))
        except Exception as exc:
            output, error = None, type(exc).__name__ + ": " + str(exc)
        after_raw = snapshot_original(self.environment)
        after = None
        try:
            after = project_state(after_raw, self.domain)
        except (SnapshotError, KeyError, TypeError) as exc:
            self._issue(str(exc))

        event = {"event_id": "event-" + str(sequence), "sequence": sequence,
                 "operation": "unmapped", "status": "unresolved", "payload": deepcopy(args),
                 "before": before, "after": after,
                 "call_source_id": "call-" + str(sequence), "result_source_id": "result-" + str(sequence)}
        if function not in SUPPORTED_TOOLS[self.domain]:
            self._issue("Unmapped write tool: " + function)
        elif before is not None and after is not None:
            key, id_key = (("transfers", "transaction_id") if self.domain == "bank" else
                           ("bookings", "booking_id"))
            old = {r[id_key]: r for r in before[key]}
            new = {r[id_key]: r for r in after[key]}
            added, removed = set(new) - set(old), set(old) - set(new)
            modified = any(old[k] != new[k] for k in set(old) & set(new))
            operation = "transfer" if self.domain == "bank" else "book_flight"
            if old == new:
                event.update(operation=operation, status="rejected")
            elif len(added) == 1 and not removed and not modified and function != "cancel_flight_booking":
                event.update(operation=operation, status="committed", payload=new[next(iter(added))])
            elif len(removed) == 1 and not added and not modified and function == "cancel_flight_booking":
                event.update(operation="cancel_flight", status="committed",
                             payload={"target_id": next(iter(removed))})
            else:
                self._issue("State delta does not match one supported committed operation")

        # Bank schedules and other bank transaction mutations are not principal sends
        # in this first reference. Even a covered tool must not mutate them silently.
        if self.domain == "bank" and before_raw.get("bank_account") != after_raw.get("bank_account"):
            self._issue("Bank account/scheduled payment mutation is outside this reference")
        receipt = {"event_id": event["event_id"], "function": function, "args": deepcopy(args),
                   "output": _plain(output), "error": error, "before_raw": before_raw,
                   "after_raw": after_raw, "before_sha256": _digest(before_raw),
                   "after_sha256": _digest(after_raw)}
        self.events.append(event)
        self.receipts.append(receipt)
        self._raw_last, self._last = after_raw, after
        return deepcopy(receipt)

    def journal(self):
        now = snapshot_original(self.environment)
        if now != self._raw_last:
            self._issue("State changed after the last recorded tool call")
        try:
            final_state = project_state(now, self.domain)
        except (SnapshotError, KeyError, TypeError) as exc:
            final_state = None
            self._issue(str(exc))
        return {"schema_version": "execution-journal-v1", "scenario_id": self.scenario_id,
                "environment": self.domain, "complete": not self.issues,
                "initial_state": deepcopy(self.initial_state), "final_state": final_state,
                "events": deepcopy(self.events), "adapter_issues": list(self.issues),
                "scope": "venmo_zelle_principal" if self.domain == "bank" else "ticket_purchase_and_cancellation",
                "origin_kind": "scripted_cpu_fixture"}

    def evidence(self):
        return {"journal": self.journal(), "raw_tool_receipts": deepcopy(self.receipts),
                "origin_kind": "scripted_cpu_fixture", "model_calls": 0}
