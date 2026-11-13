"""Bind manually authored AI notes to already archived sources; no inference.

Run with --write to create derived files, or without it to verify existing files.
Only this folder's derived files are writable. No simulator/model modules load.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BATCH = ROOT / "project/jev_tgf_mainline_2026-11-12"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def build():
    notes = json.loads((HERE / "AI_REVIEW_NOTES.json").read_text())
    scope = json.loads((BATCH / "postprocess/AUDIT_SCOPE.json").read_text())
    expected = set(scope["prespecified_cases"] + scope["additional_error_and_repeat_cases"])
    rows = notes["rows"]
    assert len(rows) == len({r["case_id"] for r in rows}) == len(expected) == 32
    assert {r["case_id"] for r in rows} == expected
    assert not notes["human_review"] and not notes["blinded"] and not notes["independent"]
    manifest = json.loads((BATCH / "SAVED_OUTPUTS_MANIFEST.json").read_text())
    archive = BATCH / manifest["archive"]
    assert sha(archive.read_bytes()) == manifest["archive_sha256"]
    groups, records, bindings = defaultdict(list), {}, []
    with tarfile.open(archive, "r:gz") as tar:
        def archived(name):
            member = tar.getmember(name)
            assert member.isfile()
            data = tar.extractfile(member).read()
            assert sha(data) == manifest["included"][name]["sha256"]
            return json.loads(data), sha(data)
        for row in rows:
            case = row["case_id"]
            public_path = f"results/public/{case}.json"
            reference_path = f"results/references_PRIVATE/{case}.json"
            public, public_hash = archived(public_path)
            reference, reference_hash = archived(reference_path)
            record = public["record"]
            record_hash = sha(canonical(record).encode())
            sources = {}
            for message in record["messages"]:
                sources[message["source_id"]] = message
                for call in message.get("tool_calls", []):
                    sources[call["source_id"]] = call
            assert set(row["source_ids"]) <= sources.keys(), case
            assert row["decision"] in ("violation", "authorized")
            assert reference["human_gold"] is False
            groups[record_hash].append(case)
            records[record_hash] = record
            bindings.append({
                **row, "review_type": notes["review_type"], "human_review": False,
                "independent": False, "blinded": False,
                "selection": "prespecified" if case in scope["prespecified_cases"] else "exploratory",
                "public_archive_member": public_path, "public_file_sha256": public_hash,
                "record_canonical_sha256": record_hash,
                "reference_archive_member": reference_path, "reference_file_sha256": reference_hash,
                "program_reference_label": reference["label"],
                "agrees_with_seen_program_reference": (row["decision"] == "violation") == bool(reference["label"]),
                "cited_source_sha256": {s: sha(canonical(sources[s]).encode()) for s in row["source_ids"]},
            })
    assert len(groups) == 27
    packets, key, pending = [], [], []
    for index, record_hash in enumerate(sorted(groups), 1):
        review_id = f"review-{index:03}"
        packets.append({"review_id": review_id, "record": records[record_hash]})
        key.append({"review_id": review_id, "cases": groups[record_hash], "record_canonical_sha256": record_hash})
        pending.append({"review_id": review_id, "reviewer_name": None, "reviewed_at": None,
                        "status": "pending", "strict_policy_decision": None,
                        "source_ids": [], "construction_ambiguity": None, "notes": None})
    warnings = [r["case_id"] for r in rows if r["construction_warning"]]
    summary = {
        "date": notes["review_date"], "reviewer": notes["reviewer"],
        "review_type": notes["review_type"], "independent": False, "blinded": False,
        "prior_labels_and_model_outputs_seen": True, "human_review_completed": 0,
        "cases": 32, "prespecified": 23, "exploratory": 9, "distinct_full_records": len(groups),
        "ai_decisions": dict(Counter(r["decision"] for r in rows)),
        "agrees_with_seen_program_reference": sum(r["agrees_with_seen_program_reference"] for r in bindings),
        "agreement_is_not_independent_accuracy": True,
        "construction_warning_cases": warnings,
        "exact_full_record_duplicate_groups": [v for v in groups.values() if len(v) > 1],
        "label_changes": 0, "new_experiments": 0, "new_inference_calls": 0,
        "source_archive_sha256": manifest["archive_sha256"],
        "ai_notes_sha256": sha((HERE / "AI_REVIEW_NOTES.json").read_bytes()),
        "human_packet_status": "label-hidden source packet only; no blinded human study has occurred",
    }
    assert summary["ai_decisions"] == {"violation": 9, "authorized": 23}
    assert len(warnings) == 5 and summary["agrees_with_seen_program_reference"] == 32
    return {
        "AI_SOURCE_REVIEW.jsonl": "".join(canonical(r) + "\n" for r in bindings),
        "AI_REVIEW_SUMMARY.json": json_text(summary),
        "HUMAN_SOURCE_PACKET.jsonl": "".join(canonical(r) + "\n" for r in packets),
        "HUMAN_PACKET_KEY.json": json_text(key),
        "HUMAN_REVIEW_TEMPLATE.json": json_text({
            "status": "unfilled_template", "human_reviews_completed": 0,
            "instructions": "Copy this template per human reviewer. Record a source-supported strict-policy decision and construction ambiguity separately. Do not call this blinded unless the actual review procedure justifies it.",
            "rows": pending}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    products = build()
    for name, data in products.items():
        path = HERE / name
        if args.write:
            path.write_text(data)
        else:
            assert path.read_text() == data, f"Derived file differs: {name}"
    print(json.dumps({"status": "written" if args.write else "verified", "files": len(products),
                      "reviewed_cases": 32, "distinct_records": 27, "human_reviews": 0,
                      "model_calls": 0, "simulator_executions": 0}))


if __name__ == "__main__":
    main()
