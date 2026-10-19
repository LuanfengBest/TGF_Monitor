"""Evaluator rejects altered requests and does not count rejection as a pass."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monitor_selection_v1 import ROOT, read
from monitor_facts_ablation_v1 import PLAN
from monitor_facts_v1 import execution_facts, guard_output
from analyze_monitor_facts_ablation_v1 import analyze
from ollama_client import save


class AnalysisTests(unittest.TestCase):
    def fixture(self, directory):
        # Real historical control request is byte-for-byte identical to this control.
        old=ROOT/'results/monitor_selection_smoke_29412254'
        plan=read(PLAN); iid='c07_short'; arm='without_facts'
        bundle=read(ROOT/'data/diagnostics/monitor_selection_v1/inputs/c07_short.json')
        save(directory/'plan.json',plan);save(directory/'source_hashes.json',plan['source_hashes'])
        save(directory/'metadata.json',read(old/'metadata.json'))
        save(directory/'summary.json',{'status':'failed','stopped_arms':[],'calls':[{'input_id':iid,'arm':arm,'status':'parsed'}]})
        save(directory/'facts'/f'{iid}.json',execution_facts(bundle))
        stem=directory/'calls'/f'{iid}__{arm}'
        for suffix in ('request','response','parsed'):
            save(str(stem)+f'_{suffix}.json',read(old/'calls'/f'{iid}__qwen3_recommended_think_{suffix}.json'))
        save(str(stem)+'_guard.json',guard_output(read(str(stem)+'_parsed.json'),bundle))
        return stem

    def test_rejected_correct_prediction_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);result=analyze(d)
            counts=result['counts']['without_facts']['all']
            self.assertEqual(counts['core_pass'],1)
            self.assertEqual(counts['mechanically_accepted'],0)
            self.assertEqual(len(result['missing_pairs']),25)

    def test_modified_request_and_false_completion_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);stem=self.fixture(d)
            p=Path(str(stem)+'_request.json');request=read(p)
            request['options']['temperature']=0;save(p,request)
            with self.assertRaises(AssertionError):analyze(d)
            self.fixture(d);summary=read(d/'summary.json');summary['status']='complete';save(d/'summary.json',summary)
            with self.assertRaises(AssertionError):analyze(d)


if __name__=='__main__':unittest.main()
