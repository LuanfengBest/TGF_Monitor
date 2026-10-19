"""One bounded paired experiment: identical Qwen3 requests except visible facts."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
from monitor_selection_v1 import ROOT, PLAN as OLD_PLAN, read, sha, render, parse_response
from monitor_facts_v1 import augment, execution_facts, guard_output
from native_ollama_tokenizer import NativeCounter
from ollama_client import Ollama, save

PLAN = ROOT / 'configs/monitor_facts_ablation_v1.json'
CODE = ['scripts/monitor_facts_ablation_v1.py', 'scripts/monitor_facts_ablation_v1.sbatch',
        'scripts/monitor_facts_v1.py', 'scripts/observed_execution_v1.py',
        'scripts/monitor_selection_v1.py', 'scripts/native_ollama_tokenizer.py',
        'scripts/ollama_client.py', 'scripts/index_visible_evidence.py',
        'tools/ollama_tokenizer/provenance.json']


def payload(bundle, arm, plan):
    material = augment(bundle) if arm == 'with_facts' else bundle
    return {'model': plan['model'], 'prompt': render(material, True), 'raw': True,
            'stream': False, 'think': True, 'keep_alive': '10m',
            'options': {'num_ctx': plan['num_ctx'], 'num_predict': plan['num_predict'],
                        'seed': plan['seed'], **plan['sampling']}}


def prepare():
    if PLAN.exists():
        raise RuntimeError('Frozen plan exists')
    old = read(OLD_PLAN)
    plan = {k: old[k] for k in ('model', 'model_digest', 'inputs', 'num_ctx', 'num_predict', 'seed', 'system_sha256')}
    plan.update(protocol='monitor_facts_ablation_v1', split='existing_development_family_only',
                arms=['without_facts', 'with_facts'], max_calls=26, max_gpu_seconds=1800,
                automatic_retries=0, max_consecutive_output_failures=2,
                sampling={k:v for k,v in old['arms']['qwen3_recommended_think'].items() if k != 'think'},
                backend_module='ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0',
                source_hashes={p:sha(ROOT/p) for p in CODE},
                comparison='New concurrent control; only added execution_facts in experimental input. Guard applied offline to both arms. No prompt/schema change.',
                limits='Specified-event, posthoc short/full views, no held-out performance. Guard acceptance is mechanical only; abstention not correctness.')
    counter = NativeCounter()
    plan['capacity'] = {e['input_id']: {a:counter.check(payload(read(ROOT/e['path']), a, plan)['prompt'], plan['num_predict']) for a in plan['arms']} for e in plan['inputs']}
    save(PLAN, plan)
    print(json.dumps({'max_calls':26, 'max_input':max(v for x in plan['capacity'].values() for v in x.values())}))


def run(out):
    plan = read(PLAN)
    out.mkdir(parents=True, exist_ok=False)
    with (ROOT/'results/monitor_facts_ablation_v1.reservation.json').open('x') as f:
        json.dump({'output':str(out), 'job_id':os.environ.get('SLURM_JOB_ID')}, f)
    rows = []; stopped = set(); consecutive = {a:0 for a in plan['arms']}
    def checkpoint(status, **extra):
        save(out/'summary.json', {'status':status, 'calls':rows, 'stopped_arms':sorted(stopped), **extra})
    save(out/'plan.json', plan); checkpoint('preflight')
    try:
        for p,h in plan['source_hashes'].items():
            assert sha(ROOT/p) == h, p
        save(out/'source_hashes.json', plan['source_hashes'])
        for e in plan['inputs']:
            assert sha(ROOT/e['path']) == e['sha256']
        counter = NativeCounter(); client = Ollama(out/'calls')
        meta = client.metadata(plan['model']); save(out/'metadata.json', meta)
        models = [m for m in meta['tags']['models'] if m['name'] == plan['model']]
        assert len(models) == 1 and models[0]['digest'] == plan['model_digest']
        for e in plan['inputs']:
            bundle = read(ROOT/e['path'])
            save(out/'facts'/f'{e["input_id"]}.json', execution_facts(bundle))
            for arm in plan['arms']:
                if arm in stopped: continue
                assert len(rows) < plan['max_calls']
                request = payload(bundle, arm, plan)
                count = counter.check(request['prompt'], plan['num_predict'])
                assert count == plan['capacity'][e['input_id']][arm]
                stem = out/'calls'/f'{e["input_id"]}__{arm}'
                save(str(stem)+'_request.json', request)
                row = {'input_id':e['input_id'], 'arm':arm, 'expected_prompt_tokens':count, 'status':'started'}
                rows.append(row); checkpoint('running'); start = time.monotonic()
                try:
                    response = client.api('generate', request)
                except Exception as exc:
                    err = {'error':repr(exc), 'wall_seconds':time.monotonic()-start}
                    if isinstance(exc, urllib.error.HTTPError): err['body'] = exc.read().decode(errors='replace')
                    save(str(stem)+'_error.json', err); row['status'] = 'transport_error'; raise
                save(str(stem)+'_response.json', response)
                row.update(wall_seconds=time.monotonic()-start, **{k:v for k,v in response.items() if k.endswith(('_count','_duration'))})
                save(str(stem)+'_usage.json', row)
                if response.get('prompt_eval_count') != count:
                    row['status'] = 'input_count_mismatch'; raise RuntimeError('Input count mismatch; no tolerance')
                if not response.get('done') or response.get('done_reason') == 'length' or response.get('eval_count',0) >= plan['num_predict']:
                    row['status'] = 'output_cap_or_incomplete'; consecutive[arm] += 1
                else:
                    try:
                        obj = parse_response(response); save(str(stem)+'_parsed.json', obj)
                        checks = guard_output(obj, bundle); save(str(stem)+'_guard.json', checks)
                        row.update(checks); row['status'] = 'parsed'; consecutive[arm] = 0
                    except (ValueError, TypeError, KeyError) as exc:
                        row['status'] = 'invalid_output'; row['error'] = repr(exc); consecutive[arm] += 1
                if consecutive[arm] >= plan['max_consecutive_output_failures']: stopped.add(arm)
                checkpoint('running'); print(json.dumps(row), flush=True)
    except Exception as exc:
        checkpoint('failed', error=repr(exc)); raise
    checkpoint('stopped_output_failures' if stopped else 'complete')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['prepare','run']); p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.command == 'prepare': prepare()
    elif args.output: run(args.output)
    else: p.error('run requires --output')
