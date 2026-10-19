"""CPU fixture/dispatch contracts only; these are not sampled/annotated trajectories."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from monitor_v2_task_adapters import CANDIDATES, VARIANTS, PUBLIC_ARGS, load_task, require_generation_ready
from prepare_monitor_v2_tasks import prepare_one
from observed_execution_v1 import decode_contract as bank_decode
from observed_airline_execution_v1 import decode_contract as air_decode


class FixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='monitor_v2_contract_')
        cls.dirs = {(name, variant): prepare_one(name, cls.tmp.name, variant)
                    for name in CANDIDATES for variant in VARIANTS[name]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, name, variant='base'):
        return load_task(name, self.dirs[name, variant], variant)

    def doc(self, task, file_id):
        result, error = task.run_tool('get_file_by_id', {'file_id': str(file_id)})
        self.assertIsNone(error)
        return json.loads(result.content)

    def pool_call(self, task, order_id, override=True):
        accounts = {r['account_id']: r['iban'] for r in self.doc(task, 1)}
        order = next(r for r in self.doc(task, 2) if r['order_id'] == order_id)
        return {'recipient': accounts[order['account_id']], 'amount': order['amount_usd'],
                'subject': 'pool=POOL-A;order=' + order_id, 'date': '2026-11-01',
                'recurring': False, 'override': override}

    def test_public_schema_and_payload_are_positive_allowlisted(self):
        for name in CANDIDATES:
            task = self.load(name)
            payload = task.public_input()
            self.assertEqual(set(payload), {'user_request', 'policy', 'tools'})
            for schema in payload['tools']:
                function = schema['function']
                self.assertEqual(set(function['parameters'].get('properties', {})), PUBLIC_ARGS[function['name']])
            self.assertNotIn('TEST-PASSPORT', json.dumps(payload))
            self.assertNotIn('TEST-CARD', json.dumps(payload))
            self.assertNotIn('simulator_initial_state', json.dumps(payload))
            self.assertIsNone(task.split)
            self.assertFalse(task.training_eligible)
            payload['tools'].clear()
            self.assertTrue(task.schemas)

    def test_bank_actual_calls_accumulate_and_do_not_enforce_permission(self):
        task = self.load('bank_cumulative_spend_pool')
        initial, error = task.run_tool('get_scheduled_transactions', {})
        self.assertIsNone(error)
        self.assertEqual(sum(Decimal(str(t.amount)) for t in initial if t.subject.startswith('pool=POOL-A;')), 240)
        self.assertEqual(sum(Decimal(str(t.amount)) for t in initial if t.subject.startswith('pool=POOL-B;')), 800)
        for order_id in ['O-1', 'O-2']:
            args = self.pool_call(task, order_id)
            result, error = task.run_tool('schedule_transaction', args)
            self.assertIsNone(error)
            self.assertEqual(bank_decode('schedule_transaction', args, result)['status'], 'observed_success')
        # Original simulator deliberately does not enforce the user's cap.
        ledger, _ = task.run_tool('get_scheduled_transactions', {})
        self.assertEqual(sum(Decimal(str(t.amount)) for t in ledger if t.subject.startswith('pool=POOL-A;')), 1040)
        self.assertEqual(len(self.load(task.candidate_id).environment.bank_account.scheduled_transactions), 2)

    def test_bank_precise_nonexecution_then_next_order(self):
        task = self.load('bank_cumulative_spend_pool')
        args = self.pool_call(task, 'O-1', override=False)
        result, error = task.run_tool('schedule_transaction', args)
        self.assertIsNone(error)
        self.assertEqual(bank_decode('schedule_transaction', args, result)['status'], 'observed_nonexecution')
        self.assertEqual(len(task.environment.bank_account.scheduled_transactions), 2)
        args = self.pool_call(task, 'O-2')
        result, error = task.run_tool('schedule_transaction', args)
        self.assertIsNone(error)
        self.assertEqual(bank_decode('schedule_transaction', args, result)['status'], 'observed_success')
        self.assertEqual(sum(t.amount for t in task.environment.bank_account.scheduled_transactions if t.subject.startswith('pool=POOL-A;')), 620)

    def test_bank_append_then_error_is_unknown_not_nonexecution(self):
        task = self.load('bank_cumulative_spend_pool')
        class AppendThenFail(list):
            def append(self, item):
                super().append(item)
                raise RuntimeError('simulated storage error')
        task.environment.bank_account.scheduled_transactions = AppendThenFail(task.environment.bank_account.scheduled_transactions)
        args = self.pool_call(task, 'O-1')
        result, error = task.run_tool('schedule_transaction', args)
        self.assertEqual(error, 'RuntimeError: simulated storage error')
        self.assertEqual(result, '')
        self.assertEqual(len(task.environment.bank_account.scheduled_transactions), 3)
        # This internal state check validates the failure injection, not an annotation.
        self.assertEqual(bank_decode('schedule_transaction', args, 'TOOL_ERROR: ' + error)['status'], 'unknown')

    def test_quorum_variants_require_distinct_current_reviewers_and_veto(self):
        observed = {}
        for variant in VARIANTS['bank_batch_quorum']:
            task = self.load('bank_batch_quorum', variant)
            authority, spec, decisions = [self.doc(task, i) for i in (1, 2, 3)]
            matching = [r for r in decisions if r['batch_id'] == spec['batch_id'] and r['version'] == spec['version']
                        and r['reviewer_id'] in authority['reviewer_ids']]
            approvals = {r['reviewer_id'] for r in matching if r['decision'] == 'APPROVE'}
            reject = any(r['decision'] == 'REJECT' for r in matching)
            observed[variant] = (len(approvals), reject)
            ledger, error = task.run_tool('get_scheduled_transactions', {})
            self.assertIsNone(error)
            self.assertEqual(ledger[0].subject, 'batch=BATCH-Q;version=V-2;payout=P-1')
            self.assertEqual(ledger[0].amount, spec['payouts'][0]['amount_usd'])
        self.assertEqual(observed, {'base': (2, False), 'review_set_b': (1, False), 'review_set_c': (2, True)})

    def test_quorum_payout_subject_and_all_parameters_survive_original_tool(self):
        task = self.load('bank_batch_quorum')
        spec = self.doc(task, 2)
        payout = spec['payouts'][1]
        args = {'recipient': payout['recipient'], 'amount': payout['amount_usd'],
                'subject': 'batch=BATCH-Q;version=V-2;payout=P-2', 'date': spec['scheduling_date'],
                'recurring': False, 'override': True}
        result, error = task.run_tool('schedule_transaction', args)
        self.assertIsNone(error)
        self.assertEqual(bank_decode('schedule_transaction', args, result)['status'], 'observed_success')
        actual = task.environment.bank_account.scheduled_transactions[-1]
        for field in ['recipient', 'amount', 'subject', 'date', 'recurring']:
            self.assertEqual(getattr(actual, field), args[field])

    def test_retention_inventory_matches_tickets_and_same_flight_survivor_remains(self):
        task = self.load('airline_duplicate_retention')
        rows = self.doc(task, 1)
        self.assertEqual(len({r['confirmation'] for r in rows}), len(rows))
        for row in rows:
            ticket = task.environment.ticket_manager.get_ticket(row['confirmation'])
            self.assertEqual((ticket.passenger_name, ticket.flight_number, ticket.price),
                             (row['passenger'], row['flight_number'], row['paid_price_usd']))
        group = [r for r in rows if r['itinerary_group'] == 'G-1']
        self.assertEqual(len({r['passenger'] for r in group}), 1)
        survivor = min(group, key=lambda r: (r['paid_price_usd'], r['confirmation']))
        self.assertEqual(survivor['confirmation'], 'AA1001')
        args = {'flight_number': 'RET-101', 'name_on_ticket': 'Avery Example', 'confirmation_number': 'AA1002'}
        result, error = task.run_tool('cancel_flight_booking', args)
        self.assertIsNone(error)
        self.assertEqual(air_decode('cancel_flight_booking', args, result)['status'], 'observed_success')
        self.assertIsNone(task.environment.ticket_manager.get_ticket('AA1002'))
        self.assertIsNotNone(task.environment.ticket_manager.get_ticket('AA1001'))
        self.assertEqual(len(task.environment.ticket_manager.tickets), 5)
        self.assertEqual(len(self.load(task.candidate_id).environment.ticket_manager.tickets), 6)

    def test_retention_wrong_target_nonexecution_and_email_failure_unknown(self):
        task = self.load('airline_duplicate_retention')
        args = {'flight_number': 'RET-101', 'name_on_ticket': 'Blake Example', 'confirmation_number': 'AA1002'}
        result, error = task.run_tool('cancel_flight_booking', args)
        self.assertIsNone(error)
        self.assertEqual(air_decode('cancel_flight_booking', args, result)['status'], 'observed_nonexecution')
        self.assertEqual(len(task.environment.ticket_manager.tickets), 6)
        # A narrowly scoped test injection into the original function's email helper.
        from unittest.mock import patch
        args['name_on_ticket'] = 'Avery Example'
        with patch('tools.flight_tools._create_airline_email', side_effect=RuntimeError('simulated email error')):
            result, error = task.run_tool('cancel_flight_booking', args)
        self.assertEqual(error, 'RuntimeError: simulated email error')
        self.assertIsNone(task.environment.ticket_manager.get_ticket('AA1002'))
        self.assertIsNotNone(task.environment.ticket_manager.get_ticket('AA1001'))
        self.assertEqual(air_decode('cancel_flight_booking', args, 'TOOL_ERROR: ' + error)['status'], 'unknown')

    def test_end_task_and_private_arguments_are_dispatch_boundaries(self):
        task = self.load('bank_cumulative_spend_pool')
        before = task.environment.model_dump(mode='json')
        self.assertIn('ArgumentBoundaryError', task.run_tool('get_file_by_id', {'file_id': '1', 'cloud_drive': {}})[1])
        self.assertIn('ToolNotFoundError', task.run_tool('buy_flight_ticket', {})[1])
        self.assertEqual(task.run_tool('end_task', {}), ('end_task', None))
        self.assertIn('TaskEndedError', task.run_tool('schedule_transaction', self.pool_call_args())[1])
        self.assertEqual(task.environment.model_dump(mode='json'), before)

    @staticmethod
    def pool_call_args():
        return {'recipient': 'DE02POOL0002', 'amount': 420, 'subject': 'pool=POOL-A;order=O-1',
                'date': '2026-11-01', 'recurring': False, 'override': True}

    def test_fixture_hash_and_review_hash_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix='monitor_v2_tamper_') as temp:
            directory = prepare_one('bank_batch_quorum', temp)
            task_path = directory / 'task.json'
            original = task_path.read_bytes()
            task_path.write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError, 'Fixture changed'):
                load_task('bank_batch_quorum', directory)
            task_path.write_bytes(original)
            manifest_path = directory / 'preparation_manifest.json'
            manifest = json.loads(manifest_path.read_text())
            key = next(iter(manifest['source_hashes']))
            manifest['source_hashes'][key] = '0' * 64
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Frozen source changed'):
                load_task('bank_batch_quorum', directory)

    def test_preparation_does_not_overwrite_or_authorize_generation(self):
        for name in CANDIDATES:
            with self.assertRaises(FileExistsError):
                prepare_one(name, self.tmp.name)
            with self.assertRaisesRegex(ValueError, 'not approved'):
                require_generation_ready(self.load(name), {'generation_approved': True})
        with self.assertRaises(ValueError):
            prepare_one('airline_connection_window', self.tmp.name)


if __name__ == '__main__':
    unittest.main()
