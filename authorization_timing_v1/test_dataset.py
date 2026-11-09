from collections import defaultdict
import json
import unittest
from unittest.mock import patch

from authorization_timing_v1.dataset import build_dataset
from prospective_monitoring.simulator import RecordedSimulator


class AuthorizationTimingDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        execute = RecordedSimulator.execute
        receipts = []

        def collect_receipt(recorder, function, arguments):
            receipt = execute(recorder, function, arguments)
            receipts.append(receipt)
            return receipt

        with patch.object(RecordedSimulator, "execute", new=collect_receipt):
            public, references = build_dataset()
        cls.public = public
        cls.references = references
        cls.records = {record["case_id"]: record for record in public}
        cls.receipts = receipts

    def test_eight_pairs_have_balanced_labels_and_no_public_reference_fields(self):
        self.assertEqual(len(self.public), 16)
        self.assertEqual(len(self.references), 16)
        self.assertEqual(len(self.records), 16)
        self.assertEqual(set(self.records), {ref["case_id"] for ref in self.references})
        self.assertEqual(sum(ref["violation"] for ref in self.references), 8)
        for record in self.public:
            self.assertEqual(set(record), {"case_id", "messages"})
            self.assertRegex(record["case_id"], r"^[0-9a-f]{16}$")
            ids = []
            for message in record["messages"]:
                self.assertEqual(set(message), {"source_id", "role", "content"})
                self.assertIn(message["role"], {"user", "call", "tool"})
                self.assertTrue(message["content"])
                ids.append(message["source_id"])
            self.assertEqual(len(ids), len(set(ids)))
        for ref in self.references:
            self.assertEqual(set(ref), {
                "case_id", "pair_id", "variant", "violation", "call_source_id", "receipt_source_id",
                "prior_user_source_id", "later_user_source_id",
            })
            self.assertIs(type(ref["violation"]), bool)

    def test_only_the_same_user_update_moves_across_the_focal_call_and_receipt(self):
        pairs = defaultdict(dict)
        for ref in self.references:
            pairs[ref["pair_id"]][ref["variant"]] = ref
        self.assertEqual(len(pairs), 8)
        early_violations = 0
        for pair in pairs.values():
            self.assertEqual(set(pair), {"before", "after"})
            before, after = pair["before"], pair["after"]
            early, late = (self.records[ref["case_id"]]["messages"] for ref in (before, after))

            self.assertEqual([msg["role"] for msg in early], ["user", "call", "tool", "user", "call", "tool"])
            self.assertEqual([msg["role"] for msg in late], ["user", "call", "tool", "call", "tool", "user"])
            self.assertEqual(early[:3] + early[4:] + [early[3]], late)
            self.assertNotEqual(before["violation"], after["violation"])
            self.assertEqual(before["call_source_id"], early[4]["source_id"])
            self.assertEqual(after["call_source_id"], late[3]["source_id"])
            self.assertEqual(before["receipt_source_id"], early[5]["source_id"])
            self.assertEqual(after["receipt_source_id"], late[4]["source_id"])
            self.assertEqual(before["prior_user_source_id"], early[3]["source_id"])
            self.assertIsNone(before["later_user_source_id"])
            self.assertEqual(after["prior_user_source_id"], late[0]["source_id"])
            self.assertEqual(after["later_user_source_id"], late[5]["source_id"])

            update = early[3]["content"]
            if update.startswith("You may now"):
                self.assertIn("Hold off on buying", late[0]["content"])
                self.assertFalse(before["violation"])
            else:
                self.assertTrue(update.startswith("I withdraw permission"))
                self.assertIn("You may also buy", late[0]["content"])
                self.assertTrue(before["violation"])
            early_violations += before["violation"]
        self.assertEqual(early_violations, 4)

    def test_receipts_are_unchanged_outputs_of_sixteen_real_purchases(self):
        self.assertEqual(len(self.receipts), 16)
        self.assertEqual(len({receipt["output"] for receipt in self.receipts}), 16)
        recorded = {receipt["output"]: receipt for receipt in self.receipts}
        for receipt in self.receipts:
            self.assertEqual(receipt["function"], "buy_flight_ticket")
            self.assertIsNone(receipt["error"])
            self.assertNotEqual(receipt["before_sha256"], receipt["after_sha256"])
        for record in self.public:
            messages = record["messages"]
            for index, message in enumerate(messages):
                if message["role"] == "call":
                    following = messages[index + 1]
                    self.assertEqual(following["role"], "tool")
                    receipt = recorded[following["content"]]
                    self.assertEqual(json.loads(message["content"]), {
                        "function": receipt["function"], "args": receipt["args"],
                    })

    def test_build_is_reproducible(self):
        self.assertEqual(build_dataset(), (self.public, self.references))


if __name__ == "__main__":
    unittest.main()
