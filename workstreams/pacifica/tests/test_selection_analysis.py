import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_monitor_selection_v1 import validate_request
from monitor_selection_v1 import ROOT,PLAN,read

class AnalysisChecks(unittest.TestCase):
    def setUp(self):
        self.plan=read(PLAN)
        self.bundle=read(ROOT/'data/diagnostics/monitor_selection_v1/inputs/c07_short.json')
        self.request=read(ROOT/'results/monitor_selection_smoke_29412254/calls/c07_short__qwen3_current_request.json')

    def test_actual_frozen_request(self):
        validate_request(self.request,self.bundle,'qwen3_current',self.plan)

    def test_sampling_or_thinking_drift_is_rejected(self):
        for key,value in [('temperature',0.8),('num_predict',1024),('seed',43)]:
            changed=copy.deepcopy(self.request);changed['options'][key]=value
            with self.assertRaises(ValueError):validate_request(changed,self.bundle,'qwen3_current',self.plan)
        changed=copy.deepcopy(self.request);changed['think']=True
        with self.assertRaises(ValueError):validate_request(changed,self.bundle,'qwen3_current',self.plan)

    def test_additional_privileged_input_is_rejected(self):
        changed=copy.deepcopy(self.request);changed['messages']=[{'role':'system','content':'reference label'}]
        with self.assertRaises(ValueError):validate_request(changed,self.bundle,'qwen3_current',self.plan)

if __name__=='__main__':unittest.main()
