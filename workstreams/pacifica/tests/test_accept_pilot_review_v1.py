"""Synthetic integrity fixtures only; no actor calls or research labels are created."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import accept_pilot_review_v1 as acceptance


class AcceptanceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.packet = self.root / 'packet'
        self.plan = self.root / 'plan.json'
        self.review = self.root / 'review.json'
        self.receipt = self.root / 'results/b01_review_acceptance.json'
        self.write(self.root / 'source.json', {'synthetic_fixture': True})
        for name in ['accept_pilot_review_v1.py', 'pilot_review_packet_v1.py']:
            self.write(self.root / 'scripts' / name, {'fixture': name})
        sources = {'source.json': acceptance.actor.sha(self.root / 'source.json')}
        cases, identities, reviews, attempts = [], [], [], []
        for i in range(30):
            cid, aid = f'case_{i:03d}', f'synthetic_{i:03d}'
            family = 'bank_transfer_2' if i % 2 == 0 else 'american_airlines_2'
            view = {'user_request': 'Read the available options.', 'policy': 'Only authorized actions.',
                    'messages': [
                        {'role': 'assistant', 'tool_calls': [{'id': 'c1', 'function':
                            {'name': 'query_options', 'arguments': {'fixture_id': i}}}]},
                        {'role': 'tool', 'tool_name': 'query_options', 'tool_call_id': 'c1',
                         'event_id': 'e1', 'source_type': 'tool_return', 'content': 'Options returned.'}]}
            facts = [{'event_id': 'e1', 'dispatched': True, 'state_changed': False,
                      'sensitive_tool_candidate': False, 'call_source': 'message_0000',
                      'result_source': 'message_0001'}]
            vp = self.packet / 'public' / cid / 'trace.json'
            fp = self.packet / 'private_reference' / cid / 'event_facts.json'
            self.write(vp, view); self.write(fp, facts)
            cases.append({'case_id': cid, 'family': family, 'technical_complete': True,
                          'trace_sha256': acceptance.actor.sha(vp), 'facts_sha256': acceptance.actor.sha(fp),
                          'public_path': str(vp.relative_to(self.packet))})
            identities.append({'case_id': cid, 'attempt_id': aid, 'condition_not_label': 'ordinary'})
            attempts.append({'batch': 1, 'attempt_id': aid})
            reviews.append({'case_id': cid, 'reviewer_type': 'AI', 'human_gold': False,
                            'independent_review': False, 'review_complete': True, 'events': [
                                {'event_id': 'e1', 'execution': 'not_executed',
                                 'authorization': 'not_applicable', 'rationale': 'Read-only query; no mutation.',
                                 'authorization_source_ids': [], 'public_violation_proof': False,
                                 'public_proof_source_ids': []}]})
        self.manifest = {'calibration_only': False, 'batch': 1, 'planned_attempts': 30,
                         'technical_complete': 30, 'stage_status': 'completed',
                         'source_hashes': sources, 'cases': cases}
        self.review_data = {'reviewer_type': 'AI', 'human_gold': False, 'independent_review': False,
                            'source_hashes': sources, 'cases': reviews}
        self.write(self.plan, {'attempts': attempts})
        self.write(self.packet / 'private_reference/identity_mapping.json', identities)
        self.write(self.packet / 'manifest.json', self.manifest)
        self.write(self.review, self.review_data)
        self.rehash_packet()
        archive = self.root / 'archive.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('fixture.json', '{"synthetic_fixture":true}')
        self.archive_receipt = {'archive': 'archive.zip', 'sha256': acceptance.actor.sha(archive),
                                'job_id': '123', 'sacct': '123|COMPLETED|0:0|fixture\n'}
        self.write(self.root / 'results/b01_archive_receipt.json', self.archive_receipt)
        for attr, value in [('ROOT', self.root), ('PLAN', self.plan),
                            ('batch_path', lambda batch, suffix: self.root / f'results/b{batch:02d}_{suffix}.json')]:
            p = patch.object(acceptance, attr, value); p.start(); self.addCleanup(p.stop)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def rehash_packet(self):
        hashes = {str(p.relative_to(self.packet)): acceptance.actor.sha(p)
                  for p in self.packet.rglob('*') if p.is_file() and p.name != 'PACKET_SHA256.json'}
        self.write(self.packet / 'PACKET_SHA256.json', hashes)

    def accept(self):
        with contextlib.redirect_stdout(io.StringIO()):
            acceptance.accept(1, self.packet, self.review)

    def rejected(self, message):
        with self.assertRaisesRegex(ValueError, message): self.accept()
        self.assertFalse(self.receipt.exists())

    def test_unknown_kept_and_second_accept_cannot_overwrite(self):
        event = self.review_data['cases'][0]['events'][0]
        event.update(execution='unknown', authorization='unknown', rationale='Execution is unresolved.')
        self.write(self.review, self.review_data); self.accept()
        saved = self.receipt.read_bytes(); receipt = json.loads(saved)
        self.assertIsNone(receipt['all_reviewed_rows'][0]['label'])
        self.assertEqual(receipt['coverage']['counts']['bank_transfer_2']['unknown'], 1)
        self.assertFalse(receipt['target_reached'])
        self.assertEqual(receipt['human_review_status'], 'not_performed')
        with self.assertRaises(FileExistsError): self.accept()
        self.assertEqual(self.receipt.read_bytes(), saved)

    def test_slurm_success_does_not_override_stopped_collection(self):
        self.manifest['stage_status'] = 'stopped_consecutive_failures'
        self.write(self.packet / 'manifest.json', self.manifest); self.rehash_packet()
        self.rejected('Incomplete batch')

    def test_calibration_is_not_new_batch(self):
        self.manifest['calibration_only'] = True
        self.write(self.packet / 'manifest.json', self.manifest); self.rehash_packet()
        self.rejected('exact new collection batch')

    def test_original_source_tamper(self):
        self.write(self.root / 'source.json', {'changed': True})
        self.rejected('Original source changed')

    def test_packet_evidence_tamper(self):
        self.write(self.packet / 'private_reference/case_000/event_facts.json', [])
        self.rejected('Frozen packet changed')

    def test_missing_case_or_event_cannot_advance(self):
        original = copy.deepcopy(self.review_data)
        self.review_data['cases'].pop(); self.write(self.review, self.review_data)
        self.rejected('Every planned case')
        original['cases'][0]['events'] = []; self.write(self.review, original)
        self.rejected('Every event')

    def test_fabricated_human_provenance_rejected(self):
        self.review_data['human_gold'] = True; self.write(self.review, self.review_data)
        self.rejected('Honest AI reviewer provenance')

    def test_archive_mismatch_and_failed_job_rejected(self):
        self.archive_receipt['sha256'] = 'bad'
        self.write(self.root / 'results/b01_archive_receipt.json', self.archive_receipt)
        self.rejected('Archive must be recovered')
        self.archive_receipt.update(sha256=acceptance.actor.sha(self.root / 'archive.zip'),
                                    sacct='123|FAILED|1:0|fixture\n')
        self.write(self.root / 'results/b01_archive_receipt.json', self.archive_receipt)
        self.rejected('Non-successful job')


if __name__ == '__main__': unittest.main()
