import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from candidate_task_adapters_v1 import load_candidate,require_generation_ready


class CandidateAdapterTests(unittest.TestCase):
    def test_invoice_runtime_dependency_and_tool_boundary(self):
        c=load_candidate('bank_invoice_release')
        doc,error=c.runtime.run_function(c.environment,'get_file_by_id',{'file_id':'1'})
        self.assertIsNone(error);self.assertIn('Morgan Reviewer',doc.content)
        result,error=c.runtime.run_function(c.environment,'schedule_transaction',dict(recipient='SIMULATED-VENDOR-A',amount=1200,
            subject='I-101',date='2026-10-20',recurring=False,override=True))
        self.assertIsNone(error);self.assertIn('scheduled successfully',result)
        self.assertEqual(len(c.environment.bank_account.scheduled_transactions),1)
        _,error=c.runtime.run_function(c.environment,'append_to_file',{'file_id':'1','content':'replace authority'})
        self.assertIn('ToolNotFoundError',error)
        fresh=load_candidate('bank_invoice_release');self.assertFalse(fresh.environment.bank_account.scheduled_transactions)

    def test_rebooking_runtime_buy_and_cancel(self):
        c=load_candidate('airline_single_passenger_rebooking')
        initial=list(c.environment.ticket_manager.tickets)
        result,error=c.runtime.run_function(c.environment,'buy_flight_ticket',{'flight_number':'SIM-NEW-01','name_on_ticket':'Avery Example'})
        self.assertIsNone(error);self.assertIn('bought successfully',result)
        result,error=c.runtime.run_function(c.environment,'cancel_flight_booking',{'flight_number':'SIM-OLD-01','name_on_ticket':'Avery Example','confirmation_number':initial[0]})
        self.assertIsNone(error);self.assertIn('successfully cancelled',result)
        self.assertEqual(len(c.environment.ticket_manager.tickets),1)
        _,error=c.runtime.run_function(c.environment,'reserve_restaurant',{})
        self.assertIn('ToolNotFoundError',error)

    def test_unreviewed_or_fabricated_split_cannot_generate(self):
        c=load_candidate('bank_invoice_release')
        for registry in [{},{c.candidate_id:{'split':'train'}},
             {c.candidate_id:{'family_independence_verified':True,'task_semantics_reviewed':True,'split':'train','fixture_hashes':{},'frozen_at':'dummy'}}]:
            with self.assertRaises(ValueError):require_generation_ready(c,registry)
        self.assertIsNone(c.split);self.assertFalse(c.training_eligible)


if __name__=='__main__':unittest.main()
