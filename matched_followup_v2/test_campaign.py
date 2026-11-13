import tempfile
import unittest
from pathlib import Path
from .common import CONFIG, load, save
from .budget import Budget, slots
from .gate import pilot_gate
from .review import validate_reference
from .schemas import output_schema
from .test_protocol import case_fixture, unknown_judge


class CampaignTests(unittest.TestCase):
    def test_budget_and_no_replay(self):
        c = load(CONFIG)
        self.assertLessEqual(len(c['cases']), 64)
        self.assertLessEqual(len(slots(c)), 600)
        self.assertEqual(c['limits']['wall_seconds'], 14400)
        self.assertEqual(c['limits']['retries'], 0)
        with tempfile.TemporaryDirectory() as d:
            b = Budget(Path(d)/'run', c)
            b.initialize({})
            with self.assertRaises(FileExistsError): b.initialize({})
            b.dispatch('c00.planner', 20, 'fixture')
            with self.assertRaises(FileExistsError): b.dispatch('c00.planner', 20, 'fixture')

    def test_unlabelled_does_not_fabricate_gold(self):
        c = load(CONFIG)
        self.assertEqual(validate_reference([], c, {})['cases'], {})
        with self.assertRaises(ValueError): validate_reference(['fake.json'], c, {})
        with self.assertRaises(ValueError): validate_reference([], dict(c, study_kind='confirmatory'), {})

    def test_schema_citations_and_unknowns(self):
        case = case_fixture()
        schema = output_schema('judge', case)
        self.assertEqual(schema['properties']['unknown_reason']['minLength'], 1)
        ids = schema['properties']['authorization_violation']['properties']['evidence']['items']['properties']['sources']['items']['enum']
        self.assertIn('m00003', ids)
        self.assertNotIn('m00000', ids)
        self.assertIsNone(output_schema('actor', case))

    def test_gate_requires_resolved_pairs_and_stops_expansion(self):
        c = load(CONFIG)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for cid in c['pilot_cases']:
                p = f"c{c['cases'].index(cid):02d}"
                save(root/'selection'/(p+'.json'), {'status':'selected'})
                for arm in ('P','L','F','T'):
                    j = unknown_judge()
                    j['authorization_violation']['score'] = 0
                    save(root/'judgments'/(p+'.'+arm+'.json'), {'status':'valid','judgment':j})
            self.assertTrue(pilot_gate(root,c)['passed'])
            for i in range(3):
                save(root/'judgments'/f'c{i:02d}.T.json', {'status':'unknown','judgment':None})
            self.assertFalse(pilot_gate(root,c)['passed'])
