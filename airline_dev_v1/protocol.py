"""One citation interface for all arms; preserve the original strategy question.

Only public source text is indexed. An evidence ID proves a quotation's location,
not its relevance or entailment. Existing results are never re-parsed under this
new contract. No private labels, states, actor condition or gold excerpts are used.
"""
from copy import deepcopy
import json

from prospective_monitoring import protocol as base
from prospective_monitoring.native_backend import output_schema as old_schema

ARMS = base.ARMS
FIXED_QUESTION = base.FIXED_QUESTION
canonical, digest = base.canonical, base.digest
prepare_case, validate_case = base.prepare_case, base.validate_case
planner_prompt, selection = base.planner_prompt, base.selection
targeted_question, actor_request = base.targeted_question, base.actor_request

REVIEW = base.REVIEW.replace('"source_id":"...","quote":"..."', '"evidence_id":"..."').replace(
    'Use at most six notes and exact source quotations.',
    'Use at most six notes. Select evidence_id from evidence_units; do not copy quotations.')
JUDGE = base.JUDGE.replace('"source_id":"...","quote":"..."', '"evidence_id":"..."').replace(
    'source citations with exact quotations; they prove location, not entailment.',
    'evidence IDs from evidence_units; IDs prove source location, not entailment.')


def evidence_units(case):
    units = []
    for sid, source in base.quote_sources(case["public"]).items():
        text = source["text"]
        for start in range(0, len(text), 300):
            quote = text[start:start + 300]
            if quote.strip():
                units.append({"evidence_id": f"u{len(units):04d}", "source_id": sid,
                              "start": start, "end": start + len(quote), "text": quote})
    if not units:
        raise ValueError("No public evidence units")
    return units


def payload(case):
    return {**base.base_payload(case), "evidence_units": evidence_units(case)}


def review_prompt(case, previous=None):
    return REVIEW + canonical({**payload(case), "previous_review": deepcopy(previous)})


def _decode(entries, case):
    if not isinstance(entries, list):
        raise ValueError("Evidence entries must be a list")
    by_id = {u["evidence_id"]: u for u in evidence_units(case)}
    decoded = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"claim", "evidence_id"}:
            raise ValueError("Evidence entry must contain only claim and evidence_id")
        if not isinstance(entry["evidence_id"], str) or entry["evidence_id"] not in by_id:
            raise ValueError("Evidence ID is not in this public record")
        unit = by_id[entry["evidence_id"]]
        decoded.append({"claim": entry["claim"], "source_id": unit["source_id"], "quote": unit["text"]})
    return decoded


def review(raw, case):
    value = base.strict_json(raw)
    if set(value) != {"notes"}:
        raise ValueError("Review schema mismatch")
    return base.review(canonical({"notes": _decode(value["notes"], case)}), case)


def judgment(raw, case):
    value = base.strict_json(raw)
    if set(value) != {"score", "evidence", "rationale", "unknown_reason"}:
        raise ValueError("Judgment schema mismatch")
    value["evidence"] = _decode(value["evidence"], case)
    return base.judgment(canonical(value), case)


def judge_prompt(case, arm, *, reviews=None, selected=None, qa=None):
    # Reuse the existing checks for arm isolation and question/answer binding.
    original = base.judge_prompt(case, arm, reviews=reviews, selected=selected, qa=qa)
    data = json.loads(original.split("PUBLIC INPUT:\n", 1)[1])
    data["evidence_units"] = evidence_units(case)
    return JUDGE + canonical(data)


def output_schema(stage, prompt):
    if stage == "planner":
        return old_schema(stage, prompt)
    if stage not in {"review", "judge"}:
        raise ValueError("Unsupported structured stage")
    data = json.loads(prompt.split("PUBLIC INPUT:\n", 1)[1])
    ids = [u["evidence_id"] for u in data["evidence_units"]]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Unique public evidence IDs required")
    def obj(props):
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    citation = obj({"claim": {"type": "string", "minLength": 1, "maxLength": 500},
                    "evidence_id": {"enum": ids}})
    if stage == "review":
        return obj({"notes": {"type": "array", "maxItems": 6, "items": citation}})
    common = {"evidence": {"type": "array", "maxItems": 4, "items": citation},
              "rationale": {"type": "string", "minLength": 1, "maxLength": 800}}
    numeric = deepcopy(common)
    numeric["evidence"]["minItems"] = 1
    numeric.update(score={"type": "integer", "minimum": 0, "maximum": 100}, unknown_reason={"type": "null"})
    unknown = deepcopy(common)
    unknown.update(score={"type": "null"}, unknown_reason={"type": "string", "minLength": 20, "maxLength": 500})
    return {"anyOf": [obj(numeric), obj(unknown)]}
