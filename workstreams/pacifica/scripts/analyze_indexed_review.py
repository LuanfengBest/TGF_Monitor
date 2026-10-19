"""Offline provenance/cost audit. Reference labels are joined only in this script."""
import argparse
import hashlib
import json
from pathlib import Path
from ollama_client import digest,save
from run_indexed_review import (ROOT,read,prepare,select_valid,audit_groups,validate_audits,
    aggregate,input_messages,SELECT_SYSTEM,SELECT_SCHEMA,AUDIT_SYSTEM,AUDIT_SCHEMA,MODEL)


def analyze(run):
    plan=read(run/'plan.json');summary=read(run/'summary.json') if (run/'summary.json').exists() else {}
    requests=sorted((run/'calls').glob('call_*_request.json'))
    responses=sorted((run/'calls').glob('call_*_response.json'))
    usages=[read(p) for p in sorted((run/'calls').glob('call_*_usage.json'))]
    cost={'requests':len(requests),'responses':len(responses),'usage_records':len(usages),
        'input_tokens':sum(u.get('prompt_eval_count',0) for u in usages),
        'output_tokens':sum(u.get('eval_count',0) for u in usages),
        'request_wall_seconds':sum(u['wall_seconds'] for u in usages),
        'server_total_seconds':sum(u.get('total_duration',0) for u in usages)/1e9,
        'token_cap_responses':sum(read(p).get('done_reason')=='length' for p in responses),
        'transport_errors':len(list((run/'calls').glob('call_*_error.json'))),'api_charge_usd':None}
    save(run/'cost_audit.json',cost)
    for path,sha in read(run/'source_hashes.json').items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha, ('source_changed',path)
    expected_digest=read(ROOT/'configs/backend_verified_2026-10-12.json')['models'][MODEL]['digest']
    assert {m['name']:m['digest'] for m in read(run/'monitor_metadata.json')['tags']['models']}[MODEL]==expected_digest
    call_no=0;traces=[]
    def verify_call(system,bundle,schema,predict,obj):
        nonlocal call_no
        call_no+=1;stem=run/'calls'/f'call_{call_no:04d}'
        req=read(str(stem)+'_request.json');resp=read(str(stem)+'_response.json')
        expected={'model':MODEL,'messages':input_messages(system,bundle),'stream':False,'think':False,
            'keep_alive':'15m','options':{'num_ctx':32768,'num_predict':predict,'seed':42,'temperature':0},'format':schema}
        assert req==expected, ('payload_changed',call_no)
        assert resp.get('done_reason')!='length', ('capped',call_no)
        assert json.loads(resp['message']['content'])==obj, ('parsed_response_changed',call_no)
    for item in plan['traces']:
        out=run/item['trace_id']
        if not (out/'result.json').exists():
            # A time-limited run can stop mid-trace. Verify every saved request's
            # input provenance even when there is no final per-trace result.
            partial={'trace_id':item['trace_id'],'status':'incomplete_no_result',
                     'partial_requests_verified':0,'partial_selections_verified':0}
            if (out/'selection_inputs.json').exists():
                view=read(ROOT/item['view_path']);assert digest(view)==item['view_sha256']
                index,records,observed,selections=prepare(view)
                assert read(out/'source_index.json')==index
                assert read(out/'canonical_records.json')==records
                assert read(out/'selection_inputs.json')==selections
                assert read(out/'observed_events.json')==observed
                specs=[(SELECT_SYSTEM,b,SELECT_SCHEMA,2048) for b in selections]
                partial_links=[]
                for i,bundle in enumerate(selections):
                    artifact=out/f'selection_{i:02d}.json'
                    if not artifact.exists():break
                    obj=read(artifact);good,bad=select_valid(obj['raw_parsed'],bundle['records'],observed)
                    assert good==obj['accepted_links'] and bad==obj['rejected']
                    resp=read(run/'calls'/f'call_{call_no+i+1:04d}_response.json')
                    assert json.loads(resp['message']['content'])==obj['raw_parsed']
                    partial_links.extend(good);partial['partial_selections_verified']+=1
                if (out/'retrieval_links.json').exists():
                    assert partial['partial_selections_verified']==len(selections)
                    assert read(out/'retrieval_links.json')==partial_links
                    for i,(bundle,overflow) in enumerate(audit_groups(view,observed,records,partial_links)):
                        if (out/f'audit_{i:02d}_input.json').exists():
                            assert read(out/f'audit_{i:02d}_input.json')==bundle
                        if not overflow:specs.append((AUDIT_SYSTEM,bundle,AUDIT_SCHEMA,3072))
                remaining=requests[call_no:]
                assert len(remaining)<=len(specs)
                for req_path,(system,bundle,schema,predict) in zip(remaining,specs):
                    req=read(req_path)
                    expected={'model':MODEL,'messages':input_messages(system,bundle),'stream':False,'think':False,
                        'keep_alive':'15m','options':{'num_ctx':32768,'num_predict':predict,'seed':42,'temperature':0},'format':schema}
                    assert req==expected, ('partial_input_changed',req_path)
                    partial['partial_requests_verified']+=1
            traces.append(partial)
            break
        view=read(ROOT/item['view_path']);assert digest(view)==item['view_sha256']
        index,records,observed,selections=prepare(view)
        assert index==read(out/'source_index.json');assert records==read(out/'canonical_records.json')
        assert observed==read(out/'observed_events.json');assert selections==read(out/'selection_inputs.json')
        links=[];candidates=0;invalid=0;rejection_reasons={};invalid_record_ids=0
        for i,bundle in enumerate(selections):
            artifact=read(out/f'selection_{i:02d}.json');obj=artifact['raw_parsed']
            verify_call(SELECT_SYSTEM,bundle,SELECT_SCHEMA,2048,obj)
            good,bad=select_valid(obj,bundle['records'],observed)
            assert good==artifact['accepted_links'] and bad==artifact['rejected']
            links.extend(good);candidates+=len(obj['selections']);invalid+=len(bad)
            available={r['record_id'] for r in bundle['records']};event_ids={e['event_id'] for e in observed}
            for row in bad:
                if row.get('record_id') not in available:
                    reason='record_id_not_in_supplied_chunk';invalid_record_ids+=1
                elif not row.get('event_ids'):
                    reason='no_associated_event'
                elif any(e not in event_ids for e in row['event_ids']):
                    reason='unknown_associated_event'
                else:reason='association_shape_or_budget'
                rejection_reasons[reason]=rejection_reasons.get(reason,0)+1
        assert links==read(out/'retrieval_links.json')
        rows=[];failures=[];retrieved_counts=[]
        for i,(bundle,overflow) in enumerate(audit_groups(view,observed,records,links)):
            assert bundle==read(out/f'audit_{i:02d}_input.json'), ('retrieval_not_exact',item['trace_id'],i)
            retrieved_counts.append({'group':i,'event_ids':[e['event_id'] for e in bundle['target_events']],
                'records':len(bundle['retrieved_records']),
                'tool_source_records':sum(r['role']=='tool' for r in bundle['retrieved_records']),
                'actor_source_records':sum(r['role']=='assistant' for r in bundle['retrieved_records'])})
            if overflow:failures.append({'group':i,'reason':overflow});continue
            obj=read(out/f'audit_{i:02d}_parsed.json');verify_call(AUDIT_SYSTEM,bundle,AUDIT_SCHEMA,3072,obj)
            try:valid=validate_audits(obj,bundle)
            except ValueError as exc:failures.append({'group':i,'reason':str(exc)});continue
            assert valid==read(out/f'audit_{i:02d}_validated.json');rows.extend(valid)
        result=read(out/'result.json');assert result['audits']==rows and result['failures']==failures
        recomputed=aggregate(rows,[e['event_id'] for e in observed])
        assert all(result[k]==v for k,v in recomputed.items())
        label=read(ROOT/'results/labels_v2'/f"{item['trace_id']}.json")
        traces.append({'trace_id':item['trace_id'],**recomputed,'reference_label':label.get('label'),
            'candidate_selections':candidates,'invalid_selections':invalid,
            'invalid_record_ids':invalid_record_ids,'selection_rejection_reasons':rejection_reasons,
            'unique_retrieved_records':len({l['record_id'] for l in links}),
            'events_with_selected_sources':len({l['event_id'] for l in links}),
            'unresolved_events':sum(r['status']=='needs_review' for r in rows),
            'validation_problem_events':sum(bool(r['validation_problems']) for r in rows),
            'positive_events':[r['event_id'] for r in rows if r['status']=='scored' and r['verdict']=='executed_violation'],
            'retrieval_groups':retrieved_counts,'failures':failures})
    complete=summary.get('status')=='completed'
    if complete:assert call_no==len(requests)==len(responses)==len(usages)==summary['calls']
    result={'status':'verified_complete' if complete else 'partial_run_retained',
        'cost':cost,'verified_call_count':call_no,
        'verified_request_count':call_no+sum(t.get('partial_requests_verified',0) for t in traces),
        'traces':traces,
        'limits':'Exact provenance and syntax checks do not certify relevance, completeness, arithmetic or semantic correctness. Development only; no TGF effect or calibrated performance estimate.'}
    save(run/'offline_analysis.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
    print(json.dumps(analyze(p.parse_args().run),indent=2,ensure_ascii=False))
