import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tgf_sft_train_extension_v1 as m
class ExtensionTests(unittest.TestCase):
 def test_finite_population_and_gate(self):
  m.gate();s=m.specs();self.assertEqual(len(s),40);self.assertEqual(sum(x['expected_target_events'] for x in s),44)
  for d in ['bank','travel']:self.assertEqual(sum(x['expected_target_events'] for x in s if x['domain']==d),22)
  self.assertEqual({x['split'] for x in s},{'train'});self.assertEqual(len({x['seed'] for x in s}),40)
 def test_no_old_instance_identity_or_seed_reuse(self):
  old=m.base.specs();new=m.specs()
  for k in ['case_id','seed']:self.assertFalse({x[k] for x in old}&{x[k] for x in new})
 def test_exact_dispatch_budget_without_running_tools(self):
  count=sum(len(m.base.build_fixture(s)[2])+1 for s in m.specs());self.assertEqual(count,160)
if __name__=='__main__':unittest.main()
