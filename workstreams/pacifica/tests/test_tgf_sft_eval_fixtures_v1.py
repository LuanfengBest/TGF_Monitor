"""Population and environment-schema checks; never dispatch or inspect final labels."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tgf_sft_eval_fixtures_v1 as m
class FixtureTests(unittest.TestCase):
 def test_preassigned_finite_population(self):
  s=m.specs();self.assertEqual(len(s),34)
  self.assertEqual(sum(x['target_events'] for x in s if x['split']=='validation'),12)
  self.assertEqual(sum(x['target_events'] for x in s if x['split']=='final_test'),24)
  self.assertEqual(len({x['seed'] for x in s}),34)
 def test_all_fixture_schema_construction_no_tools(self):
  for s in m.specs():
   view,state,calls,cls=m.fixture(s);env=cls(**state)
   self.assertEqual(set(view),{'user_request','policy'});self.assertEqual(len(calls)- (4 if s['family']=='quorum' else 1),s['target_events'])
   self.assertGreater(len(env.available_tools),1)
 def test_definitions_not_training(self):
  self.assertNotIn('train',{x['split'] for x in m.specs()})
if __name__=='__main__':unittest.main()
