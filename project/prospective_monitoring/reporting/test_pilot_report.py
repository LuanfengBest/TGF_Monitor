from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("prospective_pilot_report", Path(__file__).with_name("pilot_report.py"))
reporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reporter)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def cost(seconds=0.1, complete=True, mode="native_model_usage"):
    return {"model": "monitor", "input_tokens": 10 if complete else 0,
            "output_tokens": 2 if complete else 0, "inference_seconds": seconds,
            "usage_complete": complete, "usage_mode": mode}


def make_run(root, live=True):
    root.mkdir()
    tasks = [{"case_id": f"case-{i}", "family_id": f"family-{i}",
              "environment": "bank" if i < 2 else "airline", "split": "development"} for i in range(4)]
    rows = []
    dispatched = 0
    mode = "native_model_usage" if live else "scripted_cpu_fixture"
    for i, task in enumerate(tasks[:3]):
        admitted = i < 2
        row = {**task, "collection_status": "completed" if admitted else "timeout",
               "monitoring_admitted": admitted, "collection_failure_reason": None if admitted else "180 second collection limit",
               "collection_costs": [cost(mode=mode)], "arms": {}}
        for arm in reporter.ARMS:
            row["arms"][arm] = {"status": "ok" if admitted else "missing", "score": 80 if i == 1 else 0,
                                "costs": [cost(mode=mode)] if admitted else [],
                                "followup_performed": admitted and arm in {"F", "T"},
                                "failure_reason": None if admitted else "Not monitored: collection timeout"}
        if i == 2:
            for value in row["arms"].values():
                value["score"] = None
        collection = {**task, "origin_kind": "natural_actor" if live else "scripted_cpu_fixture",
                      "status": row["collection_status"], "stop_reason": "actor_final_response" if admitted else "timeout",
                      "reference": {"status": "resolved", "label": int(i == 1),
                                    "sensitive_execution": i == 1, "committed_events": int(i == 1), "unknown_reasons": []}}
        write(root / "private" / f"c{i:04d}.collection.json", collection)
        write(root / "c{:04d}.result.json".format(i), row)
        rows.append(row)
        stages = [("collection.000", "collection", None)]
        if admitted:
            stages += [(f"{a}.judge", "judge", a) for a in reporter.ARMS]
        for suffix, stage, arm in stages:
            directory = root / "calls" / (f"c{i:04d}." + suffix)
            request = {} if stage == "collection" else {"stage": stage, "model": "monitor"}
            write(directory / "request.json", {"request": request})
            write(directory / "dispatched.json", {"timeout_seconds": 180})
            write(directory / "outcome.json", {"status": "returned", "dispatched": True})
            write(directory / "raw.json", {"prompt_tokens": 10, "completion_tokens": 2,
                                           "inference_seconds": 0.1, "usage_complete": True, "usage_mode": mode})
            dispatched += 1
    write(root / "manifest.json", {"cases": tasks, "live_inference": live,
                                    "study_kind": "prospective_development_pilot" if live else "scripted_cpu_campaign",
                                    "automatic_formal_expansion": False})
    write(root / "config.json", {"models": {"actor": "actor", "monitor": "monitor"}, "seed": 20261103})
    write(root / "summary.json", {"cases": rows, "formal_test_cases": 0, "dispatched_calls": dispatched,
                                   "monitoring_admitted_count": 2, "close_reason": "bounded campaign",
                                   "automatic_formal_expansion": False})
    write(root / "closed.json", {"closed": True, "retry_allowed": False})
    return tasks, rows


class PilotReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.run = self.base / "run"
        self.tasks, self.rows = make_run(self.run)

    def test_all_manifest_tasks_retained_and_end_is_not_success(self):
        result = reporter.build_report(self.run)
        self.assertEqual(result["all_task_denominator"], 4)
        self.assertEqual(result["formal_test_cases"], 0)
        self.assertEqual(result["collection"]["normally_ended"], 2)
        self.assertEqual(result["collection"]["monitoring_admitted"], 2)
        self.assertEqual(result["collection"]["collection_inference_unattempted"], 1)
        self.assertEqual(result["references"]["unknown_or_unrecorded"], 1)
        self.assertEqual(result["executions"]["zero_action_negative"], 2)
        self.assertEqual(result["executions"]["sensitive_execution"], 1)
        self.assertNotIn("task_success_rate", result)
        self.assertIn("never objective achievement", result["collection"]["meaning"])
        self.assertEqual(result["monitoring"]["arms"]["T"]["not_admitted_to_monitoring"], 2)
        self.assertEqual(result["monitoring"]["arms"]["T"]["technical_failure_among_admitted"], 0)

    def test_reference_unknown_does_not_become_zero_action_negative(self):
        path = self.run / "private/c0000.collection.json"
        original = reporter.read_json(path)
        original["reference"] = {"status": "reference_unknown", "label": None,
                                 "sensitive_execution": False, "committed_events": 0,
                                 "unknown_reasons": ["missing execution state"]}
        write(path, original)
        result = reporter.build_report(self.run)
        self.assertEqual(result["references"]["unknown_or_unrecorded"], 2)
        self.assertEqual(result["executions"]["zero_action_negative"], 1)
        self.assertIsNone(result["development_diagnostics"]["primary_effect_T_minus_F_environment_equal_weight"])

    def test_abstention_and_actual_followup_pair_counts_are_distinct(self):
        rows = deepcopy(self.rows)
        rows[1]["arms"]["T"].update(status="unknown", score=None)
        rows[0]["arms"]["T"]["followup_performed"] = False
        summary = reporter.read_json(self.run / "summary.json")
        summary["cases"] = rows
        write(self.run / "summary.json", summary)
        for i, row in enumerate(rows):
            write(self.run / f"c{i:04d}.result.json", row)
        result = reporter.build_report(self.run)
        self.assertEqual(result["monitoring"]["F_T_valid_pairs_including_abstention"], 2)
        self.assertEqual(result["monitoring"]["F_T_numeric_pairs"], 1)
        self.assertEqual(result["monitoring"]["F_T_numeric_pairs_with_both_followups"], 0)
        self.assertEqual(result["monitoring"]["arms"]["T"]["abstention"], 1)

    def test_unknown_usage_is_not_zero_and_caps_do_not_prove_equal_cost(self):
        rows = deepcopy(self.rows)
        rows[0]["arms"]["T"]["costs"].append(cost(complete=False))
        summary = reporter.read_json(self.run / "summary.json")
        summary["cases"] = rows
        write(self.run / "summary.json", summary)
        write(self.run / "c0000.result.json", rows[0])
        (self.run / "calls/c0000.T.judge/raw.json").unlink()
        result = reporter.build_report(self.run)
        comparison = result["cost"]["F_T_cost_comparability"]
        self.assertFalse(comparison["comparison_available"])
        self.assertIsNone(comparison["actual_T_over_F_time"])
        self.assertTrue(comparison["caps_are_not_measurements"])
        self.assertEqual(result["call_ledger"]["unknown_usage_dispatched_slots"], ["c0000.T.judge"])

    def test_known_pre_inference_rejection_overrides_dispatch_marker(self):
        path = self.run / "calls/c0000.T.judge/outcome.json"
        write(path, {"status": "invalid", "dispatched": False, "worker_request_sent": True})
        result = reporter.build_report(self.run)
        self.assertEqual(result["call_ledger"]["known_not_dispatched_slots"], 1)
        self.assertFalse(result["cost"]["F_T_cost_comparability"]["comparison_available"])
        self.assertIn("Summary dispatched_calls differs", " ".join(result["integrity_or_completeness_issues"]))

    def test_fixture_provenance_and_usage_cannot_become_natural(self):
        other = self.base / "fixture"
        make_run(other, live=False)
        result = reporter.build_report(other)
        self.assertEqual(result["collection"]["natural_actor_records"], 0)
        self.assertFalse(result["cost"]["F_T_cost_comparability"]["measured_native_usage"])
        self.assertFalse(result["cost"]["F_T_cost_comparability"]["comparison_available"])

    def test_missing_closed_receipt_is_not_proof_process_ended(self):
        (self.run / "closed.json").unlink()
        result = reporter.build_report(self.run)
        self.assertFalse(result["closure_confirmed_by_artifact"])
        self.assertFalse(result["cost"]["F_T_cost_comparability"]["comparison_available"])

    def test_output_is_new_outside_directory_and_original_bytes_unchanged(self):
        before = reporter.file_hashes(self.run)
        output = self.base / "report"
        result = reporter.write_report(self.run, output)
        self.assertTrue(result["raw_artifacts_unchanged"])
        self.assertEqual(before, reporter.file_hashes(self.run))
        self.assertTrue((output / "REPORT.md").exists())
        with self.assertRaises(FileExistsError):
            reporter.write_report(self.run, output)
        with self.assertRaisesRegex(ValueError, "outside"):
            reporter.write_report(self.run, self.run / "report")

    def test_duplicate_or_conflicting_results_are_not_silently_selected(self):
        summary = reporter.read_json(self.run / "summary.json")
        summary["cases"].append(deepcopy(summary["cases"][0]))
        write(self.run / "summary.json", summary)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reporter.build_report(self.run)

    def test_cli_writes_report_without_dispatch(self):
        output = self.base / "cli_report"
        reporter.main(["--run", str(self.run), "--output", str(output)])
        result = reporter.read_json(output / "report.json")
        self.assertEqual(result["formal_test_cases"], 0)
        self.assertEqual(len(result["cases"]), 4)

    def test_real_campaign_artifact_layout_with_fake_backend_only(self):
        from prospective_monitoring.campaign import run_campaign
        from prospective_monitoring.test_campaign import Factory, collector, tasks
        directory = self.base / "actual_fixture_campaign"
        summary = run_campaign(tasks(2), directory, Factory(), collector)
        result = reporter.build_report(directory)
        self.assertEqual(result["all_task_denominator"], 2)
        self.assertEqual(result["call_ledger"]["dispatched_calls"], summary["dispatched_calls"])
        self.assertEqual(result["monitoring"]["F_T_numeric_pairs"], 2)
        self.assertEqual(result["collection"]["natural_actor_records"], 0)
        self.assertEqual(result["integrity_or_completeness_issues"], [])
        self.assertIsNone(result["development_diagnostics"]["primary_effect_T_minus_F_environment_equal_weight"])

    def test_model_start_failure_reports_all_unattempted_cases(self):
        from prospective_monitoring.campaign import run_campaign
        from prospective_monitoring.test_campaign import Factory, collector, tasks
        class StartupFailure(Factory):
            def __call__(self, which, remaining_seconds):
                raise RuntimeError("scripted startup failure; no model was loaded")
        directory = self.base / "startup_failure_campaign"
        run_campaign(tasks(3), directory, StartupFailure(), collector)
        result = reporter.build_report(directory)
        self.assertEqual(result["all_task_denominator"], 3)
        self.assertEqual(result["collection"]["collection_inference_unattempted"], 3)
        self.assertEqual(result["call_ledger"]["dispatched_calls"], 0)
        self.assertEqual(result["references"]["unknown_or_unrecorded"], 3)
        self.assertEqual(result["monitoring"]["arms"]["T"]["not_admitted_to_monitoring"], 3)
        self.assertEqual(result["monitoring"]["arms"]["T"]["technical_failure_among_admitted"], 0)
        self.assertIsNone(result["development_diagnostics"])


if __name__ == "__main__":
    unittest.main()
