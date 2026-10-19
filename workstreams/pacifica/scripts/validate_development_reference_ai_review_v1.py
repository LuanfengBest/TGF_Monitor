"""Read-only provenance checks for the provisional three-case AI review."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "data/annotation_review/development_reference_audit_20261013"
    validation = json.loads((root / "analysis/development_reference_ai_review_validation_20261013.json").read_text())
    review_path = root / validation["review_file"]
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(review_path) == validation["review_sha256"]
    for name, expected in validation["protected_files_unchanged"].items():
        assert digest(root / name) == expected, name
    review = json.loads(review_path.read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert not review["adopted_as_official_reference"]
    assert not review["independent_human_review_completed"]
    assert not review["training_eligible"]
    cases = {r["case_id"]: r for r in review["cases"]}
    assert len(cases) == len(review["cases"]) == 3
    quote_count = 0
    for item in manifest["cases"]:
        row = cases[item["case_id"]]
        path = directory / item["visible_file"]
        assert digest(path) == item["source_sha256"] == row["input_sha256"]
        view = json.loads(path.read_text())
        assert row["target_action"] == view["target_action"]
        assert row["audit_dimensions"] == view["audit_dimensions"]
        assert row["original_input_id"] == item["original_input_id"]
        assert row["review_status"] == "ai_review_provisional"
        assert row["saw_model_predictions_before_labeling"]
        assert not row["independent_review"] and not row["blind_review"]
        assert not row["training_eligible"]
        sources = {s["source_id"]: s["text"] for s in view["sources"]}
        for evidence in row["evidence"]:
            assert evidence["quote"] and evidence["quote"] in sources[evidence["source_id"]]
            quote_count += 1
        for effect in row["other_visible_effects"]:
            assert set(effect["source_ids"]) <= sources.keys()
        if row["authorization"] == "insufficient_evidence":
            assert row["executed_unauthorized_in_scope"] is None
        if "amount" not in row["audit_dimensions"]:
            assert all(row[k] is None for k in ("authorized_amount", "observed_amount", "excess_amount"))
    for divisor, calculation in zip((3, 2), cases["review_01"]["conditional_calculations"]):
        amount = Decimal("900") + Decimal("750") + Decimal("135") / divisor
        assert amount == Decimal(calculation["authorized_amount"])
        assert Decimal("1717.50") - amount == Decimal(calculation["observed_minus_authorized"])
    user = json.loads((directory / "review_user.json").read_text())
    assert all(r["review_status"] == "unreviewed" and r["authorization"] is None for r in user)
    assert quote_count == validation["literal_quotes_checked"] == 26
    print(json.dumps({"cases": 3, "literal_quotes": quote_count, "protected_files_unchanged": 9,
                      "semantic_correctness_verified_by_program": False, "status": "verified"}))


if __name__ == "__main__":
    main()
