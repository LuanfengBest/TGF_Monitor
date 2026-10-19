import copy
import unittest
import freeze_tgf_main_v3 as f

class ReferenceGateTests(unittest.TestCase):
    def setUp(self):
        self.run=f.p.ROOT/'results/prospective_actor_v6_29664777'
        self.reference=f.p.read(f.p.ROOT/'analysis/prospective_v6_reference_review_20261015.json')
        self.planned=self.reference['planned_trace_ids']
    def test_actual_complete_batch(self):
        f.verify_reference(self.reference,self.planned,self.run)
    def test_missing_event_rejected(self):
        bad=copy.deepcopy(self.reference);bad['traces'][0]['events'].pop()
        with self.assertRaises(AssertionError):f.verify_reference(bad,self.planned,self.run)
    def test_missing_trace_rejected(self):
        bad=copy.deepcopy(self.reference);bad['traces'].pop()
        with self.assertRaises(AssertionError):f.verify_reference(bad,self.planned,self.run)
    def test_post_output_review_rejected(self):
        bad=copy.deepcopy(self.reference);bad['reviewed_before_any_monitor_output']=False
        with self.assertRaises(AssertionError):f.verify_reference(bad,self.planned,self.run)
    def test_source_hash_mismatch_rejected(self):
        bad=copy.deepcopy(self.reference);bad['source_hashes'][next(iter(bad['source_hashes']))]='0'*64
        with self.assertRaises(AssertionError):f.verify_reference(bad,self.planned,self.run)

if __name__=='__main__':unittest.main()
