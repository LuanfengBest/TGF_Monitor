"""Bounded validation repair and paired export; no model or training execution."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import signal
import sys
import time

import tgf_sft_qualification_v1 as base
import tgf_sft_qualification_audit_v1 as train_audit
import tgf_sft_eval_fixtures_v1 as fixtures
import tgf_sft_eval_audit_v1 as eval_audit
import tgf_sft_pairs_v1 as pairs
import monitor_sft_candidates_v1 as src

ROOT = src.ROOT
PLAN = ROOT / 'configs/sft_resumption_data_v1.json'
OUT = ROOT / 'data/training/sft_resumption_v1'
REPAIR = ROOT / 'data/evaluation/sft_retention_repair_v1'
PRIVATE = ROOT / 'analysis/sft_retention_repair_v1'
EVAL = ROOT / 'data/evaluation/tgf_sft_pilot_v1'


class DeletePopThenError(dict):
    """Exercise the actual pop operation; never modify the production simulator."""
    def pop(self, key, *default):
        super().pop(key, *default)
        raise RuntimeError('simulated storage error')


def verify_hashes(mapping):
    for name, digest in mapping.items():
        if src.sha(ROOT / name) != digest:
            raise ValueError('Frozen source changed: ' + name)


def freeze():
    paths = {Path(__file__).resolve(), ROOT / 'docs/sft_resumption_plan_2026-10-14.md',
             ROOT / 'results/sft_resumption_decision_20261014.json',
             ROOT / 'tests/test_sft_resumption_data_v1.py'}
    for name in ('tgf_sft_qualification_audit_v1', 'tgf_sft_train_extension_audit_v1',
                 'tgf_sft_eval_generate_v1'):
        p = ROOT / 'configs' / (name + '.json')
        plan = src.read(p)
        verify_hashes(plan['source_hashes'])
        paths.add(p)
        paths.update(ROOT / n for n in plan['source_hashes'])
    for folder in ('data/training/tgf_sft_qualification_v1',
                   'data/training/tgf_sft_train_extension_v1',
                   'data/training/tgf_sft_pairs_v1', 'data/evaluation/tgf_sft_pilot_v1',
                   'data/tokenizers/qwen3_32b'):
        paths.update(p for p in (ROOT / folder).rglob('*') if p.is_file())
    for n in ('qualification', 'train_extension'):
        paths.add(ROOT / f'analysis/tgf_sft_{n}_acceptance_20261014.json')
    paths.add(ROOT / 'analysis/tgf_sft_eval_acceptance_revision1_20261014.json')
    spec = next(s for s in fixtures.specs() if s['case_id'] == 'v011')
    assert spec['family'] == 'retention' and spec['mode'] == 'unknown'
    base.write_new(PLAN, {'frozen_at': datetime.now().astimezone().isoformat(),
        'source_hashes': {str(p.relative_to(ROOT)): src.sha(p) for p in sorted(paths)},
        'repair_spec': spec, 'target_events_max': 1, 'tool_dispatches_max': 3,
        'local_cpu_seconds_max': 30, 'model_calls': 0, 'retry': 0,
        'train_events': 64, 'validation_events': 12, 'final_events': 24})
    return {'sources': len(paths), 'plan_sha256': src.sha(PLAN)}


def repair():
    plan = src.read(PLAN)
    verify_hashes(plan['source_hashes'])
    if REPAIR.exists() or PRIVATE.exists():
        raise ValueError('Existing repair attempt; do not repeat')
    REPAIR.mkdir(parents=True)
    PRIVATE.mkdir(parents=True)
    base.write_new(REPAIR / 'reservation.json', {'plan_sha256': src.sha(PLAN),
        'started_at': datetime.now().astimezone().isoformat()})
    spec = plan['repair_spec']
    view, state, calls, cls = fixtures.fixture(spec)
    assert len(calls) + 1 == 3
    view['messages'] = []
    env = cls(**deepcopy(state))
    runtime = base.FunctionsRuntime([base.make_function(t) for t in env.available_tools])
    audit = []
    deadline = time.monotonic() + 30
    handlers = {s: signal.signal(s, base.on_timeout) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    payload = target = extra = None
    dispatches = 0
    def journal(item):
        with (PRIVATE / 'journal.jsonl').open('a') as f:
            f.write(src.canonical(item) + '\n')
    try:
        for name, args in calls + [('end_task', {})]:
            if name == 'cancel_flight_booking':
                env.ticket_manager.tickets = DeletePopThenError(env.ticket_manager.tickets)
            dispatches += 1
            eid = base.dispatch_record(env, runtime, view, audit, name, args, journal, deadline)
            if name == 'cancel_flight_booking':
                payload = src.make_input(view, eid)
                target, extra = eval_audit.audit(payload, 'retention')
                if target['execution'] != 'uncertain' or target['executed_unauthorized'] is not None:
                    raise ValueError('Required public unknown did not occur')
                record = audit[-1]
                before = record['private_before']['ticket_manager']['tickets']
                after = record['private_after']['ticket_manager']['tickets']
                if len(before) - len(after) != 1 or args['confirmation_number'] in after:
                    raise ValueError('Private deletion fault not reached')
        old = src.read(EVAL / 'v011__e0002.json')
        if payload['user_request'] != old['user_request'] or payload['policy'] != old['policy']:
            raise ValueError('Authority changed')
        # Only the target tool return may differ; original input and parameters stay fixed.
        old_copy, new_copy = deepcopy(old), deepcopy(payload)
        old_copy['messages'][-1]['content'] = new_copy['messages'][-1]['content']
        if old_copy != new_copy:
            raise ValueError('Repair changed more than the target return')
        base.write_new(REPAIR / 'v011__e0002.json', payload)
        base.write_new(REPAIR / 'v011_raw.json', view)
        base.write_new(PRIVATE / 'audit.json', {'spec': spec, 'initial_state': state, 'audit': audit})
        base.write_new(REPAIR / 'reference.json', {'target': target, 'accounting': extra})
        report = {'status': 'repair_verified', 'target_events': 1, 'tool_dispatches': dispatches,
            'public_unknown_preserved': True, 'private_deletion_verified': True,
            'only_target_return_changed': True, 'old_input_sha256': src.sha(EVAL / 'v011__e0002.json'),
            'input_sha256': src.sha(REPAIR / 'v011__e0002.json'),
            'reference_sha256': src.sha(REPAIR / 'reference.json'),
            'reviewer_is_human': False, 'model_calls': 0}
        base.write_new(REPAIR / 'receipt.json', report)
        return report
    except BaseException as e:
        base.write_new(REPAIR / 'failure.json', {'error': str(e), 'type': type(e).__name__,
            'tool_dispatches': dispatches, 'no_retry': True})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for s, h in handlers.items():
            signal.signal(s, h)


def mask_check(row):
    p, a = row['prompt_tokens'], row['answer_tokens']
    if row['labels'][:p] != [-100] * p or row['labels'][p:p+a] != row['input_ids'][p:p+a]:
        raise ValueError('Supervision mask mismatch')
    if any(x != -100 for x in row['labels'][p+a:]):
        raise ValueError('Trailing tokens supervised')
    if row['sequence_tokens'] > 4096 or a > 1024:
        raise ValueError('No truncation permitted')


def export():
    plan = src.read(PLAN)
    verify_hashes(plan['source_hashes'])
    rec = src.read(REPAIR / 'receipt.json')
    assert rec['status'] == 'repair_verified'
    assert src.sha(REPAIR / 'v011__e0002.json') == rec['input_sha256']
    assert src.sha(REPAIR / 'reference.json') == rec['reference_sha256']
    rows = []
    for folder, gate in [('tgf_sft_qualification_v1', 'qualification_batch_data_gate_passed'),
                         ('tgf_sft_train_extension_v1', 'extension_data_gate_passed')]:
        stem = 'qualification' if 'qualification' in folder else 'train_extension'
        acceptance = src.read(ROOT / f'analysis/tgf_sft_{stem}_acceptance_20261014.json')
        path = ROOT / 'data/training' / folder / 'candidates.jsonl'
        assert acceptance[gate] is True and src.sha(path) == acceptance['candidate_sha256']
        rows.extend(src.strict_json(s) for s in path.read_text().splitlines())
    encoder = pairs.Encoder()
    arms = {a: [] for a in pairs.ARMS}
    families = defaultdict(set)
    hashes = defaultdict(set)
    pointers = 0
    for row in rows:
        meta = row['metadata']
        assert meta['split'] == 'train'
        target, _ = train_audit.audit(row['input'], meta['domain'])
        if not src.exact_equal(target, row['target']):
            raise ValueError('Train label drift')
        families['train'].add(meta['family_id'])
        hashes['train'].add(src.obj_sha(row['input']))
        pointers += len(target['evidence'])
        aa, bb = pairs.paired_rows(row)
        packed = [encoder.encode(x) for x in (aa, bb)]
        if packed[0]['input_ids'][:packed[0]['prompt_tokens']] != packed[1]['input_ids'][:packed[1]['prompt_tokens']]:
            raise ValueError('Tokenized input mismatch')
        for arm, item, toks in zip(pairs.ARMS, (aa, bb), packed):
            mask_check(toks)
            item['metadata']['use'] = 'effectiveness_train_candidate_runtime_gates_pending'
            arms[arm].append({'metadata': item['metadata'], 'input': item['input'], 'target': item['target'], 'tokens': toks})
    assert len(rows) == 64 and len(hashes['train']) == 64
    evaluation = []
    for ref in src.read(EVAL / 'references.json')['rows']:
        meta = deepcopy(ref['metadata'])
        path = EVAL / meta['input_file']
        assert src.sha(path) == meta['input_sha256']
        target, extra = ref['target'], ref['accounting']
        if meta['case_id'] == 'v011':
            path = REPAIR / 'v011__e0002.json'
            revised = src.read(REPAIR / 'reference.json')
            target, extra = revised['target'], revised['accounting']
            meta.update(input_sha256=src.sha(path), replaced_case='frozen_v011_preserved')
        payload = src.read(path)
        check, detail = eval_audit.audit(payload, meta['family'])
        assert src.exact_equal(target, check) and src.exact_equal(extra, detail)
        prefix = encoder.template.render(messages=[{'role': 'system', 'content': pairs.SYSTEM},
            {'role': 'user', 'content': src.safe_json(payload)}], tools=None,
            add_generation_prompt=True, enable_thinking=False)
        ids = encoder.tokenizer.encode(prefix, add_special_tokens=False).ids
        assert len(ids) + 1024 <= 4096
        meta['prompt_tokens'] = len(ids)
        families[meta['split']].add(meta['family_id'])
        hashes[meta['split']].add(src.obj_sha(payload))
        evaluation.append({'metadata': meta, 'input': payload, 'input_ids': ids,
                           'reference': target, 'accounting': extra})
    splits = ('train', 'validation', 'final_test')
    for i, a in enumerate(splits):
        for b in splits[i+1:]:
            if hashes[a] & hashes[b] or families[a] & families[b]:
                raise ValueError('Split leakage')
    assert len(hashes['validation']) == 12 and len(hashes['final_test']) == 24
    coverage = defaultdict(Counter)
    for row in evaluation:
        coverage[row['metadata']['family']][str(row['reference']['executed_unauthorized'])] += 1
    if any(not all(c[k] > 0 for k in ('True', 'False', 'None')) for c in coverage.values()):
        raise ValueError('Evaluation family coverage incomplete')
    OUT.mkdir(parents=True, exist_ok=False)
    files = {}
    def save_rows(name, data):
        path = OUT / name
        with path.open('x') as f:
            for row in data: f.write(src.canonical(row) + '\n')
        files[name] = src.sha(path)
    for arm, items in arms.items(): save_rows(arm + '.jsonl', items)
    # Separate public inference input from scoring labels; training runner never loads either.
    save_rows('evaluation_inputs.jsonl', [{k:r[k] for k in ('metadata','input','input_ids')} for r in evaluation])
    save_rows('evaluation_references.jsonl', [{k:r[k] for k in ('metadata','reference','accounting')} for r in evaluation])
    base.write_new(OUT / 'system.json', {'system': pairs.SYSTEM})
    files['system.json'] = src.sha(OUT / 'system.json')
    summary = {'status': 'data_gate_passed_runtime_and_gpu_pending', 'data_qualified': True,
        'training_eligible': False, 'train_events': 64, 'validation_events': 12, 'final_events': 24,
        'train_labels': dict(Counter(str(r['target']['executed_unauthorized']) for r in rows)),
        'evaluation_coverage': {k:dict(v) for k,v in coverage.items()},
        'family_ids': {k:sorted(v) for k,v in families.items()}, 'files': files,
        'data_plan_sha256': src.sha(PLAN), 'repair_receipt_sha256': src.sha(REPAIR / 'receipt.json'),
        'train_pointers_verified': pointers, 'input_core_rationale_equal': True,
        'loss_mask_verified': True, 'split_overlap': 0, 'model_calls': 0,
        'token_summary': {a:{k:sum(r['tokens'][k] for r in items) for k in ('prompt_tokens','answer_tokens','sequence_tokens')} for a,items in arms.items()},
        'reviewer_is_human': False, 'independent_review': False, 'human_spot_check_pending': True,
        'synthetic_component_pilot_only': True, 'created_at': datetime.now().astimezone().isoformat()}
    base.write_new(OUT / 'manifest.json', summary)
    verify_hashes(plan['source_hashes'])
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze','repair','export'))
    print(json.dumps(globals()[parser.parse_args().mode](), ensure_ascii=False))
