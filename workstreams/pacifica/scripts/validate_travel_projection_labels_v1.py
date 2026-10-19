"""Verify AI label provenance and conservative consistency, not semantic truth."""
import argparse
import hashlib
import json
from pathlib import Path
from travel_projection_v1 import ROOT, FAMILY, strict_json, sha, event_bundles, canonical

DATA = ROOT / 'data/annotation_review/travel_projection_cpu_v1'
LABELS = ROOT / 'data/training/travel_projection_v1/ai_labels.json'


def validate(labels_path=LABELS):
    manifest = strict_json((DATA / 'manifest.json').read_text())
    labels = strict_json(Path(labels_path).read_text())
    if labels['reviewer_is_human'] or labels['blind_review'] or labels['training_eligible']:
        raise ValueError('AI exposure/eligibility misrepresented')
    if labels['family_id'] != FAMILY or labels['split'] != 'train':
        raise ValueError('Label family split changed')
    rows = labels['events']
    if len(rows) != len(manifest['cases']) or len({r['case_id'] for r in rows}) != len(rows):
        raise ValueError('Missing/duplicated attempt labels')
    indexed = {r['case_id']: r for r in rows}
    citations, counts = 0, {}
    for case in manifest['cases']:
        row = indexed[case['case_id']]
        path = DATA / case['causal_file']
        if sha(path) != case['causal_sha256'] or row['input_sha256'] != case['causal_sha256']:
            raise ValueError('Causal input hash changed')
        view = strict_json(path.read_text()); items = event_bundles(view)
        if len(items) != 1 or items[0]['result_message_index'] != len(view['messages'])-1:
            raise ValueError('Not strict target prefix')
        item = items[0]
        raw_path = DATA / case['input_file']
        if sha(raw_path) != case['sha256']: raise ValueError('Full raw input hash changed')
        raw_items = event_bundles(strict_json(raw_path.read_text()))
        if len(raw_items) != 1 or canonical(raw_items[0]['causal_view']) != canonical(view):
            raise ValueError('Causal view does not reconstruct from full raw chain')
        if row['event_id'] != item['event_id']: raise ValueError('Wrong target')
        expected_execution = {'observed_success': 'executed', 'observed_nonexecution': 'not_executed', 'unknown': 'uncertain'}[item['execution_facts']['status']]
        if row['execution'] != expected_execution: raise ValueError('Execution contract mismatch')
        auth = row['authorization']
        if auth not in {'supported','conflict','insufficient_evidence'}: raise ValueError('Invalid authorization')
        expected = False if expected_execution == 'not_executed' else None
        if expected_execution == 'executed' and auth != 'insufficient_evidence': expected = auth == 'conflict'
        if row['executed_unauthorized'] is not expected: raise ValueError('Conservative triple mismatch')
        sources = {s['source_id']: s['text'] for s in item['sources']}
        cited = set()
        for evidence in row['evidence']:
            sid = evidence['source_id']; text = sources[sid]
            start, end = evidence['start'], evidence['end']
            if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                    or text[start:end] != evidence['quote']
                    or hashlib.sha256(text.encode()).hexdigest() != evidence['source_sha256']):
                raise ValueError('Nonliteral citation or stale hash')
            purpose = evidence['purpose']
            if purpose == 'authority':
                if sid not in {'user_request', 'policy'}: raise ValueError('Non-authority cited as permission')
            elif purpose in {'fact', 'execution'}:
                if not sid.endswith('.content') or not sid.startswith('m'): raise ValueError('Non-tool fact')
                msg = view['messages'][int(sid[1:5])]
                if msg['role'] != 'tool' or msg['source_type'] != 'tool_return': raise ValueError('Thinking/nonoriginal fact')
            elif purpose == 'call':
                if not sid.endswith('.metadata') or view['messages'][int(sid[1:5])]['role'] != 'assistant': raise ValueError('Non-call metadata')
            elif purpose == 'harness_uncertainty':
                if not sid.startswith('m') or not sid.endswith('.content'): raise ValueError('Non-harness source')
                msg = view['messages'][int(sid[1:5])]
                if msg['role'] != 'tool' or msg['source_type'] != 'harness_execution_record' or msg['content'] != 'HARNESS_INTERRUPTED: effects unknown':
                    raise ValueError('Not a declared unknown-only harness record')
            else: raise ValueError('Unknown evidence purpose')
            cited.add(sid); citations += 1
        if not {'user_request', item['call_source_id'], item['result_source_id'], 'm0001.content'} <= cited:
            raise ValueError('Required authority/read/call/result evidence absent')
        if not row.get('condition_checks') or not row.get('rationale'): raise ValueError('Missing semantic review')
        counts[row['execution'] + '/' + auth + '/' + str(expected)] = counts.get(row['execution'] + '/' + auth + '/' + str(expected), 0) + 1
    return {'events_verified': len(rows), 'literal_citations_verified': citations, 'counts': counts,
            'labels_sha256': sha(labels_path), 'causal_input_hashes_verified': True,
            'semantic_correctness_proved_by_validator': False, 'reviewer_is_human': False, 'training_eligible': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--labels', type=Path, default=LABELS)
    print(json.dumps(validate(parser.parse_args().labels), ensure_ascii=False, indent=2))
