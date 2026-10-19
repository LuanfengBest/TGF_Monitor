import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from compare_monitor_deployments_v1 import summarize
class ComparisonTests(unittest.TestCase):
 def test_missing_cap_and_abstention_are_not_success(self):
  rows=[{'input_id':'a_short','status':'output_cap_or_incomplete'}, {'input_id':'b_full','status':'parsed','core_pass':False,'flag_pass':False,'mechanically_accepted':False}]
  d=summarize(rows,['a_short','b_full','c_short'])
  self.assertEqual(d['all'],{'planned':3,'attempted':2,'missing':1,'parsed':1,'core_pass':0,'execution_pass':0,'flag_pass':0,'mechanically_accepted':0})
 def test_duplicates_and_foreign_ids_rejected(self):
  with self.assertRaises(AssertionError):summarize([{'input_id':'foreign','status':'parsed'}],['a_short'])
  with self.assertRaises(AssertionError):summarize([{'input_id':'a_short','status':'parsed'}]*2,['a_short'])
if __name__=='__main__':unittest.main()
