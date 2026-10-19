import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_ollama_tokenizer import NativeCounter
from summarize_costs import summarize


class NativeCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.counter = NativeCounter()

    def test_all_saved_monitor_requests_match_backend(self):
        checked = 0
        for run in ('paired_first_29362188', 'paired_ascii_first_29362895'):
            for path in sorted((ROOT / 'results' / run / 'calls').glob('*_request.json')):
                req = json.loads(path.read_text())
                if 'prompt' not in req:
                    continue
                resp = json.loads(path.with_name(path.name.replace('_request', '_response')).read_text())
                with self.subTest(path=path.name, run=run):
                    self.assertEqual(self.counter.count(req['prompt']), resp['prompt_eval_count'])
                checked += 1
        self.assertEqual(checked, 12)

    def test_actual_ascii_b2_prompt_still_reserves_output_capacity(self):
        path = ROOT / 'results/paired_ascii_first_29362895/calls/call_0008_request.json'
        req = json.loads(path.read_text())
        self.assertEqual(self.counter.check(req['prompt'], 2048), 21527)
        with self.assertRaisesRegex(ValueError, 'no truncation'):
            self.counter.check(req['prompt'], 12000)

    def test_post_response_failure_is_charged_without_transport_error(self):
        costs = summarize(ROOT / 'results/paired_ascii_first_29362895')['by_model']
        self.assertEqual(sum(r['requests'] for r in costs.values()), 8)
        self.assertEqual(sum(r['responses'] for r in costs.values()), 8)
        self.assertEqual(sum(r['post_response_errors'] for r in costs.values()), 1)
        self.assertEqual(sum(r['transport_errors'] for r in costs.values()), 0)


if __name__ == '__main__':
    unittest.main()
