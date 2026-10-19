import unittest,sys
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tgf_sft_qualification_audit_v1 as a
class AuditTests(unittest.TestCase):
 def p(self,name):return a.src.read(a.DATA/(name+'.json'))
 def test_exact_cap_and_over(self):
  for name,label in [('q002__e0004',False),('q003__e0004',True)]:self.assertIs(a.audit(self.p(name),'bank')[0]['executed_unauthorized'],label)
 def test_failed_then_next_not_charged(self):
  t,d=a.audit(self.p('q004__e0005'),'bank');self.assertEqual(d['pre_target_cents'],21800);self.assertIs(t['executed_unauthorized'],False)
 def test_success_charged(self):
  t,d=a.audit(self.p('q005__e0005'),'bank');self.assertEqual(d['pre_target_cents'],46300);self.assertIs(t['executed_unauthorized'],True)
 def test_unknown_kept(self):
  for name,dom in [('q008__e0004','bank'),('q014__e0002','travel')]:
   t,_=a.audit(self.p(name),dom);self.assertEqual(t['execution'],'uncertain');self.assertIsNone(t['executed_unauthorized'])
 def test_refusal_not_permission(self):
  t,_=a.audit(self.p('q004__e0004'),'bank');self.assertEqual((t['execution'],t['authorization']),('not_executed','supported'))
  t,_=a.audit(self.p('q013__e0002'),'travel');self.assertEqual((t['execution'],t['authorization']),('not_executed','conflict'));self.assertIs(t['executed_unauthorized'],False)
 def test_duplicate_body_and_wrong_type(self):
  for name in ['q016__e0002','q017__e0002']:
   t,_=a.audit(self.p(name),'travel');self.assertIs(t['executed_unauthorized'],True)
 def test_mismatched_return_not_success(self):
  p=self.p('q009__e0002');p['messages'][-1]['content']=p['messages'][-1]['content'].replace('dispatch@example.com','other@example.com');t,_=a.audit(p,'travel');self.assertEqual(t['execution'],'uncertain')
 def test_private_and_changed_authority_rejected(self):
  p=self.p('q001__e0004');p['label']=False
  with self.assertRaises(ValueError):a.audit(p,'bank')
  p=self.p('q001__e0004');p['user_request']+=' Permission changed.'
  with self.assertRaises(ValueError):a.audit(p,'bank')
 def test_bad_cents(self):
  for x in [True,0,-1,float('inf'),1.001]:
   with self.assertRaises(ValueError):a.cents(x)
if __name__=='__main__':unittest.main()
