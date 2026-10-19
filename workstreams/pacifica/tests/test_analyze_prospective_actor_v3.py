import sys
from pathlib import Path
from copy import deepcopy
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_prospective_actor_v3 import check_context
class ContextTests(unittest.TestCase):
 def fixture(self):
  c=[{'role':'system','content':'HIDDEN'},{'role':'user','content':'task'},
     {'role':'assistant','tool_calls':[{'function':{'name':'f','arguments':{}}}]},
     {'role':'tool','tool_name':'f','content':'done'}]
  v={'user_request':'task','policy':'p','messages':deepcopy(c[2:])}
  v['messages'][0]['tool_calls'][0]['id']='c1';v['messages'][1].update(event_id='e1',source_type='tool_return',tool_call_id='c1')
  return c,v
 def test_generated_id_bookkeeping_does_not_change_original(self):
  c,v=self.fixture();check_context(c,v)
 def test_harness_record_is_not_inserted_into_actor_context(self):
  c,v=self.fixture();v['messages'].append({'role':'tool','content':'not dispatched','source_type':'harness_execution_record'});check_context(c,v)
 def test_changed_evidence_rejected(self):
  c,v=self.fixture();v['messages'][1]['content']='changed'
  with self.assertRaises(ValueError):check_context(c,v)
if __name__=='__main__':unittest.main()
