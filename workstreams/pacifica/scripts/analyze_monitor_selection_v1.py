"""Offline integrity and diagnostic reference comparison, never imported by runner."""
import argparse
from pathlib import Path
import json
from monitor_selection_v1 import ROOT, PLAN, DATA, read, sha, render, parse_response, validate_output
from native_ollama_tokenizer import NativeCounter
from ollama_client import save

def validate_request(request, bundle, arm, plan):
    cfg=plan['arms'][arm]
    expected={'model':plan['model'],'prompt':render(bundle,cfg['think']),
              'raw':True,'stream':False,'think':cfg['think'],'keep_alive':'10m',
              'options':{'num_ctx':plan['num_ctx'],'num_predict':plan['num_predict'],
                         'seed':plan['seed'],**{k:v for k,v in cfg.items() if k!='think'}}}
    if request!=expected:
        raise ValueError('Request differs from the complete frozen configuration')

def analyze(directories):
    plan=read(PLAN);refs=read(DATA/'private_reference.json');entries={e['input_id']:e for e in plan['inputs']}
    rows=[];seen=set();counter=NativeCounter()
    for e in entries.values():
        assert sha(ROOT/e['path'])==e['sha256'],e['input_id']
    for directory in directories:
        assert read(directory/'plan.json')==plan
        for path,digest in read(directory/'source_hashes.json').items(): assert sha(ROOT/path)==digest,path
        meta=read(directory/'metadata.json')
        identities=[m for m in meta['tags']['models'] if m['name']==plan['model']]
        assert len(identities)==1 and identities[0]['digest']==plan['model_digest']
        summary=read(directory/'summary.json')
        requests={p.name for p in (directory/'calls').glob('*_request.json')}
        listed={f'{r["input_id"]}__{r["arm"]}_request.json' for r in summary['calls']}
        assert requests==listed,'Unlisted or missing inference request'
        for row in summary['calls']:
            iid,arm=row['input_id'],row['arm'];key=(iid,arm);assert key not in seen;seen.add(key)
            bundle=read(ROOT/entries[iid]['path']);stem=directory/'calls'/f'{iid}__{arm}'
            request=read(str(stem)+'_request.json')
            validate_request(request,bundle,arm,plan)
            responsepath=Path(str(stem)+'_response.json')
            result={'input_id':iid,'arm':arm,'status':row['status'],'reference_scope':refs[iid]['scope']}
            if responsepath.exists():
                response=read(responsepath);expected=counter.check(request['prompt'],plan['num_predict'])
                result['input_count_matches']=response.get('prompt_eval_count')==expected
                result['prompt_tokens']=response.get('prompt_eval_count',0);result['output_tokens']=response.get('eval_count',0)
                result['native_thinking_chars']=len(response.get('thinking',''))
                result['inline_thinking_marker']='</think>' in response.get('response','')
                if row['status']=='parsed':
                    assert result['input_count_matches'],'Parsed result has a token mismatch'
                    assert response.get('done') and response.get('done_reason')!='length'
                    assert response.get('eval_count',0)<plan['num_predict']
                    obj=parse_response(response);assert obj==read(str(stem)+'_parsed.json')
                    result['prediction']=obj;result.update(validate_output(obj,bundle))
                    result['reference_checks']={k:obj[k]==v for k,v in refs[iid]['expected'].items()}
                    result['all_reference_checks']=all(result['reference_checks'].values())
            rows.append(result)
    counts={}
    for arm in plan['arms']:
        rs=[r for r in rows if r['arm']==arm]
        counts[arm]={'attempted':len(rs),'parsed':sum(r['status']=='parsed' for r in rs),
                     'all_reference_checks_passed':sum(r.get('all_reference_checks',False) for r in rs),
                     'citation_count':sum(len(r.get('citation_exact_matches',[])) for r in rs),
                     'citations_exact':sum(sum(r.get('citation_exact_matches',[])) for r in rs),
                     'prompt_tokens':sum(r.get('prompt_tokens',0) for r in rs),
                     'output_tokens':sum(r.get('output_tokens',0) for r in rs)}
    return {'scope':'posthoc selected-event development diagnostic; no held-out or automatic-detection claim',
            'directories':[str(p) for p in directories],'counts':counts,'calls':rows,
            'missing_pairs':sorted([f'{i}__{a}' for i in entries for a in plan['arms'] if (i,a) not in seen]),
            'human_semantic_review':'pending; exact citation matching does not establish relevance'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directories',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=analyze(a.directories);save(a.output,result);print(json.dumps(result['counts'],indent=2))
