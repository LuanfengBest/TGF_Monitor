"""Constrain syntax and source IDs, never force the substantive verdict."""
from .public import source_map


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def output_schema(kind, case):
    if kind == "actor":
        return None
    if kind == "planner":
        candidates = [e["event_id"] for e in case["ledger"] if e["question_candidate"]]
        no_question = obj({"status": {"const": "no_question"}, "event_id": {"type": "null"},
                           "question": {"type": "null"}})
        if not candidates:
            return no_question
        return {"anyOf": [obj({"status": {"const": "selected"},
                               "event_id": {"enum": candidates},
                               "question": {"type": "string", "minLength": 1, "maxLength": 650}}), no_question]}
    evidence = obj({"claim": {"type": "string", "minLength": 1, "maxLength": 500},
                    "sources": {"type": "array", "minItems": 1, "maxItems": 4,
                                "items": {"enum": list(source_map(case["public"]))}}})
    endpoint = obj({"score": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
                    "evidence": {"type": "array", "maxItems": 4, "items": evidence},
                    "rationale": {"type": "string", "maxLength": 800}})
    return obj({"authorization_violation": endpoint, "task_constraint_error": endpoint,
                "task_complete": {"type": ["boolean", "null"]},
                "unknown_reason": {"type": "string", "minLength": 1, "maxLength": 500}})
