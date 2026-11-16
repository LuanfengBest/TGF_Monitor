"""Reproduce the original scorer across both ledgers, without live execution."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def guard(event,args):
    if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo','subprocess.Popen','os.system','os.posix_spawn'}:
        raise RuntimeError('Saved-result analysis blocks network and subprocesses')


def analyze():
    sys.addaudithook(guard)
    from authorization_timing_recovery_v1.common import verify_inputs, BUNDLE, OLD, OLD_SEAL, read, filehash
    from authorization_timing_jev_v2.score import score
    from authorization_timing_jev_v2.run import ensure_smoke
    from jev_monitor_v1.core import digest,parse_response
    amendment,cfg,rows,seal=verify_inputs()
    known={r['request_id']:r for r in rows}
    seen={};counts={'formal_dispatched':0,'formal_returned':0,'formal_valid':0,'all_dispatched':0}
    for folder,expected in [(OLD,OLD_SEAL),(BUNDLE,seal)]:
        for p in sorted((folder/'results').glob('*/dispatch.json')):
            d=read(p);rid=d['request_id'];row=known[rid]
            assert rid not in seen and d['manifest_sha256']==expected and d['attempt']==1
            assert d['request_sha256']==digest(row) and d['model']==row['model'] and d['phase']==row['phase']
            seen[rid]=p.parent;counts['all_dispatched']+=1;counts['formal_dispatched']+=row['phase']=='formal'
            if not (p.parent/'result.json').exists():continue
            r=read(p.parent/'result.json')
            counts['formal_returned']+=row['phase']=='formal'
            counts['formal_valid']+=row['phase']=='formal' and r['status']=='valid'
            assert r['request_id']==rid and r['model']==row['model']
            if r['status'] in {'valid','abstention'}:
                assert r['returned_model']=={'jev':'jev-1.14.0','qwen':'Qwen/Qwen3-32B'}[row['model']]
            if r.get('raw_sha256'):assert filehash(p.parent/'raw.json')==r['raw_sha256']
            if r['status'] in {'valid','abstention'}:
                raw=read(p.parent/'raw.json')
                parsed=parse_response(row['model'],raw['body'] if row['model']=='jev' else raw)
                assert all(r[k]==v for k,v in parsed.items())
            if row['model']=='qwen' and r['status'] in {'valid','abstention'}:
                native=read(p.parent/'raw.json');ready=read(BUNDLE/'results/qwen_ready.json')
                assert native['prompt_sha256']==ready['capacity'][rid]['prompt_sha256']
                assert native['prompt_tokens']==ready['capacity'][rid]['prompt_tokens']
                frozen=next(x for x in read(OLD/'capacity_LOCAL.json')['requests'] if x['request_id']==rid)
                assert digest(native['prompt_token_ids'])==native['prompt_sha256']==frozen['prompt_sha256']
                assert len(native['prompt_token_ids'])==native['prompt_tokens']
                assert len(native['token_ids'])==native['completion_tokens']
                assert r['usage']=={'input_tokens':native['prompt_tokens'],'output_tokens':native['completion_tokens']}
                assert native['completion_tokens']<=512
            if row['model']=='jev' and r['status'] in {'valid','abstention'}:
                assert r['usage']==read(p.parent/'raw.json')['body']['usage']
    assert counts['all_dispatched']<=72
    assert all(sum(known[rid]['model']==m for rid in seen)<=36 for m in ['jev','qwen'])
    with tempfile.TemporaryDirectory() as d:
        directory=Path(d);(directory/'results').mkdir()
        for name in ['references_PRIVATE.json','requests.json']:shutil.copyfile(OLD/name,directory/name)
        for rid,path in seen.items():shutil.copytree(path,directory/'results'/rid)
        analysis=score(directory)
    accounting=read(BUNDLE/'cluster/accounting_final.json')
    assert not accounting['queue']['stdout'].strip()
    assert accounting['prior_gpu']['elapsed_seconds']==1237
    gpu=accounting.get('gpu');cpu=accounting.get('cpu')
    assert gpu and cpu and gpu['elapsed_seconds']<=540 and cpu['elapsed_seconds']<=840
    assert 'gres/gpu:h200=1' in gpu['tres'] and 'gres/gpu' not in cpu['tres']
    gpu_total=1237+gpu['elapsed_seconds'];assert gpu_total<=1800
    assert analysis['usage']['jev']['reserved_api_usd_all_attempts']<=.1
    assert analysis['usage']['qwen']['output_tokens_known']<=18432
    all_done=(counts['formal_returned']==64 and (BUNDLE/'results/qwen_all_finished.json').exists()
              and (BUNDLE/'results/jev_formal_finished.json').exists() and not (BUNDLE/'results/STOP.json').exists())
    if all_done:
        assert gpu['state']=='COMPLETED' and gpu['exit_code']=='0:0'
        assert read(BUNDLE/'results/qwen_all_finished.json')['completed_slots']==36
        assert read(BUNDLE/'results/jev_formal_finished.json')['completed_slots']==32
        ensure_smoke(BUNDLE,'qwen',seal)
        assert read(BUNDLE/'results/qwen_ready.json')['verified_compiled_subgraphs']==65
        assert not (BUNDLE/'results/STOP.json').exists()
    cache_hits=[json.loads(line) for p in (BUNDLE/'results').glob('cache_hits_*.jsonl') for line in p.read_text().splitlines()]
    output={'status':'completed' if all_done else 'incomplete','formal_planned':64,**counts,
            'primary_effect':analysis['contrasts']['jev']['pair_accuracy_difference'] if all_done else None,
            'second_gpu_job':gpu['job_id'],'second_gpu_seconds':gpu['elapsed_seconds'],'aggregate_gpu_seconds':gpu_total,
            'aggregate_h200_hours':gpu_total/3600,'cpu_preflight_job':cpu['job_id'],'cpu_preflight_allocated_seconds':cpu['elapsed_seconds'],
            'cache_unique_subgraphs':len({(x['graph_index'],x['range_start'],x['range_end']) for x in cache_hits}),
            'jev_estimated_api_usd':analysis['usage']['jev']['estimated_api_usd_known'],
            'actual_simulator_bookings':16,'new_simulator_bookings_on_recovery':0,'human_reviews':0,
            'interpretation':'One constructed eight-pair diagnostic, one judgment per cell; no population accuracy, repeated stability or internal reasoning claim.'}
    return analysis,output


def details():
    """Required per-arm costs and every pair member's status, from saved files."""
    from authorization_timing_recovery_v1.common import BUNDLE, OLD, read
    from authorization_timing_jev_v2.score import pair_category
    refs=read(OLD/'references_PRIVATE.json')
    rows=[r for r in read(OLD/'requests.json') if r['phase']=='formal']
    by_slot={(r['model'],r['arm'],r['case_id']):r for r in rows}
    groups={};pairs=[]
    for model in ['jev','qwen']:
        for arm in ['source_card','linked_card']:
            key=model+'.'+arm
            results=[read(BUNDLE/'results'/r['request_id']/'result.json') for r in rows if r['model']==model and r['arm']==arm]
            inputs=sum(r['usage']['input_tokens'] for r in results)
            latency=sum(r['latency_seconds'] for r in results)
            groups[key]={'formal_calls':len(results),'input_tokens':inputs,
                         'output_tokens':sum(r['usage']['output_tokens'] for r in results),
                         'total_request_latency_seconds':latency,'mean_request_latency_seconds':latency/len(results),
                         'estimated_api_usd':inputs*.042/1e6 if model=='jev' else None,
                         'usage_complete_attempts':sum(r['usage_complete'] for r in results),
                         'choice_argmax_mismatches':sum(r.get('choice_argmax_consistent') is False for r in results)}
            for pair_id in sorted({r['pair_id'] for r in refs}):
                references=[next(r for r in refs if r['pair_id']==pair_id and r['variant']==v) for v in ['before','after']]
                members=[]
                for ref in references:
                    row=by_slot[model,arm,ref['case_id']]
                    path=BUNDLE/'results'/row['request_id']/'result.json';result=read(path)
                    members.append({'variant':ref['variant'],'case_id':ref['case_id'],'request_id':row['request_id'],
                                    'reference':ref['label'],'status':result['status'],'verdict':result['verdict'],
                                    'correct':result['status']=='valid' and result['verdict']==ref['label'],
                                    'result_path':str(path.relative_to(ROOT))})
                predictions=[m['verdict'] if m['status']=='valid' else None for m in members]
                category=pair_category([r['label'] for r in references],predictions,references[0]['expected_relation'])
                pairs.append({'group':key,'pair_id':pair_id,'stratum':references[0]['group'],
                              'expected_relation':references[0]['expected_relation'],'members':members,
                              'both_correct':all(m['correct'] for m in members),'category':category})
    return {'formal_groups':groups,'pair_rows':pairs,'human_reviews':0,
            'latency_scope':'Request-only client wall time; excludes queue, GPU startup and cleanup. Different API/local deployments, not a hardware-normalized speed comparison.'}


if __name__=='__main__':
    analysis,outcome=analyze()
    if '--write' in sys.argv:
        b=Path(__file__).resolve().parent/'recovery_01'
        for name,value in [('analysis.json',analysis),('FINAL_OUTCOME.json',outcome)]:
            with (b/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    if '--write-details' in sys.argv:
        with (Path(__file__).resolve().parent/'recovery_01/DETAILS.json').open('x') as f:
            json.dump(details(),f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(outcome,ensure_ascii=False,indent=2))
