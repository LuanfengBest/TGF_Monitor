"""Verify frozen inputs and contracts without model/API/GPU work."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import socket
from . import core
from .run import DEFAULT, verify_manifest, planned, read


def verify(bundle=DEFAULT):
    seal=verify_manifest(bundle)
    requests=planned(bundle)
    public={r['case_id']:r for r in (core.strict_json(s) for s in (bundle/'public_inputs.jsonl').read_text().splitlines())}
    labels={r['case_id']:r for r in (core.strict_json(s) for s in (bundle/'labels_PRIVATE.jsonl').read_text().splitlines())}
    if set(public)!=set(labels) or len(public)!=60:
        raise ValueError('All 60 paired cases required')
    by_case=defaultdict(dict)
    for r in requests:
        by_case[r['case_id']][r['arm']]=r
        if r['phase']=='development' and r['state']['record']!=public[r['case_id']]['record']:
            raise ValueError('Original public record changed')
        unsafe={'source_case_id','hidden_goal','private_state','reference','reference_violation','label','old_judge','condition','block'}
        def scan(value):
            if isinstance(value,dict):
                if set(value)&unsafe: raise ValueError('Private bookkeeping key in state')
                for child in value.values():scan(child)
            elif isinstance(value,list):
                for child in value:scan(child)
        scan(r['state'])
    for cid,arms in by_case.items():
        if set(arms)!=set('ABCD'):
            raise ValueError('Missing arm')
        if arms['A']['state']!=arms['C']['state'] or arms['B']['state']!=arms['D']['state']:
            raise ValueError('Observation mismatch across models')
        if arms['A']['state']['record']!=arms['B']['state']['record']:
            raise ValueError('Ledger treatment replaced original evidence')
    if Counter(r['model'] for r in requests)!=Counter({'jev':124,'qwen':124}):
        raise ValueError('Wrong actual request reservation')
    if Counter(r['phase'] for r in requests)!=Counter({'development':240,'smoke':8}):
        raise ValueError('Wrong phase counts')
    labels_per_hash=defaultdict(set)
    for cid,row in public.items():
        if row['public_sha256']!=core.digest(row['record']):
            raise ValueError('Public hash mismatch')
        labels_per_hash[row['public_sha256']].add(labels[cid]['label'])
        if labels[cid]['source_case_id'] in core.canonical(row['record']):
            raise ValueError('Potential source-case identity leak')
    if any(len(x)!=1 for x in labels_per_hash.values()):
        raise ValueError('Identical public input has conflicting inherited labels')
    saved={r['case_id']:r['fact_ledger'] for r in (core.strict_json(s) for s in (bundle/'ledger.jsonl').read_text().splitlines())}
    for cid,arms in by_case.items():
        if saved[cid]!=core.ledger(arms['A']['state']['record']):
            raise ValueError('Ledger not reproducible from public record')
    capacity=read(bundle/'capacity_LOCAL.json')
    if capacity['qwen_requests']!=124 or not capacity['all_qwen_inputs_fit']:
        raise ValueError('Qwen capacity incomplete')
    rules=read(bundle/'rule_results.json')
    covered=[r for r in rules if r['verdict']!='unknown']
    return {'manifest_sha256':seal,'verified':True,'model_calls':0,'planned_development':240,'planned_smoke':8,
            'public_records':60,'unique_public_records':len(labels_per_hash),'instance_blocks':len({r['block'] for r in labels.values()}),
            'rule_covered':len(covered),'rule_reference_disagreements':sum(r['verdict']!=labels[r['case_id']]['label'] for r in covered),
            'jev_live_token_count_and_cluster_admission':'not verified offline'}


if __name__=='__main__':
    def forbid(*args,**kwargs):raise RuntimeError('Offline verification forbids network access')
    socket.socket.connect=forbid
    socket.create_connection=forbid
    print(core.canonical(verify()))
