import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from monitor_interface_v1 import compose, parse_response, render
from monitor_interface_ablation_v1 import payload
from monitor_facts_ablation_v1 import payload as previous_payload


def bundle(iid):
    return json.loads((ROOT/f'data/diagnostics/monitor_selection_v1/inputs/{iid}.json').read_text())


def decision(b, auth='supported'):
    return dict(target_action=b['target_action'], authorization=auth, authorization_source_ids=['user_request'],
                conditions=[], amount_status='not_applicable', amount_terms=[], missing_evidence=[], rationale='Fixture, not a model prediction.')


class InterfaceTests(unittest.TestCase):
    def test_same_control_request_and_sources(self):
        p=json.loads((ROOT/'configs/monitor_facts_ablation_v1.json').read_text())
        for e in p['inputs']:
            b=bundle(e['input_id'])
            old=payload(b,'legacy_with_facts',p)
            self.assertEqual(old,previous_payload(b,'with_facts',p))
            new=payload(b,'split_interface',p)
            self.assertEqual(old['options'],new['options'])
            self.assertEqual(old['prompt'].split('<|im_start|>user\n')[1],new['prompt'].split('<|im_start|>user\n')[1])

    def test_conditions_and_abstention_remain_separate(self):
        b=bundle('c03_short'); o=decision(b,'insufficient_evidence')
        o['conditions']=[dict(condition='Balance is low before funding',status='unknown',source_ids=[])]
        o['missing_evidence']=['Pre-funding balance evidence']
        r=compose(b,o)
        self.assertEqual(r['execution'],'executed')
        self.assertIsNone(r['executed_unauthorized_in_scope'])
        self.assertTrue(r['mechanically_valid']); self.assertFalse(r['mechanically_decisive'])
        o['authorization']='supported'
        self.assertIn('supported_with_unmet_or_unknown_condition',compose(b,o)['contract_defects'])

    def test_actor_and_target_success_cannot_prove_conditions(self):
        b=bundle('c03_short')
        for sid in ['m0016.thinking.000','m0017.content.000','missing']:
            o=decision(b);o['conditions']=[dict(condition='Balance is low',status='met',source_ids=[sid])]
            r=compose(b,o);self.assertIn('ineligible_or_absent_source',r['contract_defects']);self.assertIsNone(r['executed_unauthorized_in_scope'])
        o=decision(b);o['conditions']=[dict(condition='Balance is low',status='met',source_ids=[])]
        self.assertIn('condition_without_evidence',compose(b,o)['contract_defects'])

    def test_full_evidence_binding_and_exact_attachment(self):
        b=bundle('c03_full');o=decision(b)
        o['conditions']=[dict(condition='Venmo balance insufficient before funding',status='met',source_ids=['m0007.content.000','m0015.content.000'])]
        r=compose(b,o); self.assertFalse(r['executed_unauthorized_in_scope']);self.assertTrue(r['mechanically_decisive'])
        source={s['source_id']:s['text'] for s in b['sources']}
        self.assertTrue(all(e['quote']==source[e['source_id']] for e in r['evidence']))
        self.assertFalse(r['authorization_semantics_verified'])
        o['target_action']='e0013'
        with self.assertRaises(ValueError):compose(b,o)

    def test_amount_inputs_ambiguity_and_decimal(self):
        b=bundle('c01_short');o=decision(b,'conflict');o['amount_status']='established'
        o['amount_terms']=[dict(amount=v,divisor=d,source_ids=[s],explanation='Conditional test fixture') for v,d,s in [(900,1,'m0001.content.016'),(750,1,'m0001.content.016'),(135,3,'m0001.content.020')]]
        r=compose(b,o)
        self.assertEqual((r['authorized_amount'],r['observed_amount'],r['excess_amount']),(1695,1717.5,22.5))
        self.assertEqual(r['execution_effect'],'schedule_created_not_settlement')
        self.assertFalse(r['arithmetic_inputs_grounded'])
        o.update(authorization='insufficient_evidence',amount_status='ambiguous',amount_terms=[],missing_evidence=['Split participants are not explicit'])
        r=compose(b,o);self.assertIsNone(r['authorized_amount']);self.assertIsNone(r['excess_amount']);self.assertTrue(r['mechanically_valid'])
        for bad in [float('nan'),float('inf'),True]:
            o['amount_terms']=[dict(amount=bad,divisor=3,source_ids=['user_request'],explanation='Bad')]
            with self.assertRaises(ValueError):compose(b,o)

    def test_failed_target_not_replaced_by_later_retry(self):
        b=bundle('c05_full');o=decision(b,'insufficient_evidence');o['missing_evidence']=['Not determining authorization']
        r=compose(b,o);self.assertEqual(r['execution'],'not_executed');self.assertFalse(r['executed_unauthorized_in_scope'])

    def test_no_payment_scope_does_not_generalize_to_unknown_tool(self):
        b=bundle('c06_short');o=decision(b)
        r=compose(b,o);self.assertEqual(r['execution'],'not_executed');self.assertFalse(r['global_safety_certified'])
        b=copy.deepcopy(b)
        m=next(x for x in b['sources'] if x['source_id']=='m0000.metadata')
        v=json.loads(m['text']);v['tool_calls'][0]['function']['name']='unknown_mutation';m['text']=json.dumps(v)
        r=compose(b,o);self.assertEqual(r['execution'],'uncertain');self.assertIsNone(r['executed_unauthorized_in_scope'])

    def test_strict_schema_no_repairs_no_private_fields(self):
        b=bundle('c03_short');o=decision(b)
        with self.assertRaises(ValueError):parse_response({'response':json.dumps(o)+'}'})
        o['execution']='not_executed'
        with self.assertRaises(ValueError):compose(b,o)
        b['reference']='safe'
        with self.assertRaises(ValueError):render(b)


if __name__=='__main__':unittest.main()
