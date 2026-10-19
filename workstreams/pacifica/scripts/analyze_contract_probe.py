"""Offline provenance, contract, fixture-semantic and cost audit (no inference)."""
import argparse
import hashlib
import json
from pathlib import Path
from ollama_client import save
from run_contract_probe import (ROOT, prepare_specs, call_spec, groups, decode_audit,
                                decode_selection, MODEL)
from run_structured_review import read
from run_indexed_review import aggregate


def analyze(out):
    plan = read(out / 'plan.json')
    for path, expected in read(out / 'source_hashes.json').items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != expected:
            raise ValueError('Source changed: ' + path)
    meta = read(out / 'monitor_metadata.json')
    if {m['name']:m['digest'] for m in meta['tags']['models']}.get(MODEL) != plan['model_digest']:
        raise ValueError('Monitor digest mismatch')
    specs, view, index, records, observed, targets, selections = prepare_specs(plan)
    if read(out/'source_index.json') != index or read(out/'canonical_records.json') != records:
        raise ValueError('Canonical evidence differs from frozen visible view')
    known = {s['name']:s for s in specs+selections}
    links_path = out/'retrieval_links.json'
    if links_path.exists():
        links = []
        for spec in selections:
            parsed = read(out/'cases'/spec['name']/'parsed.json')
            links.extend(decode_selection(parsed, spec['bundle']))
        if read(links_path) != links:
            raise ValueError('Stored links differ from decoded selection')
        for i, (bundle, error) in enumerate(groups(view, targets, observed, records, links)):
            if not error:
                spec = call_spec(f'real_audit_{i:02d}', 'audit', bundle, plan['trace']['view_path'])
                known[spec['name']] = spec
    attempts = read(out/'attempts.json')
    audits = []
    for row in attempts:
        spec = known[row['name']]
        if read(out/'cases'/row['name']/'spec.json') != spec:
            raise ValueError('Saved spec is not reproducible from frozen visible input')
        request = read(out/'calls'/f"call_{row['call']:04d}_request.json")
        expected = {'model':MODEL, 'messages':spec['messages'], 'stream':False,
                    'think':False, 'keep_alive':'15m', 'options':{'num_ctx':32768,
                    'num_predict':spec['predict'],'seed':42,'temperature':0},'format':spec['schema']}
        if request != expected:
            raise ValueError('Actual request changed: '+row['name'])
        response_path = out/'calls'/f"call_{row['call']:04d}_response.json"
        item = dict(name=row['name'], kind=row['kind'], input_provenance='verified')
        if response_path.exists():
            response = read(response_path)
            try:
                if response.get('done_reason') == 'length':
                    raise ValueError('output_cap')
                obj = json.loads(response['message']['content'])
                decoded = decode_selection(obj,spec['bundle']) if row['kind']=='selection' else decode_audit(obj,spec['bundle'])
                if read(out/'cases'/row['name']/'parsed.json') != obj or read(out/'cases'/row['name']/'decoded.json') != decoded:
                    raise ValueError('Derived output mismatch')
                item.update(contract='passed', decoded_count=len(decoded))
            except (ValueError,FileNotFoundError) as exc:
                item.update(contract='failed', reason=str(exc))
        else:
            item.update(contract='no_response')
        audits.append(item)
    calls = out/'calls'
    reqs = sorted(calls.glob('*_request.json'))
    responses = [read(p) for p in sorted(calls.glob('*_response.json'))]
    usages = [read(p) for p in sorted(calls.glob('*_usage.json'))]
    cost = dict(requests=len(reqs), responses=len(responses), usage_records=len(usages),
                prompt_tokens=sum(x.get('prompt_eval_count',0) for x in usages),
                output_tokens=sum(x.get('eval_count',0) for x in usages),
                request_wall_seconds=sum(x.get('wall_seconds',0) for x in usages),
                server_seconds=sum(x.get('total_duration',0) for x in usages)/1e9,
                capped_responses=sum(x.get('done_reason')=='length' for x in responses),
                transport_errors=len(list(calls.glob('*_error.json'))),
                maximum_actual_prompt_tokens=max((x.get('prompt_eval_count',0) for x in usages),default=0),
                api_charge_usd=None, gpu_seconds='Read from sacct, separate from request time')
    if len(audits) != len(reqs):
        raise ValueError('Request/attempt accounting mismatch')
    expected = read(ROOT/'data/diagnostics/contract_probe_v1/offline_expected.json')
    semantics = []
    for case, rows in expected.items():
        file = out/'cases'/(case+'_audit')/'decoded.json'
        if not file.exists():
            semantics.append(dict(case=case,status='not_completed')); continue
        got = {r['event_id']:r for r in read(file)}
        for e, wanted in rows.items():
            actual = {k:got[e][k] for k in wanted}
            semantics.append(dict(case=case,event_id=e,expected=wanted,actual=actual,
                                  match=actual==wanted, explanation=got[e]))
    result = dict(status='offline_verified', requests_verified=len(audits), contract_audits=audits,
                  synthetic_semantics=semantics, cost=cost,
                  caveat='Development diagnostics; fixture correctness is not real-trajectory performance. No TGF inference.')
    if links_path.exists():
        result['real_event_source_ids'] = {e['event_id']:list(dict.fromkeys(
            x['record_id'] for x in links if x['event_id']==e['event_id'])) for e in targets}
        rows, skips = [], []
        for i, (bundle, error) in enumerate(groups(view, targets, observed, records, links)):
            if error:
                if read(out/'skipped'/f'{i:02d}.json') != bundle:
                    raise ValueError('Skipped evidence bundle differs from original records')
                skips.append(dict(group=i,error=error,targets=[e['event_id'] for e in bundle['target_events']]))
            else:
                file = out/'cases'/f'real_audit_{i:02d}'/'parsed.json'
                if file.exists(): rows.extend(decode_audit(read(file),bundle))
        payment_path = out/'payment_result.json'
        if payment_path.exists():
            reconstructed = {**aggregate(rows,[e['event_id'] for e in targets]),
                'scope':'ONLY payment scheduling events, not a trajectory score','audits':rows,'skips':skips}
            if read(payment_path) != reconstructed:
                raise ValueError('Payment result differs from original responses/skips')
            result['payment_derivation_verified'] = True
            result['payment_events_audited'] = len(rows)
            result['payment_events_skipped'] = len(skips)
    save(out/'offline_analysis.json',result)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    analyze(p.parse_args().output)
