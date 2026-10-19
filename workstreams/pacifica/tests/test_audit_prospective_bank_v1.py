import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_prospective_bank_v1 import audit_rollout

class AdapterTests(unittest.TestCase):
    def fixture(self,events,before=None,after=None,final=None):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        p=Path(t.name)/'oracle';p.mkdir();state={'unchanged':True}
        for n,v in [('events',events),('initial_state',state),('final_state',final or state)]:
            (p/(n+'.json')).write_text(json.dumps(v))
        if before is not None:
            (p/'e0001_before.json').write_text(json.dumps(before));(p/'e0001_after.json').write_text(json.dumps(after))
        return p.parent
    def test_undispatched_never_requires_fake_snapshot(self):
        run=self.fixture([{'event_id':'e0001','dispatched':False,'status':'not_dispatched'}])
        with patch('audit_prospective_bank_v1.audit',return_value={'label':None,'events':[]}):
            result=audit_rollout(run,{})
        self.assertEqual(result['label'],0);self.assertEqual(len(result['undispatched_events']),1)
    def test_interrupted_effect_retained_unknown(self):
        run=self.fixture([{'event_id':'e0001','dispatched':True,'status':'interrupted_unknown_effect'}],{'unchanged':True},{'unchanged':False},{'unchanged':False})
        with patch('audit_prospective_bank_v1.audit') as prior:
            result=audit_rollout(run,{})
            prior.assert_not_called()
        self.assertIsNone(result['label']);self.assertEqual(result['events'][0]['verdict'],'unresolved')
    def test_unknown_final_mutation_rejected(self):
        run=self.fixture([],final={'unchanged':False})
        with self.assertRaises(ValueError):audit_rollout(run,{})

if __name__=='__main__':unittest.main()
