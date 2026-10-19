from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import travel_monitor_baseline_v1 as runner
import travel_monitor_contract_v1 as contract
import analyze_travel_monitor_baseline_v1 as analysis
from travel_projection_v1 import event_bundles
from native_ollama_tokenizer import NativeCounter

PACKET = ROOT / 'data/annotation_review/travel_projection_cpu_v1'
SCHEMAS = runner.read(ROOT / 'configs/travel_projection_cpu_v1.json')['public_schemas']


def bundle(case='p001'):
    return contract.build_input(runner.read(PACKET / (case + '_causal.json')), SCHEMAS)


def output():
    return {'execution': 'executed', 'authorization': 'supported',
            'executed_unauthorized_in_scope': False, 'authorized_amount': None,
            'observed_amount': None, 'excess_amount': None,
            'evidence': [{'source_id': 'user_request', 'quote': 'TRIP-P'}], 'rationale': 'test'}


class FakeCounter:
    def check(self, *args): return 20


class FakeClient:
    def __init__(self, responses, digest='d'):
        self.responses = list(responses); self.calls = 0; self.digest = digest
    def metadata(self, *args):
        return {'version': {'version': '0.0.0'}, 'tags': {'models': [{'name': 'm', 'digest': self.digest}]}}
    def api(self, *args):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, BaseException): raise r
        return r


def response(raw=None, count=20):
    return {'done': True, 'done_reason': 'stop', 'prompt_eval_count': count,
            'eval_count': 10, 'response': json.dumps(output()) if raw is None else raw}


class InputTests(unittest.TestCase):
    def test_all_six_sources_unchanged_and_common_contract(self):
        for i in range(1, 7):
            b = bundle(f'p{i:03d}')
            view = runner.read(PACKET / f'p{i:03d}_causal.json')
            self.assertEqual(b['sources'], event_bundles(view)[0]['sources'])
            self.assertEqual(b['tool_effect_contract'], contract.TOOL_EFFECT_CONTRACT)
            self.assertEqual(set(b), {'target_action', 'audit_dimensions', 'sources', 'public_tools', 'tool_effect_contract'})
            prompt = contract.render(b)
            for forbidden in ('execution_facts', 'condition_checks', 'training_eligible', 'StoreThenError', 'ai_labels', 'private_reference'):
                self.assertNotIn(forbidden, prompt)

    def test_decoder_poison_never_enters_prompt(self):
        view = runner.read(PACKET / 'p001_causal.json'); item = event_bundles(view)[0]
        item['execution_facts'] = {'status': 'SECRET_REFERENCE_123'}
        item['private_case_name'] = 'SECRET_REFERENCE_456'
        with patch.object(contract, 'event_bundles', return_value=[item]):
            text = contract.render(contract.build_input(view, SCHEMAS))
        self.assertNotIn('SECRET_REFERENCE', text)

    def test_future_and_private_material_rejected(self):
        with self.assertRaises(ValueError):
            contract.build_input(runner.read(PACKET / 'p001.json'), SCHEMAS)
        view = runner.read(PACKET / 'p001_causal.json'); view['label'] = True
        with self.assertRaises(ValueError): contract.build_input(view, SCHEMAS)
        b = bundle(); b['execution_facts'] = {'status': 'observed_success'}
        with self.assertRaises(ValueError): contract.render(b)

    def test_native_capacity_all_six(self):
        counter = NativeCounter()
        for i in range(1, 7):
            self.assertGreater(counter.check(contract.render(bundle(f'p{i:03d}')), 6144), 0)

    def test_strict_parser(self):
        good = json.dumps(output())
        self.assertEqual(contract.parse_response({'response': '<think>ignored</think>' + good}), output())
        for raw in (good.replace('"execution": "executed"', '"execution": "executed", "execution": "uncertain"'),
                    good.replace('"authorized_amount": null', '"authorized_amount": NaN'),
                    good.replace('"executed_unauthorized_in_scope": false', '"executed_unauthorized_in_scope": 0')):
            with self.assertRaises(ValueError): contract.parse_response({'response': raw})

    def test_guard_does_not_credit_false_for_unknown_or_wrong_quote(self):
        b = bundle('p006'); o = output(); o['execution'] = 'uncertain'
        checks = contract.guard(o, b)
        self.assertFalse(checks['internally_consistent'])
        self.assertIn('inconsistent_decision', checks['rejection_reasons'])
        o['executed_unauthorized_in_scope'] = None
        o['evidence'][0]['quote'] = 'not a real citation'
        self.assertFalse(contract.guard(o, b)['citation_exact_matches'][0])

    def test_guard_requires_call_return_and_authority_but_not_semantics(self):
        b = bundle(); o = output()
        self.assertFalse(contract.guard(o, b)['mechanically_accepted'])
        ids = ['user_request', 'm0002.metadata', 'm0003.content']
        o['evidence'] = [{'source_id': s['source_id'], 'quote': s['text'][:24]} for s in b['sources'] if s['source_id'] in ids]
        g = contract.guard(o, b)
        self.assertTrue(g['mechanically_accepted']); self.assertFalse(g['semantically_verified'])


class RuntimeTests(unittest.TestCase):
    def run_fake(self, responses, digest='d', remaining=1000):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name)
        for i in range(3): runner.durable_save(root / f'i{i}.json', bundle())
        p = {'model': 'm', 'model_digest': 'd', 'backend_installation_hashes': {},
             'max_http_seconds': 20, 'max_calls': 3, 'max_consecutive_output_failures': 2,
             'num_predict': 100, 'num_ctx': 32768, 'seed': 42, 'sampling': {},
             'inputs': [{'input_id': f'i{i}', 'path': f'i{i}.json', 'expected_prompt_tokens': 20} for i in range(3)]}
        client = FakeClient(responses, digest)
        with patch.object(runner, 'ROOT', root):
            try: runner.execute(p, root / 'out', client, FakeCounter(), time.monotonic() + remaining)
            except (TimeoutError, ValueError, runner.DiagnosticInterrupted): pass
        return root, runner.read(root / 'out/summary.json'), client

    def test_two_parse_failures_stop_no_retry(self):
        root, s, c = self.run_fake([response('invalid'), response('invalid')])
        self.assertEqual(c.calls, 2); self.assertEqual(s['status'], 'stopped_output_failures')
        self.assertEqual(s['not_attempted'], ['i2'])
        self.assertTrue((root / 'out/calls/i0_response.json').exists())

    def test_transport_failure_preserved_with_unknown_usage(self):
        root, s, c = self.run_fake([TimeoutError('test transport')])
        self.assertEqual(c.calls, 1); self.assertEqual(s['status'], 'failed')
        self.assertTrue(s['calls'][0]['final_usage_unknown'])
        self.assertTrue((root / 'out/calls/i0_request.json').exists())
        self.assertTrue((root / 'out/calls/i0_error.json').exists())

    def test_signal_interruption_is_not_output_failure_and_no_retry(self):
        root, s, c = self.run_fake([runner.DiagnosticInterrupted('test signal')])
        self.assertEqual(c.calls, 1); self.assertEqual(s['status'], 'failed')
        self.assertEqual(s['calls'][0]['status'], 'transport_or_interruption')
        self.assertEqual(s['not_attempted'], ['i1', 'i2'])

    def test_count_mismatch_preserves_raw_usage_and_stops(self):
        root, s, c = self.run_fake([response(count=21)])
        self.assertEqual(c.calls, 1); self.assertEqual(s['status'], 'failed')
        self.assertEqual(s['calls'][0]['prompt_eval_count'], 21)
        self.assertEqual(s['calls'][0]['status'], 'input_count_mismatch')
        self.assertTrue((root / 'out/calls/i0_response.json').exists())

    def test_wrong_identity_stops_before_generate(self):
        root, s, c = self.run_fake([], digest='wrong')
        self.assertEqual(c.calls, 0); self.assertEqual(s['status'], 'failed')

    def test_budget_stop_before_dispatch(self):
        root, s, c = self.run_fake([], remaining=2)
        self.assertEqual(c.calls, 0); self.assertEqual(s['status'], 'budget_stop')

    def test_reservation_refuses_second_run(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name)
        cfg = root / 'plan.json'; runner.durable_save(cfg, {'test': True})
        reserve = root / 'reservation.json'; runner.durable_save(reserve, {'prior': True}, exclusive=True)
        with patch.object(runner, 'verify', return_value={}), patch.object(runner, 'PLAN', cfg), patch.object(runner, 'RESERVATION', reserve):
            with self.assertRaises(FileExistsError): runner.run(root / 'never_created')
        self.assertFalse((root / 'never_created').exists())


class AnalysisTests(unittest.TestCase):
    def test_missing_and_failed_calls_remain_in_denominator_and_costs(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name)
        p = {'model': 'm', 'model_digest': 'd', 'num_ctx': 32768, 'num_predict': 100,
             'seed': 42, 'sampling': {}, 'max_calls': 6, 'inputs': []}
        refs = {}
        flags = [False, True, True, True, False, None]
        for i, flag in enumerate(flags, 1):
            iid = f'p{i:03d}'; runner.durable_save(root / (iid + '.json'), bundle(iid))
            p['inputs'].append({'input_id': iid, 'path': iid + '.json', 'expected_prompt_tokens': 20})
            refs[iid] = {'execution': 'executed' if i < 5 else ('not_executed' if i == 5 else 'uncertain'),
                         'authorization': 'conflict' if 2 <= i <= 5 else 'supported', 'executed_unauthorized': flag}
        base = root / 'out'; runner.durable_save(base / 'plan.json', p)
        runner.durable_save(base / 'metadata.json', FakeClient([]).metadata())
        runner.durable_save(base / 'summary.json', {'status': 'failed', 'calls': [{'input_id': 'p001', 'status': 'input_count_mismatch'}]})
        runner.durable_save(base / 'calls/p001_request.json', runner.payload(bundle(), p))
        runner.durable_save(base / 'calls/p001_response.json', response(count=21))
        with patch.object(analysis, 'verify', return_value=p), patch.object(analysis, 'verify_references', return_value={'references': refs}), patch.object(analysis, 'ROOT', root):
            r = analysis.analyze(base)
        self.assertEqual(r['calls'], 1); self.assertEqual(r['known_events'], 5)
        self.assertEqual(r['known_core_correct'], 0); self.assertEqual(r['unknown_reference_agreement'], 0)
        self.assertEqual(r['TPR'], 0); self.assertEqual(r['TNR'], 0)
        self.assertEqual(r['known_prompt_tokens'], 21); self.assertEqual(r['known_completion_tokens'], 10)
        self.assertEqual(r['statuses']['not_attempted'], 5)


if __name__ == '__main__': unittest.main()
