"""Secondary diagnostics fixed before formal outputs; never issues model calls."""
import collections
import hashlib
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from tgf_jev_mainline_v1.common import BUNDLE, OUT, read, save, verify
from tgf_jev_mainline_v1.protocol import ARMS
from tgf_jev_mainline_v1.analyze import metrics


def outcome(model, case, arm):
    path = OUT / 'judgments' / model / f'{case}.{arm}' / 'result.json'
    result = read(path) if path.exists() else {'status': 'not_started'}
    return result.get('verdict') if result.get('status') == 'valid' else None


def paired(rows):
    blocks = sorted({r['block'] for r in rows})
    index = {b: i for i, b in enumerate(blocks)}
    rng = np.random.default_rng(2026111202)
    draws = rng.integers(0, len(blocks), (5000, len(blocks))) if blocks else None
    table = {m+'.'+a: metrics(rows, m, a) for m in ('qwen', 'jev') for a in ARMS}
    samples = {}
    for model in ('qwen', 'jev'):
        for arm in ARMS:
            counts = np.zeros((len(blocks), 5))
            for row in rows:
                y = row['label'] == 1
                z = outcome(model, row['case_id'], arm)
                counts[index[row['block']]] += [y, not y, y and z == 'violation',
                                                not y and z == 'authorized', not y and z == 'violation']
            count = counts[draws].sum(axis=1) if blocks else np.empty((0, 5))
            with np.errstate(divide='ignore', invalid='ignore'):
                samples[model+'.'+arm] = {'TPR': count[:, 2]/count[:, 0],
                    'FPR': count[:, 4]/count[:, 1],
                    'G': count[:, 2]/count[:, 0]*count[:, 3]/count[:, 1]}
    contrasts = {}
    for model in ('qwen', 'jev'):
        for control in ('F', 'C', 'P'):
            values = {}
            for metric in ('G', 'TPR', 'FPR'):
                a, b = table[model+'.T'][metric], table[model+'.'+control][metric]
                sample = samples[model+'.T'][metric] - samples[model+'.'+control][metric]
                good = sample[np.isfinite(sample)]
                values[metric] = {'estimate': a-b if a is not None and b is not None else None,
                    'ci95': np.quantile(good, [.025, .975]).tolist() if len(good) else None,
                    'valid_bootstraps': len(good), 'undefined_bootstraps': len(sample)-len(good),
                    'zero_width_is_not_certification': bool(len(good) and good.min() == good.max())}
            contrasts[model+'.T-'+control] = values
    return {'rows': len(rows), 'instance_blocks': len(blocks), 'table': table, 'contrasts': contrasts}


def add_usage(total, model, stage, slot, judge=False):
    key = model+'.'+stage
    acc = total.setdefault(key, {'dispatches': 0, 'returned': 0, 'unknown_usage': 0,
        'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0,
        'inference_seconds': 0., 'request_seconds': 0.})
    if not (slot/'dispatch.json').exists():
        return
    acc['dispatches'] += 1
    raw = read(slot/'raw.json') if (slot/'raw.json').exists() else {}
    acc['returned'] += bool(raw)
    result = read(slot/'result.json') if (slot/'result.json').exists() else {}
    usage = (result.get('usage') or {}) if judge else {
        'input_tokens': raw.get('prompt_tokens'), 'output_tokens': raw.get('completion_tokens')}
    if all(type(usage.get(k)) is int for k in ('input_tokens', 'output_tokens')):
        for k in ('input_tokens', 'output_tokens'):
            acc[k] += usage[k]
        acc['total_tokens'] += usage['input_tokens']+usage['output_tokens']
    else:
        acc['unknown_usage'] += 1
    acc['inference_seconds'] += raw.get('inference_seconds', 0.)
    acc['request_seconds'] += result.get('latency_seconds', 0.)


def main():
    verify()
    assert read(OUT/'qwen_summary.json')['complete']
    assert read(OUT/'jev_summary.json')['complete']
    refs = read(OUT/'reference_manifest_PRIVATE.json')['rows']
    plan = read(OUT/'judge_plan.json')
    methods = read(BUNDLE/'postprocess'/'METHODS.json')
    diagnostic = {'methods': methods, 'environments': {}, 'strategy_deployment_costs': {}}
    packets = []
    for env in ('bank', 'airline'):
        rows = [r for r in refs if r['eligible'] and r['environment'] == env]
        groups = collections.defaultdict(list)
        blocks = collections.defaultdict(list)
        for row in rows:
            groups[row['public_sha256']].append(row)
            blocks[row['block']].append(row)
        representatives = [min(group, key=lambda r: r['case_id']) for group in groups.values()]
        changed = {r['block'] for r in rows for m in ('qwen', 'jev')
                   if outcome(m, r['case_id'], 'T') != outcome(m, r['case_id'], 'F')}
        def rank(block):
            anonymous = min(r['case_id'] for r in blocks[block])
            return hashlib.sha256(('tgf-semantic-audit-v1|'+anonymous).encode()).hexdigest()
        unchanged = sorted(set(blocks)-changed, key=rank)
        sampled = unchanged[:math.ceil(len(unchanged)*.1)]
        selected = changed | set(sampled)
        for row in sorted(rows, key=lambda r: r['case_id']):
            if row['block'] not in selected:
                continue
            cid = row['case_id']
            qa = {}
            for arm in ('F', 'T'):
                f = OUT/'followups'/f'{cid}.{arm}'/'result.json'
                qa[arm] = read(f) if f.exists() else {'status': 'missing'}
                if 'question' in qa[arm]:
                    qa[arm]['question'] = qa[arm]['question'].split('\nPUBLIC ORIGINAL EVIDENCE:')[0]
            packets.append({'case_id': cid, 'environment': env, 'block': row['block'],
                'selection': 'T_F_change' if row['block'] in changed else 'prespecified_unchanged_sample',
                'reference': row, 'public': read(OUT/'public'/f'{cid}.json'), 'qa': qa,
                'outcomes': {m+'.'+a: outcome(m, cid, a) for m in ('qwen', 'jev') for a in ARMS}})
        env_ids = {r['case_id'] for r in rows}
        diagnostic['environments'][env] = {
            'eligible_rows': len(rows), 'unique_public_inputs': len(groups),
            'duplicate_rows_beyond_first': len(rows)-len(groups),
            'duplicate_groups': [[r['case_id'] for r in g] for g in groups.values() if len(g)>1],
            'conflicting_reference_groups': [[r['case_id'] for r in g] for g in groups.values()
                if len({r['label'] for r in g})>1],
            'unique_full_judge_inputs': {a: len({r['state_sha256'] for r in plan
                if r['case_id'] in env_ids and r['arm']==a and r['status']=='ready'}) for a in ARMS},
            'unique_public_sensitivity': paired(representatives),
            'audit_changed_blocks': sorted(changed), 'audit_sampled_unchanged_blocks': sampled,
            'coverage_sufficient': all(len({r['block'] for r in rows if r['label']==y})>=8 for y in (0, 1))}
        for model in ('qwen', 'jev'):
            for arm in ARMS:
                cost = {}
                for row in rows:
                    cid = row['case_id']
                    add_usage(cost, model, 'judge', OUT/'judgments'/model/f'{cid}.{arm}', judge=True)
                    if arm in ('F', 'T'):
                        add_usage(cost, 'actor', 'followup', OUT/'followups'/f'{cid}.{arm}')
                    elif arm == 'C':
                        add_usage(cost, 'qwen', 'review', OUT/'reviews'/cid)
                diagnostic['strategy_deployment_costs'][env+'.'+model+'.'+arm] = cost
    diagnostic['cost_disclosure'] = {'collection': 'Common experimental data generation; separate in frozen RESULTS.json',
        'cpu_selection_and_ledger': 'Zero model calls; actual original CPU runtime not metered',
        'shared_evidence': 'Costs charged in full to each independently deployed strategy; never sum these counterfactual totals as actual experiment cost',
        'qwen_timing': 'Use inference_seconds for GPU model time; request_seconds includes process overhead',
        'jev_timing': 'request_seconds is observed API latency, not GPU time'}
    ratios = {}
    for env in ('bank', 'airline'):
        for model in ('qwen', 'jev'):
            f = diagnostic['strategy_deployment_costs'][env+'.'+model+'.F']
            t = diagnostic['strategy_deployment_costs'][env+'.'+model+'.T']
            ratios[env+'.'+model] = {stage: {k: t.get(stage, {}).get(k, 0)/v[k] if v[k] else None
                for k in ('input_tokens', 'output_tokens', 'total_tokens', 'inference_seconds', 'request_seconds')}
                for stage, v in f.items()}
    diagnostic['T_to_F_cost_ratios'] = ratios
    save(BUNDLE/'SUPPLEMENT.json', diagnostic)
    save(BUNDLE/'postprocess'/'AUDIT_PACKET.json', packets)
    print({'audit_cases': len(packets), 'envs': {e: {k: v[k] for k in ('eligible_rows',
        'unique_public_inputs', 'coverage_sufficient')} for e, v in diagnostic['environments'].items()}})


if __name__ == '__main__':
    main()
