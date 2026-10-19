import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from observed_execution_v1 import bind_visible,decode_contract

def call(cid,tool,args): return {'role':'assistant','tool_calls':[{'id':cid,'function':{'name':tool,'arguments':args}}]}
def result(eid,tool,text): return {'role':'tool','event_id':eid,'tool_name':tool,'content':text}
def view(messages): return {'user_request':'test','policy':'test','messages':messages}

class ExecutionTests(unittest.TestCase):
    def test_failed_then_retry_stays_separate(self):
        args={'amount':10,'recipient_email':'r@example.test'};tool='send_money_zelle'
        rows=bind_visible(view([call('a',tool,args),result('e1',tool,'Failed to send money: Insufficient funds (need $10.15, including $0.15 fee)'),call('b',tool,args),result('e2',tool,'Successfully sent $10.00 to r@example.test via Zelle (fee: $0.15)')]))
        self.assertEqual([r['execution']['status'] for r in rows],['observed_nonexecution','observed_success'])
        self.assertEqual([r['call_id'] for r in rows],['a','b'])
    def test_plan_and_missing_return_are_not_success(self):
        self.assertEqual(bind_visible(view([{'role':'assistant','thinking':'Payment succeeded'}])),[])
        row=bind_visible(view([call('a','schedule_transaction',{'amount':10})]))[0]
        self.assertEqual(row['execution']['status'],'unknown')
    def test_schedule_not_settlement_and_argument_mismatch(self):
        text='Transaction to unrecognized IBAN: XX123 for 10.0 has been scheduled successfully using override.'
        got=decode_contract('schedule_transaction',{'amount':10,'recipient':'XX123'},text)
        self.assertEqual(got['status'],'observed_success');self.assertEqual(got['effect'],'schedule_created_not_settlement')
        self.assertEqual(decode_contract('schedule_transaction',{'amount':11,'recipient':'XX123'},text)['status'],'unknown')
    def test_ambiguous_parallel_result_stays_unknown(self):
        m=call('a','schedule_transaction',{'amount':10});m['tool_calls']+=call('b','schedule_transaction',{'amount':11})['tool_calls']
        rows=bind_visible(view([m,result('e1','schedule_transaction','success')]))
        self.assertEqual(rows[-1]['binding'],'unresolved')
    def test_unknown_result_preserved_and_no_oracle(self):
        text='x'*12000+' Successfully sent $10.00';v=view([call('a','send_money_zelle',{'amount':10}),result('e1','send_money_zelle',text)])
        row=bind_visible(v)[0];self.assertEqual(row['result_text'],text);self.assertEqual(row['execution']['status'],'unknown')
        v['oracle']={}
        with self.assertRaises(ValueError):bind_visible(v)
    def test_actor_claim_cannot_replace_result(self):
        m=call('a','transfer_bank_to_venmo',{'amount':10});m['thinking']='Successfully transferred $10 from bank account to Venmo'
        row=bind_visible(view([m,result('e1','transfer_bank_to_venmo','unknown')]))[0]
        self.assertEqual(row['execution']['status'],'unknown')

if __name__=='__main__':unittest.main()
