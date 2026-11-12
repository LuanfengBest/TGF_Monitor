"""One fixed end-to-end pilot gates expansion; failed cases are never replaced."""
from pathlib import Path
from .common import load


def pilot_gate(directory, config):
    root = Path(directory)
    planners = valid = pairs = 0
    details = []
    for cid in config["pilot_cases"]:
        i = config["cases"].index(cid)
        prefix = f"c{i:02d}"
        s = load(root / "selection" / (prefix + ".json"))
        planners += s["status"] in {"selected", "no_question"}
        judgments = {}
        for arm in ("P", "L", "F", "T"):
            p = root / "judgments" / (prefix + "." + arm + ".json")
            result = load(p) if p.exists() else {"status": "missing"}
            valid += result["status"] == "valid"
            judgments[arm] = result
        paired = all(judgments[a]["status"] == "valid" and
                     judgments[a]["judgment"]["authorization_violation"]["score"] is not None
                     for a in ("F", "T"))
        pairs += paired
        details.append({"case_id": cid, "planner": s["status"], "resolved_FT_pair": paired,
                        "judgments": {a: r["status"] for a, r in judgments.items()}})
    cap = config["campaign"]
    return {"passed": planners >= cap["pilot_min_planners"] and
                      valid >= cap["pilot_min_valid_main_judgments"] and
                      pairs >= cap["pilot_min_resolved_pairs"],
            "valid_planners": planners, "valid_main_judgments": valid,
            "resolved_FT_pairs": pairs, "details": details,
            "not_an_accuracy_or_effectiveness_gate": True}
