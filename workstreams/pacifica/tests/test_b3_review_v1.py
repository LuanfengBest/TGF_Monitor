import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import b3_review_v1 as b
import jsonschema

class Protocol(unittest.TestCase):
 def setUp(self):
  self.common=b.read(b.ROOT/'results/paired_native_remaining_29366122/pilot_002_ordinary/common_judge_evidence.json')
 def test_final_judge_original_evidence_unchanged(self):
  before=copy.deepcopy(self.common);out=b.judge_bundle(self.common,{'findings':[]})
  self.assertEqual(self.common,before)
  self.assertEqual({k:v for k,v in out.items() if k not in ('followup','extra_monitor_review')},before)
  self.assertIsNone(out['followup'])
 def test_no_oracle_fields(self):
  bad={'findings':[],'reference_label':1}
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(bad,b.extra_schema(self.common))
 def test_unknown_source_rejected(self):
  bad={'findings':[{'event_id':'e0010','finding':'x','source_ids':['private_state']}]}
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(bad,b.extra_schema(self.common))
 def test_unknown_event_rejected(self):
  bad={'findings':[{'event_id':'e9999','finding':'x','source_ids':['user_request']}]}
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(bad,b.extra_schema(self.common))
 def test_read_scope_is_original_public_projection(self):
  item={'common_path':'results/paired_native_remaining_29366122/pilot_002_ordinary/common_judge_evidence.json','view_path':'results/bank_pilot_v2_29341393/actors/pilot_002_ordinary/monitor_view.json'}
  self.assertEqual(b.load_common(item),self.common)
 def test_no_semantic_prompt_revision_for_judge(self):
  from paired_protocol_v3 import JUDGE_SYSTEM
  self.assertEqual(b.JUDGE_SYSTEM,JUDGE_SYSTEM)
if __name__=='__main__':unittest.main()
