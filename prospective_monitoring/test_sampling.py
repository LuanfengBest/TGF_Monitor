from copy import deepcopy
import hashlib
import unittest

from prospective_monitoring.sampling import select_test_cases, validate_candidates


def candidate(case_id, label, environment="bank", family_id=None, split="test", sensitive=None, **changes):
    row = {"case_id": case_id, "environment": environment,
           "family_id": family_id or environment + "_" + case_id, "split": split,
           "label": label, "reference_complete": True, "capacity_ok": True,
           "normalized_hash": hashlib.sha256(case_id.encode()).hexdigest(),
           "sensitive_negative": label == 0 if sensitive is None else sensitive,
           "origin_kind": "natural_actor"}
    row.update(changes)
    return row


def registry(rows, **changes):
    families = {r["family_id"]: {k: r[k] for k in ("family_id", "environment", "split")} for r in rows}
    result = {"families": list(families.values()), "test_families_ready": True}
    result.update(changes)
    return result


class SamplingTests(unittest.TestCase):
    def test_selection_reproducible_and_input_order_independent(self):
        rows = [candidate(str(i), i % 2) for i in range(20)]
        reg = registry(rows)
        a = select_test_cases(rows, {"bank": {0: 3, 1: 3}}, registry=reg, seed=42)
        b = select_test_cases(list(reversed(rows)), {"bank": {0: 3, 1: 3}}, registry=reg, seed=42)
        self.assertEqual(a, b)
        self.assertEqual(len(a["selected_case_ids"]), 6)
        self.assertEqual(len(a["exclusions"]), 14)

    def test_monitor_result_fields_are_rejected_not_used_for_selection(self):
        for forbidden in ("arms", "score", "judge", "monitor_outputs", "TGF_score"):
            rows = [candidate("p", 1)]
            rows[0][forbidden] = {"score": 90}
            with self.assertRaisesRegex(ValueError, "allowlist"):
                select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=registry(rows))

    def test_same_family_cannot_cross_split_even_if_not_selected(self):
        rows = [candidate("d", 1, family_id="same", split="dev"),
                candidate("t", 1, family_id="same", split="test")]
        with self.assertRaisesRegex(ValueError, "crosses splits"):
            validate_candidates(rows)

    def test_relabelling_candidate_split_does_not_change_registry(self):
        rows = [candidate("d", 1, family_id="old", split="dev")]
        reg = registry(rows)
        rows[0]["split"] = "test"
        with self.assertRaisesRegex(ValueError, "registry"):
            select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=reg)

    def test_known_development_case_cannot_be_renamed_to_test_family(self):
        rows = [candidate("old", 1)]
        reg = registry(rows, known_development_case_ids=["old"])
        with self.assertRaisesRegex(ValueError, "known development"):
            select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=reg)

    def test_absent_test_registry_is_not_a_test_manifest(self):
        rows = [candidate("p", 1), candidate("n", 0)]
        with self.assertRaisesRegex(ValueError, "registry"):
            select_test_cases(rows, {"bank": {0: 1, 1: 1}})
        with self.assertRaisesRegex(ValueError, "no ready"):
            select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=registry(rows, test_families_ready=False))

    def test_duplicates_across_splits_and_within_test_are_excluded(self):
        rows = [candidate("dev", 1, split="dev"), candidate("copied", 1),
                candidate("p1", 1), candidate("p2", 1), candidate("n", 0)]
        rows[1]["normalized_hash"] = rows[0]["normalized_hash"]
        rows[3]["normalized_hash"] = rows[2]["normalized_hash"]
        result = select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=registry(rows))
        reasons = {x["case_id"]: x["reasons"] for x in result["exclusions"]}
        self.assertIn("duplicate_trace_in_other_split", reasons["copied"])
        self.assertIn("duplicate_normalized_trace", reasons["p2"])
        self.assertEqual(result["selected_case_ids"], ["n", "p1"])

    def test_conflicting_duplicate_reference_is_not_arbitrarily_kept(self):
        rows = [candidate("p", 1), candidate("n", 0)]
        rows[1]["normalized_hash"] = rows[0]["normalized_hash"]
        result = select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=registry(rows))
        self.assertEqual(result["selected_case_ids"], [])
        self.assertTrue(all("duplicate_hash_reference_conflict" in x["reasons"] for x in result["exclusions"]))

    def test_unknown_incomplete_capacity_and_scripted_fixtures_cannot_enter_test(self):
        rows = [candidate("unknown", None), candidate("missing_log", 0, reference_complete=False),
                candidate("too_long", 1, capacity_ok=False),
                candidate("script", 1, origin_kind="scripted_cpu_fixture"), candidate("n", 0)]
        result = select_test_cases(rows, {"bank": {0: 1, 1: 1}}, registry=registry(rows))
        reasons = {x["case_id"]: x["reasons"] for x in result["exclusions"]}
        self.assertIn("reference_unknown", reasons["unknown"])
        self.assertIn("incomplete_reference_evidence", reasons["missing_log"])
        self.assertIn("capacity_ineligible", reasons["too_long"])
        self.assertIn("not_natural_actor_trajectory", reasons["script"])
        self.assertEqual(result["status"], "insufficient_pool")
        self.assertEqual(result["selected_case_ids"], [])

    def test_at_least_half_negatives_require_real_sensitive_actions(self):
        rows = [candidate("p1", 1), candidate("p2", 1), candidate("s", 0),
                candidate("n1", 0, sensitive=False), candidate("n2", 0, sensitive=False),
                candidate("n3", 0, sensitive=False)]
        result = select_test_cases(rows, {"bank": {0: 4, 1: 2}}, registry=registry(rows))
        self.assertEqual(result["selected_case_ids"], [])
        self.assertEqual(result["shortfalls"][0]["sensitive_negative_shortfall"], 1)
        self.assertEqual(result["status"], "insufficient_pool")

    def test_family_cap_uses_feasible_assignment_not_greedy_choice(self):
        rows = [candidate("a_p", 1, family_id="a"), candidate("a_sensitive", 0, family_id="a"),
                candidate("b_p", 1, family_id="b"),
                candidate("c_plain", 0, family_id="c", sensitive=False)]
        result = select_test_cases(rows, {"bank": {0: 2, 1: 1}}, max_per_family=1, registry=registry(rows))
        self.assertEqual(result["selected_case_ids"], ["a_sensitive", "b_p", "c_plain"])

    def test_no_partial_final_manifest_when_one_environment_short(self):
        rows = [candidate("bp", 1), candidate("bn", 0), candidate("ap", 1, "airline")]
        result = select_test_cases(rows, {"bank": {0: 1, 1: 1}, "airline": {0: 1, 1: 1}}, registry=registry(rows))
        self.assertEqual(result["selected_case_ids"], [])
        self.assertTrue(result["provisional_case_ids"])
        self.assertEqual(result["shortfalls"][0]["environment"], "airline")


if __name__ == "__main__":
    unittest.main()
