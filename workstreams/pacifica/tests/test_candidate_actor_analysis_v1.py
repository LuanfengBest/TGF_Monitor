from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
from test_candidate_actor_pilot_v1 import response,Replay
from candidate_actor_pilot_v1 import rollout,load_candidate
from analyze_candidate_actor_pilot_v1 import check_attempt
from ollama_client import save


class SavingReplay(Replay):
    def __init__(self,replies,path):
        super().__init__(replies);self.path=path
    def chat(self,model,context,**kw):
        request={'model':model,'messages':deepcopy(context),'tools':kw['tools'],'think':kw['think'],'stream':False,
                 'options':{'seed':kw['seed'],'temperature':kw['temperature'],'num_ctx':kw['ctx'],'num_predict':kw['predict']}}
        out=super().chat(model,context,**kw)
        save(self.path/f'call_{self.count:04d}_request.json',request)
        save(self.path/f'call_{self.count:04d}_response.json',out)
        return out


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.attempt={'attempt_id':'test','candidate_id':'bank_invoice_release','condition':'ordinary','seed':139}
        self.plan={'actor':'fake','actor_think':'low','actor_context':32768,'actor_output_tokens':2048,
                   'temperature':0.6,'actor_max_turns':12,'actor_max_seconds':10,'max_tool_events':32}
        c=load_candidate('bank_invoice_release')
        registry={'candidates':{c.candidate_id:{'family_independence_verified':True,'task_semantics_reviewed':True,
                  'split':'development','fixture_hashes':c.fixture_hashes,'frozen_at':'test','family_id':'test_only'}}}
        client=SavingReplay([response(('get_file_by_id',{'file_id':'1'})),response(('end_task',{}))],self.base/'test/actor_calls')
        rollout(self.attempt,self.plan,registry,self.base/'test/rollout',client)

    def test_original_chain_verified_and_thinking_tamper_rejected(self):
        result=check_attempt(self.base,self.attempt,self.plan)
        self.assertEqual(result['requests'],2)
        p=self.base/'test/rollout/monitor_view.json';view=json.loads(p.read_text())
        view['messages'][0]['thinking']='Changed after generation';save(p,view)
        with self.assertRaises(ValueError):check_attempt(self.base,self.attempt,self.plan)

    def test_changed_next_request_rejected(self):
        p=self.base/'test/actor_calls/call_0002_request.json';req=json.loads(p.read_text())
        req['messages'][0]['content']='Altered hidden system';save(p,req)
        with self.assertRaises(ValueError):check_attempt(self.base,self.attempt,self.plan)


if __name__=='__main__':unittest.main()
