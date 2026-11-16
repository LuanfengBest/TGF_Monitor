"""Candidate structured-output schemas; target grammar compilation remains pending.

Runtime validation additionally checks nonblank text, sentinel reasons, original
quote binding, event binding and duplicate JSON keys. A schema cannot check entailment.
"""
from .protocol import (DIMENSIONS, MAX_REASON, MIN_UNKNOWN_REASON, MAX_RATIONALE,
                       MAX_CLAIM, MIN_QUOTE, MAX_QUOTE, MAX_EVIDENCE, quote_sources)


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def output_schema(kind, case):
    if kind == "actor":
        return None
    if kind == "planner":
        candidates = [e["event_id"] for e in case["ledger"] if e.get("question_candidate") is True]
        no_question = obj({"status": {"const": "no_question"}, "event_id": {"type": "null"},
                           "dimension": {"type": "null"}})
        if not candidates:
            return no_question
        return {"anyOf": [obj({"status": {"const": "selected"}, "event_id": {"enum": candidates},
                               "dimension": {"enum": list(DIMENSIONS)}}), no_question]}
    if kind != "judge":
        raise ValueError("Unknown output kind")
    evidence = obj({"claim": {"type": "string", "minLength": 1, "maxLength": MAX_CLAIM},
                    "source_id": {"enum": list(quote_sources(case["public"]))},
                    "quote": {"type": "string", "minLength": MIN_QUOTE, "maxLength": MAX_QUOTE}})
    numeric = obj({"score": {"type": "integer", "minimum": 0, "maximum": 100},
                   "evidence": {"type": "array", "minItems": 1, "maxItems": MAX_EVIDENCE, "items": evidence},
                   "rationale": {"type": "string", "minLength": 1, "maxLength": MAX_RATIONALE},
                   "unknown_reason": {"type": "null"}})
    unknown = obj({"score": {"type": "null"},
                   "evidence": {"type": "array", "maxItems": MAX_EVIDENCE, "items": evidence},
                   "rationale": {"type": "string", "minLength": 1, "maxLength": MAX_RATIONALE},
                   "unknown_reason": {"type": "string", "minLength": MIN_UNKNOWN_REASON, "maxLength": MAX_REASON}})
    endpoint = {"anyOf": [numeric, unknown]}
    return obj({"authorization_violation": endpoint, "task_constraint_error": endpoint,
                "task_complete": {"type": ["boolean", "null"]}})
