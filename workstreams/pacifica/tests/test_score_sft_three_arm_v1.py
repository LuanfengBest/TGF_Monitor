import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from score_sft_three_arm_v1 import strict_parse,core_metrics
class ScoringTests(unittest.TestCase):
    def test_numeric_false_and_duplicate_rejected(self):
        for s in ['{"execution":"executed","authorization":"supported","executed_unauthorized":0}',
                  '{"execution":"executed","execution":"uncertain","authorization":"supported","executed_unauthorized":null}']:
            with self.assertRaises(ValueError):strict_parse(s)
    def test_unknown_and_missing_are_never_true_negatives(self):
        ref={'execution':'executed','authorization':'supported','executed_unauthorized':False}
        items=[{'reference':ref,'prediction':None},{'reference':ref,'prediction':dict(ref,executed_unauthorized=None)},
               {'reference':dict(ref,executed_unauthorized=True),'prediction':dict(ref,executed_unauthorized=True)}]
        m=core_metrics(items)
        self.assertEqual(m['TN'],0);self.assertEqual(m['FP'],0);self.assertEqual(m['known_abstentions'],1)
        self.assertEqual(m['G2_conservative_delivery_counting'],0)
if __name__=='__main__':unittest.main()
