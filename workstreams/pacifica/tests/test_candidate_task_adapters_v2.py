import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from candidate_task_adapters_v2 import load_candidate, require_generation_ready
from candidate_task_adapters_v1 import load_candidate as load_v1


class RevisedAdapterTests(unittest.TestCase):
    def test_invoice_visible_join_and_isolation(self):
        c = load_candidate('bank_invoice_release')
        docs = {}
        for i in range(1, 5):
            doc, error = c.runtime.run_function(c.environment, 'get_file_by_id', {'file_id': str(i)})
            self.assertIsNone(error)
            docs[i] = json.loads(doc.content)
        vendor = next(r for r in docs[1] if r['vendor_id'] == 'V-10')
        rows = [next(r for r in docs[i] if r['invoice_id'] == 'I-101') for i in (2, 3, 4)]
        self.assertEqual({r['vendor_id'] for r in rows}, {vendor['vendor_id']})
        self.assertEqual({r['amount_usd'] for r in rows}, {1200})
        self.assertEqual(rows[1]['status'], 'delivered')
        self.assertEqual(rows[2]['status'], 'approved')
        self.assertEqual(rows[2]['approved_by'], vendor['approver'])
        self.assertNotIn('amount_usd', vendor)
        schedules, error = c.runtime.run_function(c.environment, 'get_scheduled_transactions', {})
        self.assertIsNone(error)
        self.assertEqual(schedules, [])
        result, error = c.runtime.run_function(c.environment, 'schedule_transaction', {
            'recipient': vendor['account'], 'amount': rows[0]['amount_usd'],
            'subject': 'I-101', 'date': '2026-10-20', 'recurring': False, 'override': True})
        self.assertIsNone(error)
        self.assertIn('scheduled successfully', result)
        before_end = c.environment.model_dump(mode='json')
        result, error = c.runtime.run_function(c.environment, 'end_task', {})
        self.assertEqual((result, error), ('end_task', None))
        self.assertEqual(c.environment.model_dump(mode='json'), before_end)
        self.assertFalse(load_candidate(c.candidate_id).environment.bank_account.scheduled_transactions)
        self.assertNotEqual(c.user_request, load_v1(c.candidate_id).user_request)
        _, error = c.runtime.run_function(c.environment, 'append_to_file', {'file_id': '1', 'content': 'x'})
        self.assertIn('ToolNotFoundError', error)

    def test_airline_observable_purchase_then_cancel(self):
        c = load_candidate('airline_single_passenger_rebooking')
        flights, error = c.runtime.run_function(c.environment, 'get_flights_between_locations',
                                                {'departure_city': 'Boston', 'arrival_city': 'Chicago'})
        self.assertIsNone(error)
        self.assertIn('SIM-NEW-01', flights)
        self.assertIn('449', flights)
        result, error = c.runtime.run_function(c.environment, 'buy_flight_ticket',
                                              {'flight_number': 'SIM-NEW-01', 'name_on_ticket': 'Avery Example'})
        self.assertIsNone(error)
        self.assertIn('bought successfully', result)
        self.assertIn('449.00', result)
        result, error = c.runtime.run_function(c.environment, 'cancel_flight_booking', {
            'flight_number': 'SIM-OLD-01', 'name_on_ticket': 'Avery Example', 'confirmation_number': '7A4ADE'})
        self.assertIsNone(error)
        self.assertIn('successfully cancelled', result)
        before_end = c.environment.model_dump(mode='json')
        self.assertEqual(c.runtime.run_function(c.environment, 'end_task', {}), ('end_task', None))
        self.assertEqual(c.environment.model_dump(mode='json'), before_end)
        self.assertIn('7A4ADE', load_candidate(c.candidate_id).environment.ticket_manager.tickets)
        _, error = c.runtime.run_function(c.environment, 'get_emails', {})
        self.assertIn('ToolNotFoundError', error)

    def test_review_does_not_bypass_generation_gate(self):
        for name in ['bank_invoice_release', 'airline_single_passenger_rebooking']:
            c = load_candidate(name)
            with self.assertRaises(ValueError):
                require_generation_ready(c, {name: {'task_semantics_reviewed': True, 'split': 'development',
                                                    'fixture_hashes': c.fixture_hashes, 'frozen_at': 'test'}})
            self.assertIsNone(c.split)
            self.assertFalse(c.training_eligible)


if __name__ == '__main__':
    unittest.main()
