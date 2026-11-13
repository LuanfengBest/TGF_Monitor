import unittest
from copy import deepcopy

from .run import public_cases, states


class Smoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = dict(public_cases())

    def test_public_batch(self):
        self.assertEqual(len(self.records), 189)
        for record in self.records.values():
            arms = states(record)
            self.assertEqual(arms["raw"]["record"], arms["agv"]["record"])
            self.assertEqual(arms["ledger"]["fact_ledger"], arms["agv"]["fact_ledger"])

    def test_reject_label(self):
        record = next(iter(self.records.values()))
        with self.assertRaises(ValueError):
            states(dict(record, label="violation"))

    def test_later_permission_and_missing_receipt(self):
        for record in self.records.values():
            graph = states(record)["agv"]["authorization_checks"]
            for check in graph["booking_checks"]:
                if "exact_passenger_match" not in check:
                    continue
                revised = deepcopy(record)
                permission = next(m for m in revised["messages"] if m["source_id"] == check["candidate_permission"])
                revised["messages"].remove(permission)
                revised["messages"].append(permission)
                def find_check(r):
                    return next(c for c in states(r)["agv"]["authorization_checks"]["booking_checks"]
                                if c["call"] == check["call"])
                self.assertNotEqual(find_check(revised)["candidate_permission"], permission["source_id"])
                revised = deepcopy(record)
                revised["messages"] = [m for m in revised["messages"] if m["source_id"] != check["receipt"]]
                self.assertNotIn("exact_passenger_match", find_check(revised))
                return
        self.fail("No covered booking in public batch")
