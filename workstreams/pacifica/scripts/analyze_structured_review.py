"""Offline integrity, source coverage and cost analysis; never calls a model."""
import argparse
import hashlib
import json
from pathlib import Path
from ollama_client import digest, save
from run_b1 import parts
from run_structured_review import events, verify_facts, validate_judge
from summarize_costs import summarize

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def analyze(run):
    plan=read(run/'plan.json')
    summary=read(run/'summary.json')
    for name,sha in read(run/'source_hashes.json').items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    rows=[]
    attempts={r['trace_id']:r for r in summary['attempts']}
    for item in plan['traces']:
        name=item['trace_id'];folder=run/name
        row={'trace_id':name,'status':attempts.get(name,{}).get('status','not_called')}
        if not (folder/'chunks.json').exists():
            rows.append(row);continue
        view=read(ROOT/item['view_path'])
        assert digest(view)==item['view_sha256']
        chunks=read(folder/'chunks.json')
        assert chunks==parts(view,10000)
        assert read(folder/'observed_events.json')==events(view)
        kept=[];rejected=[]
        quote_sources={}
        for i,chunk in enumerate(chunks):
            path=folder/f'extraction_{i:02d}.json'
            if not path.exists():break
            extraction=read(path)
            accepted,bad=verify_facts(extraction['raw_parsed'],view,chunk)
            assert accepted==extraction['accepted'] and bad==extraction['rejected']
            kept.extend(accepted);rejected.extend(bad)
            for fact in bad:
                quote=fact.get('quote','')
                mid=fact.get('message_id')
                if len(quote)>160 or len(fact.get('relevance',''))>80:
                    reason='length_limit'
                elif mid not in {part['message_id'] for part in chunk}:
                    reason='message_not_in_supplied_chunk'
                elif quote and quote in view['user_request']:
                    reason='user_request_incorrectly_cited_as_trace_message'
                elif any(quote and quote in msg.get(field,'') for msg in view['messages']
                         for field in ('content','thinking')):
                    reason='wrong_message_id'
                else:
                    reason='not_verbatim_in_any_message'
                quote_sources[reason]=quote_sources.get(reason,0)+1
        if (folder/'review_bundle.json').exists():
            bundle=read(folder/'review_bundle.json')
            assert bundle['verified_source_quotes']==kept
            assert bundle['user_request']==view['user_request'] and bundle['policy']==view['policy']
            assert bundle['observed_events']==events(view)
        else:bundle=None
        row.update(all_original_parts_preserved=True,observed_events=len(events(view)),
                   accepted_quotes=len(kept),rejected_quotes=len(rejected),
                   rejection_categories=quote_sources,
                   quoted_message_ids=sorted(set(f['message_id'] for f in kept)))
        if (folder/'result.json').exists():
            result=read(folder/'result.json')
            assert result['view_sha256']==digest(view)
            status=validate_judge(result,events(view))
            assert status['status']==result['status']
            row.update({k:result[k] for k in ['status','verdict','unauthorized_action_score',
                       'score_verdict_consistent','summary','uncertainties','evidence']})
        # Reference labels are loaded only in this offline analysis, never the model runner.
        label=read(ROOT/'results/labels_v2'/f'{name}.json')
        row['independent_label']=label.get('label')
        row['label_unresolved_events']=label.get('unresolved_events')
        attempt=attempts[name]
        for call_id in range(attempt['start_call'],attempt['end_call']+1):
            request=read(run/'calls'/f'call_{call_id:04d}_request.json')
            payload=json.loads(request['messages'][1]['content'])
            if 'trace_parts' in payload:
                assert payload['trace_parts']==chunks[payload['chunk_id']]
                assert payload['user_request']==view['user_request']
                assert payload['policy']==view['policy']
            else:
                assert payload==bundle
        row['all_runtime_inputs_match_prepared_view_or_verified_bundle']=True
        rows.append(row)
    cost=summarize(run)
    total_responses=sum(r['responses'] for r in cost['by_model'].values())
    assert total_responses==summary['calls'] or summary['status']!='completed'
    output={'scope':plan['scope'],'summary':summary,'rows':rows,'cost':cost,
            'metrics_note':'No threshold fitted and no formal performance claim. Preserve both unresolved reference labels and all model needs_review cases in reporting.'}
    save(run/'offline_analysis.json',output)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    a=p.parse_args();r=analyze(a.run)
    print(json.dumps({'rows':r['rows'],'cost':r['cost']['by_model']},ensure_ascii=False,indent=2))
