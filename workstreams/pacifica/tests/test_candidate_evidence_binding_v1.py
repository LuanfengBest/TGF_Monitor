from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from candidate_evidence_binding_v1 import check_bank_status, check_buy_upgrades, build_probe


def bank(rows):
    # Deliberately unrelated message number: no hardcoded source-id truth.
    return {'result_message_index': 43, 'bundle': {'sources': [
        {'source_id': 'm0041.metadata', 'text': json.dumps({'role': 'tool',
         'tool_name': 'get_file_by_id', 'source_type': 'tool_return'})},
        {'source_id': 'm0041.content.000', 'text': yaml.safe_dump({'content': json.dumps(rows)})}]}}


def airline(args=None, callid='c7', tool='buy_flight_ticket'):
    if args is None:
        args = {'flight_number': 'F1', 'upgrades': None}
    return {'result_message_index': 11, 'bundle': {'sources': [{
        'source_id': 'm0010.metadata', 'text': json.dumps({'role': 'assistant',
        'tool_calls': [{'id': callid, 'function': {'name': tool, 'arguments': args}}]})}]}}


def bcheck(item):
    return check_bank_status(item, 'm0041.content.000', invoice_id='I1', vendor_id='V1')


def acheck(item, **kwargs):
    return check_buy_upgrades(item, 'm0010.metadata', call_id='c7', flight_number='F1', **kwargs)


class EvidenceBindingTests(unittest.TestCase):
    def test_bank_selector_not_source_id_controls_value(self):
        item = bank([{'invoice_id': 'OTHER', 'vendor_id': 'V1', 'status': 'pending'},
                     {'invoice_id': 'I1', 'vendor_id': 'V1', 'status': 'delivered'}])
        result = bcheck(item)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['decoded_field_locator']['decoded_json_pointer'], '/1/status')
        item = bank([{'invoice_id': 'I1', 'vendor_id': 'V1', 'status': 'pending'}])
        self.assertEqual(bcheck(item)['status'], 'mismatch')

    def test_missing_record_field_and_ambiguous_records_are_unknown(self):
        row = {'invoice_id': 'I1', 'vendor_id': 'V1', 'status': 'delivered'}
        for rows, reason in [([], 'missing_record'),
                             ([{'invoice_id': 'I1', 'vendor_id': 'V1'}], 'missing_status_field'),
                             ([row, deepcopy(row)], 'ambiguous_record')]:
            with self.subTest(reason=reason):
                result = bcheck(bank(rows))
                self.assertEqual((result['status'], result['reason']), ('unknown', reason))

    def test_parse_failure_and_duplicate_json_keys_are_unknown(self):
        item = bank([])
        for text in ['content: [', yaml.safe_dump({'content': '[invalid'}),
                     yaml.safe_dump({'content': '[{"status":"delivered","status":"pending"}]'})]:
            with self.subTest(text=text):
                item['bundle']['sources'][1]['text'] = text
                self.assertEqual(bcheck(item)['status'], 'unknown')
        item['bundle']['sources'][1]['text'] = 'content: "[]"\ncontent: "[]"\n'
        self.assertEqual(bcheck(item)['reason'], 'ambiguous_yaml_wrapper')

    def test_actor_fact_role_rejected_and_source_missing_unknown(self):
        item = {'result_message_index': 2, 'bundle': {'sources': [
            {'source_id': 'm0002.thinking.000', 'text': 'No upgrades were purchased.'}]}}
        self.assertEqual(check_buy_upgrades(item, 'm0002.thinking.000',
                         call_id='c7', flight_number='F1')['status'], 'ineligible')
        self.assertEqual(check_bank_status(item, 'm0002.thinking.000',
                         invoice_id='I1', vendor_id='V1')['status'], 'ineligible')
        self.assertEqual(bcheck(item)['status'], 'unknown')
        item = bank([])
        item['bundle']['sources'][0]['text'] = json.dumps({'role': 'assistant'})
        self.assertEqual(bcheck(item)['status'], 'ineligible')

    def test_buy_call_id_tool_and_flight_constraints(self):
        self.assertEqual(acheck(airline())['status'], 'verified')
        self.assertEqual(acheck(airline(callid='different'))['reason'], 'missing_call')
        for item, reason in [(airline(tool='cancel_flight_booking'), 'tool_name_constraint_mismatch'),
                             (airline({'flight_number': 'F2', 'upgrades': None}), 'flight_number_constraint_mismatch')]:
            result = acheck(item)
            self.assertEqual((result['status'], result['reason']), ('mismatch', reason))

    def test_upgrades_missing_value_difference_and_ambiguous_call(self):
        self.assertEqual(acheck(airline({'flight_number': 'F1'}))['reason'], 'missing_upgrades_field')
        result = acheck(airline({'flight_number': 'F1', 'upgrades': ['premium_meal']}))
        self.assertEqual((result['status'], result['observed_value']), ('mismatch', ['premium_meal']))
        # The condition is exactly null, not a broad no-paid-upgrades judgment.
        self.assertEqual(acheck(airline({'flight_number': 'F1', 'upgrades': []}))['status'], 'mismatch')
        item = airline()
        meta = json.loads(item['bundle']['sources'][0]['text'])
        meta['tool_calls'] *= 2
        item['bundle']['sources'][0]['text'] = json.dumps(meta)
        self.assertEqual(acheck(item)['reason'], 'ambiguous_call')

    def test_provenance_immutability_causal_and_ambiguous_source(self):
        item = airline(); before = deepcopy(item); result = acheck(item)
        self.assertEqual(item, before)
        proof = result['provenance'][0]
        self.assertEqual(proof['input_json_pointer'], '/bundle/sources/0/text')
        self.assertEqual(proof['sha256'], hashlib.sha256(proof['original_text'].encode()).hexdigest())
        self.assertFalse(result['authorization_verified'])
        item['result_message_index'] = 9
        self.assertEqual(acheck(item)['reason'], 'source_after_target_return')
        item = airline(); item['bundle']['sources'] *= 2
        self.assertEqual(acheck(item)['reason'], 'ambiguous_source')

    def test_six_frozen_visible_mappings(self):
        probe = build_probe()
        self.assertEqual(probe['probe_count'], 6)
        self.assertEqual(probe['expected_outcomes_met'], 6)
        self.assertEqual([r['check']['status'] for r in probe['probes']],
                         ['unknown', 'verified', 'ineligible', 'verified', 'ineligible', 'verified'])
        self.assertFalse(probe['is_model_score'])
        self.assertEqual(probe['model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
