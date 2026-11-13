"""Scientific invariants and dispatch safety, independent of model accuracy."""
import copy,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from . import protocol as p,judge_stage as j,specs
from .common import BUNDLE,read
from jev_monitor_v1.prepare import fixtures
from jev_monitor_v1.core import canonical,digest

class Checks(unittest.TestCase):
 def test_independent_instances_and_paired_conditions(self):
  m=read(BUNDLE/'tasks_PRIVATE.json');self.assertEqual(len(m['instances']),96);self.assertEqual(len(m['tasks']),192)
  self.assertEqual(m['tasks_sha256'],digest(m['tasks']))
  for i in m['instances']:
   ts=[t for t in m['tasks'] if t['instance_id']==i['instance_id']]
   self.assertEqual({t['condition'] for t in ts},{'ordinary','side_objective'})
   self.assertEqual(ts[0]['authorization_messages'],ts[1]['authorization_messages'])
   self.assertEqual(ts[0]['initial_user_text'],ts[1]['initial_user_text'])
   self.assertIsNone(ts[0]['expected_actor_label']);self.assertIsNone(ts[1]['expected_actor_label'])
 def test_only_question_content_changes(self):
  for f in fixtures():
   state,dim=p.public_state(f['record']);before=copy.deepcopy(state)
   a=p.with_supplement(state,'F',{'question':p.question(state,dim,'F'),'answer':'unchanged answer'})
   b=p.with_supplement(state,'T',{'question':p.question(state,dim,'T'),'answer':'unchanged answer'})
   self.assertEqual(state,before);self.assertEqual(a['record'],b['record']);self.assertEqual(a['fact_ledger'],b['fact_ledger'])
   self.assertEqual(a['marked_operation'],b['marked_operation']);self.assertNotEqual(a['supplemental_qa']['question'],b['supplemental_qa']['question'])
   self.assertEqual(p.jev_body(a)['state'],a);self.assertTrue(p.qwen_prompt(a).endswith(canonical(a)))
 def test_receipt_success_not_requested_amount(self):
  record=copy.deepcopy(fixtures()[0]['record']);record['messages'][-1]['content']='Failed to send money: Insufficient funds (need $10.10, including $0.10 fee)'
  with self.assertRaises(ValueError):p.public_state(record)
 def test_private_labels_never_in_state(self):
  for r in read(BUNDLE/'smoke.json'):
   text=canonical(r['state']);self.assertNotIn('private_system',text);self.assertNotIn('expected_label',text);self.assertNotIn('reference_status',text)
 def test_failure_does_not_retry(self):
  class Fail:
   calls=0
   def generate(self,*args,**kwargs):self.calls+=1;raise TimeoutError('injected')
  b=Fail();s,_=p.public_state(fixtures()[0]['record']);row={'request_id':'test.P','state':s}
  with tempfile.TemporaryDirectory() as tmp,patch.object(j,'OUT',Path(tmp)),patch.object(j,'sha',return_value='test'):
   first=j.classify_one('qwen',row,b,time.monotonic()+30)
   second=j.classify_one('qwen',row,b,time.monotonic()+30)
   self.assertEqual(b.calls,1);self.assertEqual(first['status'],'invalid');self.assertEqual(first,second)
 def test_unreturned_claim_never_reissued(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(j,'OUT',Path(tmp)):
   d=Path(tmp)/'judgments/qwen/test.P';d.mkdir(parents=True);(d/'dispatch.json').write_text('{}')
   self.assertEqual(j.classify_one('qwen',{'request_id':'test.P'},None,time.monotonic()+30)['status'],'unknown_after_dispatch')
 def test_budget_arithmetic(self):
  c=read(BUNDLE/'config.json');lim=c['limits'];self.assertEqual(lim['total_calls'],sum(lim[k] for k in ('collection_calls','followup_calls','review_calls','qwen_judge_calls','jev_calls')))
  self.assertEqual(lim['qwen_output_tokens'],192*2048+776*1024)
  self.assertLessEqual(776*32000*.042/1e6,c['jev']['api_usd_cap'])
if __name__=='__main__':unittest.main()
