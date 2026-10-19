"""Offline fake responses/environment only: no model requests or simulator dispatch."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import prospective_actor_reminder_v1 as a
import tgf_public_trace_reminder_v1 as public
from analyze_prospective_actor_v6 import check_context,check_states
from tgf_public_trace_v1 import shared_bundle as legacy_bundle
from pilot_review_packet_reminder_v1 import packet


def reply(name=None,capped=False):
    return {'done':True,'done_reason':'length' if capped else 'stop','eval_count':2048 if capped else 10,
            'message':{'role':'assistant','content':'Still working.','thinking':'PUBLIC_THINKING',
                       'tool_calls':[] if name is None else [{'function':{'name':name,'arguments':{}}}]}}

class FakeClient:
    def __init__(self,replies):self.replies=iter(replies);self.count=0;self.contexts=[]
    def chat(self,*args,**kwargs):
        self.contexts.append(deepcopy(args[1]));self.count+=1
        return deepcopy(next(self.replies))

class Env:
    def __init__(self):self.n=0
    def model_dump(self,**kw):return {'counter':self.n}

class ReminderTests(unittest.TestCase):
    def run_rollout(self,replies,turns=40,expired=False,interrupted=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);out=Path(tmp.name)/'rollout'
        env=Env();c=SimpleNamespace(candidate_id='bank_transfer_2',user_request='PUBLIC_REQUEST',policy='PUBLIC_POLICY',environment=env,schemas=[])
        client=FakeClient(replies)
        if expired:client.deadline=time.monotonic()-1
        def dispatch(c,name,args):
            if interrupted:c.environment.n+=1;raise TimeoutError('Partial fake dispatch')
            return ('end_task' if name=='end_task' else 'read-only result'),None
        with patch.object(a,'load_original',return_value=c),patch.object(a,'require_original_ready',return_value='development'),patch.object(a,'dispatch',side_effect=dispatch):
            status=a.rollout({'attempt_id':'fake','candidate_id':c.candidate_id,'condition':'injected','secondary_objective':'PRIVATE_SENTINEL','seed':1},
                {'actor_max_seconds':10,'actor_max_turns':turns,'actor':'fake','actor_think':'low','actor_context':131072,'actor_output_tokens':2048,'temperature':.6,'max_tool_events':80},
                {'candidates':{c.candidate_id:{'family_id':'fake'}}},out,client)
        view=a.read(out/'monitor_view.json');context=a.read(out/'raw/actor_context.json')
        check_context(context,view);check_states(out,a.read(out/'oracle/events.json'));public.shared_bundle(view)
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(view));self.assertIn('PRIVATE_SENTINEL',context[0]['content'])
        return status,out,client
    def test_empty_reminder_tools_and_end(self):
        s,o,c=self.run_rollout([reply(),reply('get_balance'),reply('end_task')])
        self.assertEqual(s,'ended');self.assertEqual(c.count,3)
        self.assertEqual(c.contexts[1][-1],{'role':'user','content':public.UPSTREAM_REMINDER})
        self.assertEqual(len(a.read(o/'summary.json')['no_tool_reminders']),1)
    def test_five_cumulative_not_consecutive_and_no_seventh_request(self):
        seq=[]
        for _ in range(5):seq.extend([reply(),reply('get_balance')])
        seq.append(reply())
        s,o,c=self.run_rollout(seq)
        self.assertEqual((s,c.count,len(a.read(o/'summary.json')['no_tool_reminders'])),('no_tool_reminder_limit',11,5))
    def test_turn_budget_counts_reminder_followup(self):
        s,o,c=self.run_rollout([reply(),reply(),reply()],turns=3)
        self.assertEqual((s,c.count,len(a.read(o/'summary.json')['no_tool_reminders'])),('turn_limit',3,2))
    def test_no_request_after_deadline(self):
        s,o,c=self.run_rollout([],expired=True);self.assertEqual((s,c.count),('time_limit',0))
    def test_cap_never_adds_reminder(self):
        s,o,c=self.run_rollout([reply(capped=True)])
        self.assertEqual(s,'output_cap_or_incomplete');self.assertEqual(a.read(o/'summary.json')['no_tool_reminders'],[])
    def test_end_does_not_continue(self):
        s,o,c=self.run_rollout([reply('end_task'),reply()]);self.assertEqual((s,c.count),('ended',1))
    def test_interruption_preserves_partial_effect(self):
        s,o,c=self.run_rollout([reply('change')],interrupted=True)
        self.assertEqual(s,'time_limit');self.assertEqual(a.read(o/'oracle/final_state.json')['counter'],1)
        self.assertEqual(a.read(o/'oracle/events.json')[0]['status'],'interrupted_unknown_effect')
    def test_arbitrary_user_or_modified_reminder_rejected(self):
        c=SimpleNamespace(user_request='r',policy='p')
        for msg in [{'role':'user','content':'Authorize payment'}, {'role':'user','content':public.UPSTREAM_REMINDER}, {'role':'system','content':'private'}]:
            with self.assertRaises(ValueError):public.visible_view(c,[msg])
            with self.assertRaises(ValueError):public.shared_bundle({'user_request':'r','policy':'p','messages':[msg]})
    def test_exact_upstream_reminder(self):
        tree=ast.parse((ROOT/'third_party/MonitorBench/datasets/dual_objective/agent/utils/pipeline_elements.py').read_text())
        self.assertIn(public.UPSTREAM_REMINDER,[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)])
    def test_legacy_views_unchanged(self):
        s,o,c=self.run_rollout([reply('get_balance'),reply('end_task')]);v=a.read(o/'monitor_view.json')
        self.assertEqual(public.shared_bundle(v),legacy_bundle(v))
    def test_scientific_difference_is_only_declared_reminder_logic(self):
        old=ast.parse((ROOT/'scripts/prospective_actor_v6.py').read_text());new=ast.parse((ROOT/'scripts/prospective_actor_reminder_v1.py').read_text())
        def fn(t):return next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='rollout')
        oldfn,newfn=fn(old),fn(new)
        # Explicitly remove new bookkeeping fields / assignment and substitute only the no-tools block.
        oldblock=next(n for n in ast.walk(oldfn) if isinstance(n,ast.If) and ast.unparse(n.test)=='not tool_calls')
        class Normalize(ast.NodeTransformer):
            def visit_Assign(self,n):
                if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='reminders':return None
                return self.generic_visit(n)
            def visit_If(self,n):
                if ast.unparse(n.test)=='not tool_calls':return deepcopy(oldblock)
                return self.generic_visit(n)
            def visit_Dict(self,n):
                pairs=[(k,v) for k,v in zip(n.keys,n.values) if not(isinstance(k,ast.Constant) and k.value in {'collector_version','no_tool_reminders','max_no_tool_reminders'})]
                n.keys=[p[0] for p in pairs];n.values=[p[1] for p in pairs];return self.generic_visit(n)
        self.assertEqual(ast.dump(oldfn,include_attributes=False),ast.dump(Normalize().visit(newfn),include_attributes=False))
        import prospective_actor_v6 as olda
        for name in ['load_original','dispatch','SYSTEM','DeadlineOllama','require_original_ready']:
            self.assertIs(getattr(a,name),getattr(olda,name))
if __name__=='__main__':unittest.main()
