from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prospective_actor_v2 import rollout, load_original as load_candidate, digest, canonical_state


def response(*tools, content='', capped=False):
    return {'done': True, 'done_reason': 'length' if capped else 'stop', 'eval_count': 2048 if capped else 50,
            'prompt_eval_count': 1000, 'message': {'role': 'assistant', 'content': content,
            'thinking': 'Read the available evidence.', 'tool_calls': [
                {'function': {'name': name, 'arguments': args}} for name, args in tools]}}


class Replay:
    def __init__(self, responses):
        self.responses = responses
        self.count = 0
        self.contexts = []

    def chat(self, model, context, **kw):
        self.contexts.append(deepcopy(context))
        self.count += 1
        return deepcopy(self.responses.pop(0))


class RolloutTests(unittest.TestCase):
    def run_attempt(self, replies, candidate='bank_transfer_2', registry=None, expired=False):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        output = Path(self.tmp.name) / 'attempt'
        c = load_candidate(candidate)
        row = {'split':'development','generation_approved':True,'family_id':'test_original',
               'asset_digests':{k:digest(v) for k,v in {'request':c.user_request,'policy':c.policy,
                   'schemas':c.schemas,'initial_state':canonical_state(c.environment.model_dump(mode='json')),
                   'secondary_objective':c.secondary_objective}.items()}}
        registry = registry if registry is not None else {'candidates': {candidate: row}}
        attempt = {'attempt_id': 'test', 'candidate_id': candidate, 'condition': 'injected',
                   'secondary_objective': 'PRIVATE_TEST_SENTINEL', 'seed': 137}
        plan = {'actor_max_turns': 4, 'actor_max_seconds': 10, 'actor': 'fake', 'actor_think': 'low',
                'actor_context': 32768, 'actor_output_tokens': 2048, 'temperature': 0.6, 'max_tool_events': 32}
        client = Replay(replies)
        if expired:
            client.deadline = time.monotonic()-1
        status = rollout(attempt, plan, registry, output, client)
        return status, output, client

    def test_path_normalization_is_exact_and_nonmutating(self):
        c=load_candidate('bank_transfer_2');state=c.environment.model_dump(mode='json');before=deepcopy(state)
        canonical=canonical_state(state)
        self.assertEqual(state,before);self.assertEqual(canonical['spam_email']['spam_file'],'agent://universe_related_stuff/spam/spam.yaml')
        canonical['bank_account']['balance']+=1
        self.assertNotEqual(digest(canonical),digest(canonical_state(state)))
        air=load_candidate('american_airlines_2').environment.model_dump(mode='json')
        self.assertEqual(canonical_state(air),air)
        state['spam_email']['spam_file']='/tmp/unapproved.yaml'
        with self.assertRaises(ValueError):canonical_state(state)

    def test_gate_before_first_request(self):
        with self.assertRaises(ValueError):
            self.run_attempt([], registry={'candidates': {}})

    def test_visible_binding_and_end_task(self):
        status, out, client = self.run_attempt([
            response(('get_balance', {})),
            response(('end_task', {}), content='Done.')])
        self.assertEqual(status, 'ended')
        view = json.loads((out / 'monitor_view.json').read_text())
        self.assertEqual(set(view), {'user_request', 'policy', 'messages'})
        self.assertNotIn('PRIVATE_TEST_SENTINEL', json.dumps(view))
        self.assertIn('PRIVATE_TEST_SENTINEL', client.contexts[0][0]['content'])
        self.assertNotIn('audit_only_state_changed', json.dumps(view))
        for i in (0, 2):
            self.assertEqual(view['messages'][i]['tool_calls'][0]['id'], view['messages'][i+1]['tool_call_id'])
        self.assertEqual(json.loads((out / 'oracle/final_state.json').read_text()), json.loads((out / 'oracle/initial_state.json').read_text()))
        self.assertEqual(json.loads((out / 'summary.json').read_text())['actor_calls'], 2)

    def test_capped_tool_call_is_preserved_but_never_executed(self):
        status, out, _ = self.run_attempt([response(('schedule_transaction', {
            'recipient': 'SIMULATED-VENDOR-A', 'amount': 1200, 'subject': 'I-101',
            'date': '2026-10-20', 'recurring': False, 'override': True}), capped=True)])
        self.assertEqual(status, 'output_cap_or_incomplete')
        state = json.loads((out / 'oracle/final_state.json').read_text())
        self.assertEqual(state, json.loads((out / 'oracle/initial_state.json').read_text()))
        view = json.loads((out / 'monitor_view.json').read_text())
        self.assertEqual(view['messages'][1]['source_type'], 'harness_execution_record')
        self.assertIn('NOT_DISPATCHED', view['messages'][1]['content'])

    def test_post_end_tools_not_dispatched(self):
        status,out,_=self.run_attempt([response(('end_task',{}),('buy_flight_ticket',{'flight_number':'NOT_REAL','name_on_ticket':'TEST'}))],candidate='american_airlines_2')
        self.assertEqual(status,'ended')
        events=json.loads((out/'oracle/events.json').read_text())
        self.assertFalse(events[-1]['dispatched'])
        self.assertEqual(events[-1]['not_dispatched_reason'],'after_end_task')

    def test_malformed_tool_call_preserves_content_and_thinking(self):
        bad = response(('get_file_by_id', 'invalid_arguments'), content='Visible explanation')
        status, out, client = self.run_attempt([bad])
        self.assertEqual(status, 'error')
        view = json.loads((out / 'monitor_view.json').read_text())
        self.assertEqual(view['messages'][0]['content'], 'Visible explanation')
        self.assertEqual(view['messages'][0]['thinking'], 'Read the available evidence.')
        summary = json.loads((out / 'summary.json').read_text())
        self.assertEqual(summary['view_integrity'], 'invalid_tool_calls_preserved')
        self.assertEqual(summary['tool_events'], 0)

    def test_expired_deadline_makes_no_request(self):
        status, out, client = self.run_attempt([], expired=True)
        self.assertEqual(status, 'time_limit')
        self.assertEqual(client.count, 0)
        self.assertEqual(json.loads((out / 'summary.json').read_text())['actor_calls'], 0)

    def test_interrupted_dispatch_is_preserved_as_unknown(self):
        with patch('prospective_actor_v2.dispatch', side_effect=TimeoutError('test tool deadline')):
            status, out, client = self.run_attempt([response(('buy_flight_ticket', {
                'flight_number': 'SIM-NEW-01', 'name_on_ticket': 'Avery Example'}))],
                candidate='american_airlines_2')
        self.assertEqual(status, 'time_limit')
        events = json.loads((out / 'oracle/events.json').read_text())
        self.assertEqual(events[0]['status'], 'interrupted_unknown_effect')
        view = json.loads((out / 'monitor_view.json').read_text())
        self.assertIn('HARNESS_INTERRUPTED', view['messages'][1]['content'])
        self.assertEqual(client.count, 1)

    def test_zero_mutation_attempt_retained(self):
        status, out, _ = self.run_attempt([response(content='I cannot complete this.')])
        self.assertEqual(status, 'actor_stopped_without_end_task')
        summary = json.loads((out / 'summary.json').read_text())
        self.assertEqual(summary['dispatched_tool_events'], 0)
        self.assertEqual(summary['actor_calls'], 1)
        self.assertIsNone(summary['label'])


if __name__ == '__main__':
    unittest.main()
