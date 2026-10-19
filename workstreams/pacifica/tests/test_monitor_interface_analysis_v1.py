"""Evaluation integrity checks with synthetic transport artifacts, no inference."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_monitor_interface_ablation_v1 import analyze
from monitor_interface_ablation_v1 import PLAN, payload
from monitor_facts_v1 import execution_facts, guard_output
from ollama_client import save


class EvaluationTests(unittest.TestCase):
    def fixture(self, directory):
        plan=json.loads(PLAN.read_text());save(directory/'plan.json',plan)
        save(directory/'source_hashes.json',plan['source_hashes'])
        save(directory/'backend_installation_hashes.json',plan['backend_installation_hashes'])
        save(directory/'metadata.json',dict(version={'version':plan['reported_api_version']},
             tags={'models':[{'name':plan['model'],'digest':plan['model_digest']}]}))
        entry=next(e for e in plan['inputs'] if e['input_id']=='c07_short')
        b=json.loads((ROOT/entry['path']).read_text());facts=execution_facts(b)
        save(directory/'facts/c07_short.json',facts)
        for arm in plan['arms']:
            save(directory/f'calls/c07_short__{arm}_request.json',payload(b,arm,plan))
        obj=dict(execution='executed',authorization='supported',executed_unauthorized_in_scope=False,
                 authorized_amount=100,observed_amount=100,excess_amount=0,
                 evidence=[{'source_id':'user_request','quote':b['sources'][0]['text']}],rationale='Synthetic evaluation fixture')
        stem=directory/'calls/c07_short__legacy_with_facts'
        save(str(stem)+'_response.json',dict(done=True,done_reason='stop',eval_count=100,
             prompt_eval_count=plan['capacity']['c07_short']['legacy_with_facts'],response=json.dumps(obj)))
        save(str(stem)+'_parsed.json',obj);save(str(stem)+'_report.json',guard_output(obj,b))
        summary=dict(status='budget_exhausted',stopped_arms=[],calls=[
            dict(input_id='c07_short',arm='legacy_with_facts',status='parsed'),
            dict(input_id='c07_short',arm='split_interface',status='cancelled')])
        save(directory/'summary.json',summary)
        return summary

    def test_incomplete_failure_keeps_denominator_and_unknown_cost(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p);r=analyze(p)
            self.assertEqual(len(r['missing_calls']),24)
            self.assertEqual(r['counts']['split_interface']['planned'],13)
            self.assertEqual(r['counts']['split_interface']['missing'],12)
            self.assertEqual(r['counts']['split_interface']['missing_final_token_counts'],1)
            self.assertEqual(r['counts']['split_interface']['raw_reference_core'],0)
            # Correct raw label is not delivered success when the guard rejects it.
            self.assertEqual(r['counts']['legacy_with_facts']['raw_reference_core'],1)
            self.assertEqual(r['counts']['legacy_with_facts']['delivered_reference_core'],0)

    def test_complete_claim_and_response_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);summary=self.fixture(p)
            bad=copy.deepcopy(summary);bad['status']='complete';save(p/'summary.json',bad)
            with self.assertRaises(AssertionError):analyze(p)
            save(p/'summary.json',summary)
            response=p/'calls/c07_short__legacy_with_facts_response.json'
            value=json.loads(response.read_text());value['prompt_eval_count']-=1;save(response,value)
            with self.assertRaises(AssertionError):analyze(p)


if __name__=='__main__':unittest.main()
