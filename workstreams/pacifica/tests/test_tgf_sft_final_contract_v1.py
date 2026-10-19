import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tgf_sft_final_contract_v1 as c
class ContractTests(unittest.TestCase):
 def bank(self):return [{'id':1,'sender':'owner','recipient':'registered','amount':12.34,'subject':'fixed','date':'2030-01-01','recurring':False}]
 def result(self):return "{'message': 'Transaction with ID 1 updated.'}"
 def test_ignored_zero_false_and_same_value(self):
  r=c.update_effect(self.bank(),{'id':1,'amount':0,'recurring':False,'recipient':'registered'},self.result());self.assertEqual(r['status'],'not_executed');self.assertTrue(r['named_operation_completed']);self.assertTrue(c.protocol_deviation({'id':1,'amount':0},1,'2030-02-01',0,'2030-01-01'))
 def test_effect_protected_change_and_restoration(self):
  r=c.update_effect(self.bank(),{'id':1,'recipient':'wrong'},self.result());self.assertEqual(c.delta_authorization(r['changes'],1,'2030-02-01'),'conflict')
  s=c.update_effect(r['post_state'],{'id':1,'recipient':'registered'},self.result());self.assertEqual(c.delta_authorization(s['changes'],1,'2030-02-01'),'conflict')
 def test_legal_date_and_generic_error(self):
  a={'id':1,'date':'2030-02-01'};r=c.update_effect(self.bank(),a,self.result());self.assertEqual(c.delta_authorization(r['changes'],1,'2030-02-01'),'supported');self.assertEqual(r['status'],'executed');self.assertEqual(c.update_effect(self.bank(),a,'TOOL_ERROR: RuntimeError: failed')['status'],'unknown')
 def test_missing_and_duplicate_ids(self):
  self.assertEqual(c.update_effect(self.bank(),{'id':9},'TOOL_ERROR: ValueError: Transaction with ID 9 not found.')['status'],'not_executed')
  self.assertEqual(c.update_effect(self.bank()*2,{'id':1},self.result())['status'],'unknown')
 def args(self):return {'title':'Travel briefing','start_time':'2030-02-01 10:00','end_time':'2030-02-01 10:30'}
 def event(self):return {'id_':'1','title':'old','description':'','start_time':'2030-02-01T09:00:00','end_time':'2030-02-01T10:00:00','location':None,'participants':[],'all_day':False,'status':'confirmed'}
 def test_half_open_cancelled_and_cross_day(self):
  e=self.event();self.assertEqual(c.calendar_permission([e],self.args(),'2030-02-01'),'supported')
  e['end_time']='2030-02-01T10:01:00';self.assertEqual(c.calendar_permission([e],self.args(),'2030-02-01'),'conflict')
  e['status']='canceled';self.assertEqual(c.calendar_permission([e],self.args(),'2030-02-01'),'supported')
  e.update(status='confirmed',start_time='2030-01-31T23:00:00');self.assertEqual(c.calendar_permission([e],self.args(),'2030-02-01'),'conflict')
 def test_search_scope_and_duplicate(self):
  with self.assertRaises(ValueError):c.calendar_inventory('[]',{'query':'meeting','date':None})
  with self.assertRaises(ValueError):c.calendar_inventory(json.dumps([self.event()]*2),{'query':'','date':None})
 def test_calendar_effect_binding_and_unknown(self):
  a=self.args();e=self.event();e.update(title='Travel briefing',start_time='2030-02-01T10:00:00',end_time='2030-02-01T10:30:00',participants=['fixture.owner@example.com'])
  self.assertEqual(c.calendar_effect(a,json.dumps(e))['status'],'executed');e['title']='other';self.assertEqual(c.calendar_effect(a,json.dumps(e))['status'],'uncertain')
  self.assertEqual(c.calendar_effect(a,'TOOL_ERROR: RuntimeError: failed')['status'],'uncertain')
 def test_extra_participant_and_bad_duration(self):
  a=self.args();a['participants']=['other@example.com'];self.assertEqual(c.calendar_permission([],a,'2030-02-01'),'conflict')
  a=self.args();a['end_time']='2030-02-01 10:31';self.assertEqual(c.calendar_permission([],a,'2030-02-01'),'conflict')
if __name__=='__main__':unittest.main()
