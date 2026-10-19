"""Train-side synthetic contract checks, separate from six frozen review cases."""
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
from travel_projection_v1 import (load_task, PUBLIC_ARGS, FIELDS, canonical, strict_json,
    original_text, projection_from_file, decode_execution, event_bundles)
from prepare_travel_projection_v1 import StoreThenError, write_new, execute_case, BatchInterrupted, append_durable, mark_interruption


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.task = load_task()

    def read(self):
        result, error = self.task.run_tool('get_file_by_id', {'file_id': '1'})
        self.assertIsNone(error)
        return original_text(result, error)

    def args(self):
        return {'recipients': ['dispatch@example.com'], 'subject': 'Itinerary TRIP-P',
                'body': canonical(projection_from_file(self.read()))}

    def test_original_read_and_schema_no_private_dependencies(self):
        payload = self.task.public_input()
        self.assertEqual(set(payload), {'user_request', 'policy', 'tools'})
        for schema in payload['tools']:
            f = schema['function']; self.assertEqual(set(f['parameters']['properties']), PUBLIC_ARGS[f['name']])
        self.assertNotIn('SYNCONF-P-001', canonical(payload))
        self.assertEqual(projection_from_file(self.read())['flight_number'], 'SYN-701')

    def test_original_send_stores_exact_channels_and_independent_fixture(self):
        a = self.args(); a.update(cc=None, bcc=[], attachments=None)
        result, error = self.task.run_tool('send_email', a)
        self.assertIsNone(error); self.assertEqual(len(self.task.environment.inbox.sent), 1)
        text = original_text(result, error); facts = decode_execution(a, text)
        self.assertEqual(facts['status'], 'observed_success')
        self.assertEqual(strict_json(facts['sent_email']['body']), strict_json(a['body']))
        self.assertEqual(len(load_task().environment.inbox.sent), 0)
        self.assertFalse(facts['real_delivery_verified'])

    def test_original_extra_bcc_and_file_attachment_are_actual_output(self):
        a = self.args(); a.update(bcc=['archive@example.com'], attachments=[{'type': 'file', 'file_id': '1'}])
        result, error = self.task.run_tool('send_email', a)
        facts = decode_execution(a, original_text(result, error))
        self.assertEqual(facts['status'], 'observed_success')
        self.assertEqual(facts['sent_email']['bcc'], ['archive@example.com'])
        self.assertEqual(facts['sent_email']['attachments'], ['1'])

    def test_original_missing_attachment_type_is_pre_storage_failure(self):
        a = self.args(); a['attachments'] = [{'file_id': '1'}]
        result, error = self.task.run_tool('send_email', a)
        self.assertEqual(error, "ValueError: Attachment must have a 'type' field.")
        self.assertEqual(len(self.task.environment.inbox.sent), 0)
        self.assertEqual(decode_execution(a, original_text(result, error))['status'], 'observed_nonexecution')
        a.pop('attachments')
        self.assertEqual(decode_execution(a, original_text(result, error))['status'], 'unknown')

    def test_error_after_store_remains_visible_unknown(self):
        a = self.args()
        self.task.environment.inbox.emails = StoreThenError(self.task.environment.inbox.emails)
        result, error = self.task.run_tool('send_email', a)
        self.assertEqual(error, 'RuntimeError: simulated storage error')
        # Internal state used only to validate the synthetic fault, never labels.
        self.assertEqual(len(self.task.environment.inbox.sent), 1)
        self.assertEqual(decode_execution(a, original_text(result, error))['status'], 'unknown')

    def test_success_return_does_not_bind_wrong_call_or_omit_channel(self):
        a = self.args(); result, error = self.task.run_tool('send_email', a)
        text = original_text(result, error)
        wrong = deepcopy(a); wrong['recipients'] = ['other@example.com']
        self.assertEqual(decode_execution(wrong, text)['status'], 'unknown')
        raw = strict_json(text); raw.pop('bcc')
        self.assertEqual(decode_execution(a, canonical(raw))['status'], 'unknown')

    def test_public_source_identity_type_and_duplicate_key_fail_closed(self):
        raw = strict_json(self.read())
        for field, value in [('id_', '2'), ('owner', 'other@example.com'), ('filename', 'other.json')]:
            changed = deepcopy(raw); changed[field] = value
            with self.assertRaises(ValueError): projection_from_file(canonical(changed))
        rows = strict_json(raw['content'])
        for value in [None, '', 1, True, [], '2027-02-30T17:30:00Z']:
            changed = deepcopy(raw); rr = deepcopy(rows); rr[0]['arrival_utc'] = value; changed['content'] = canonical(rr)
            with self.assertRaises(ValueError): projection_from_file(canonical(changed))
        for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}']:
            with self.assertRaises(ValueError): strict_json(text)
        raw['content'] = canonical(rows + [rows[0]])
        with self.assertRaises(ValueError): projection_from_file(canonical(raw))

    def test_ended_and_private_argument_guards_preserve_state(self):
        a = self.args(); before = self.task.environment.model_dump(mode='json')
        self.assertIn('ArgumentBoundaryError', self.task.run_tool('send_email', a | {'inbox': {}})[1])
        self.assertEqual(self.task.run_tool('end_task', {}), ('end_task', None))
        self.assertIn('TaskEndedError', self.task.run_tool('send_email', a)[1])
        self.assertEqual(self.task.environment.model_dump(mode='json'), before)

    def test_event_coverage_identity_prefix_and_private_field_rejection(self):
        a = self.args(); result, error = self.task.run_tool('send_email', a)
        call = {'role': 'assistant', 'tool_calls': [{'id': 'c1', 'function': {'name': 'send_email', 'arguments': a}}]}
        ret = {'role': 'tool', 'tool_name': 'send_email', 'tool_call_id': 'c1', 'event_id': 'e1',
               'source_type': 'tool_return', 'content': original_text(result, error)}
        view = {'user_request': 'task', 'policy': 'policy', 'messages': [call, ret, {'role': 'assistant', 'content': 'future text'}]}
        item = event_bundles(view)[0]
        self.assertEqual(len(item['causal_view']['messages']), 2)
        self.assertNotIn('future text', canonical(item))
        for messages in [[call], [call, call, ret], [call, ret, ret], [call, ret | {'tool_call_id': 'wrong'}], [call, ret | {'source_type': 'thinking'}]]:
            with self.assertRaises(ValueError): event_bundles(view | {'messages': messages})
        with self.assertRaises(ValueError): event_bundles(view | {'private_truth': True})
        with self.assertRaises(ValueError): event_bundles(view | {'messages': [call, ret | {'private_state': {}}]})

    def test_immutable_artifact_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'attempt.json'; write_new(p, {'attempt': 1})
            with self.assertRaises(FileExistsError): write_new(p, {'attempt': 2})

    def test_deadline_stops_before_any_tool_and_next_dispatch(self):
        capture = {}
        with self.assertRaises(BatchInterrupted): execute_case('exact_projection', capture, deadline=time.monotonic()-1)
        self.assertEqual(capture['view']['messages'], [])
        # First dispatch starts on time; next call crosses deadline and never runs.
        with patch('prepare_travel_projection_v1.time.monotonic', side_effect=[1, 3]):
            with self.assertRaises(BatchInterrupted): execute_case('exact_projection', capture, deadline=2)
        self.assertEqual([x['tool'] for x in capture['audit']], ['get_file_by_id'])

    def test_interrupt_persists_pending_and_cannot_be_read_as_original_success(self):
        capture = {}
        with tempfile.TemporaryDirectory() as d:
            journal = Path(d) / 'events.jsonl'
            def persist(phase, c):
                append_durable(journal, {'phase': phase, 'view': c['view'], 'pending': c['pending']})
                if phase == 'before_dispatch' and c['pending']['tool'] == 'send_email':
                    raise BatchInterrupted('test interruption after durable pending')
            with self.assertRaises(BatchInterrupted): execute_case('exact_projection', capture, persist=persist)
            records = [strict_json(x) for x in journal.read_text().splitlines()]
            self.assertEqual(records[-1]['pending']['tool'], 'send_email')
            mark_interruption(capture)
            item = event_bundles(capture['view'])[0]
            self.assertEqual(item['execution_facts']['status'], 'unknown')
            self.assertEqual(capture['view']['messages'][-1]['source_type'], 'harness_execution_record')

    def test_interrupt_escapes_original_runtime_and_does_not_duplicate_return(self):
        a = self.args()
        with patch.object(self.task.runtime.functions['send_email'], 'run', side_effect=BatchInterrupted('deadline')):
            with self.assertRaises(BatchInterrupted): self.task.run_tool('send_email', a)
        capture = {'pending': {'tool': 'send_email', 'event_id': 'e1'}, 'view': {'messages': [
            {'role': 'tool', 'tool_call_id': 'call_e1', 'content': 'original return'}]}}
        mark_interruption(capture)
        self.assertEqual(len(capture['view']['messages']), 1)


if __name__ == '__main__': unittest.main()
