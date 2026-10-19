"""Bounded interface comparison; both arms use identical visible sources/facts."""
import argparse
import json
import os
from pathlib import Path
import signal
import time
import urllib.error

from monitor_selection_v1 import ROOT, read, sha, parse_response as parse_legacy
from monitor_facts_ablation_v1 import payload as legacy_payload
from monitor_facts_v1 import execution_facts, guard_output
from monitor_interface_v1 import render, parse_response, compose
from native_ollama_tokenizer import NativeCounter
from ollama_client import Ollama, save

PLAN = ROOT / 'configs/monitor_interface_ablation_v1.json'
CODE = ['scripts/monitor_interface_ablation_v1.py', 'scripts/monitor_interface_ablation_v1.sbatch',
        'scripts/monitor_interface_v1.py', 'scripts/analyze_monitor_interface_ablation_v1.py',
        'tests/test_monitor_interface_v1.py', 'scripts/monitor_facts_ablation_v1.py',
        'scripts/monitor_facts_v1.py', 'scripts/observed_execution_v1.py',
        'scripts/monitor_selection_v1.py', 'scripts/native_ollama_tokenizer.py',
        'scripts/ollama_client.py', 'scripts/index_visible_evidence.py',
        'tools/ollama_tokenizer/provenance.json', 'configs/monitor_interface_evaluation_v1.json']


def payload(bundle, arm, plan):
    request = legacy_payload(bundle, 'with_facts', plan)
    if arm == 'split_interface':
        request['prompt'] = render(bundle)
    elif arm != 'legacy_with_facts':
        raise ValueError('Unknown arm')
    return request


def verify(plan):
    for name, digest in plan['source_hashes'].items():
        assert sha(ROOT/name) == digest, name
    for entry in plan['inputs']:
        assert sha(ROOT/entry['path']) == entry['sha256'], entry['input_id']


def prepare():
    if PLAN.exists():
        raise RuntimeError('Frozen protocol already exists')
    old = read(ROOT/'configs/monitor_facts_ablation_v1.json')
    plan = {k: old[k] for k in ('model', 'model_digest', 'num_ctx', 'num_predict', 'seed', 'sampling', 'backend_module')}
    entries = {e['input_id']: e for e in old['inputs']}
    order = ['c07_short', 'c08_short', 'c06_short', 'c03_short', 'c03_full',
             'c05_short', 'c05_full', 'c04_short', 'c04_full', 'c02_short', 'c02_full', 'c01_short', 'c01_full']
    observed=read(ROOT/'results/monitor_facts_backend_observer_29447280.json')
    plan.update(protocol='monitor_interface_ablation_v1', prelaunch_revision=2,
                reported_api_version='0.0.0', backend_installation_hashes=observed['installation_hashes'],
                superseded_unlaunched_plan_sha256=sha(ROOT/'configs/monitor_interface_ablation_v1_prelaunch_rejected_20261013.json'),
                inputs=[entries[i] for i in order],
                arms=['legacy_with_facts', 'split_interface'], max_calls=26, max_gpu_seconds=1800,
                runner_deadline_seconds=1620, automatic_retries=0, max_consecutive_output_failures=2,
                split='existing_development_family_only', source_hashes={p:sha(ROOT/p) for p in CODE},
                comparison='Joint interface/system/output-schema/composition change; same original sources, visible execution facts, base model and sampling. Not a single-feature causal ablation.',
                limits='Specified events and posthoc short views; no held-out generalization. Separate raw decisions, program reports, defects, abstentions and AI semantic review. No training.')
    plan['order'] = [[iid, arm] for i, iid in enumerate(order)
                     for arm in (plan['arms'] if i % 2 == 0 else list(reversed(plan['arms'])))]
    counter = NativeCounter()
    plan['capacity'] = {e['input_id']: {arm:counter.check(payload(read(ROOT/e['path']), arm, plan)['prompt'], plan['num_predict'])
                                      for arm in plan['arms']} for e in plan['inputs']}
    save(PLAN, plan)
    print(json.dumps({'max_calls': 26, 'max_gpu_seconds': 1800,
                      'max_input_tokens': max(v for x in plan['capacity'].values() for v in x.values())}))


def run(out):
    plan = read(PLAN)
    verify(plan)
    with (ROOT/'results/monitor_interface_ablation_v1.reservation.json').open('x') as handle:
        json.dump({'output': str(out), 'job_id': os.environ.get('SLURM_JOB_ID')}, handle)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows, stopped = [], set()
    consecutive = {a: 0 for a in plan['arms']}
    def checkpoint(status, **extra):
        save(out/'summary.json', {'status': status, 'calls': rows, 'stopped_arms': sorted(stopped),
                                 'elapsed_seconds': time.monotonic()-started, **extra})
    def timeout(signum, frame):
        raise TimeoutError('Bounded supervisor deadline')
    signal.signal(signal.SIGTERM, timeout)
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(plan['runner_deadline_seconds'])
    save(out/'plan.json', plan)
    save(out/'source_hashes.json', plan['source_hashes'])
    checkpoint('preflight')
    try:
        installed={name:sha(name) for name in plan['backend_installation_hashes']}
        assert installed == plan['backend_installation_hashes'], 'Backend binary changed'
        save(out/'backend_installation_hashes.json',installed)
        counter, client = NativeCounter(), Ollama(out/'calls')
        metadata = client.metadata(plan['model'])
        save(out/'metadata.json', metadata)
        matching = [m for m in metadata['tags']['models'] if m['name'] == plan['model']]
        assert len(matching) == 1 and matching[0]['digest'] == plan['model_digest']
        assert metadata['version']['version'] == plan['reported_api_version'], 'Unexpected reported API version'
        entries = {e['input_id']: e for e in plan['inputs']}
        for iid, arm in plan['order']:
            if arm in stopped:
                continue
            assert len(rows) < plan['max_calls']
            bundle = read(ROOT/entries[iid]['path'])
            save(out/'facts'/f'{iid}.json', execution_facts(bundle))
            request = payload(bundle, arm, plan)
            expected = counter.check(request['prompt'], plan['num_predict'])
            assert expected == plan['capacity'][iid][arm]
            stem = out/'calls'/f'{iid}__{arm}'
            save(str(stem)+'_request.json', request)
            row = {'input_id': iid, 'arm': arm, 'status': 'started', 'expected_prompt_tokens': expected}
            rows.append(row)
            checkpoint('running')
            before = time.monotonic()
            try:
                response = client.api('generate', request)
            except Exception as exc:
                error = {'error': repr(exc), 'wall_seconds': time.monotonic()-before,
                         'final_token_counts_available': False}
                if isinstance(exc, urllib.error.HTTPError):
                    error['body'] = exc.read().decode(errors='replace')
                save(str(stem)+'_error.json', error)
                row['status'] = 'cancelled' if isinstance(exc, TimeoutError) else 'transport_error'
                raise
            save(str(stem)+'_response.json', response)
            row.update(wall_seconds=time.monotonic()-before,
                       **{k:v for k,v in response.items() if k.endswith(('_count', '_duration'))})
            save(str(stem)+'_usage.json', row)
            if response.get('prompt_eval_count') != expected:
                row['status'] = 'input_count_mismatch'
                raise RuntimeError('Exact input count mismatch')
            if not response.get('done') or response.get('done_reason') == 'length' or response.get('eval_count', 0) >= plan['num_predict']:
                row['status'] = 'output_cap_or_incomplete'
                consecutive[arm] += 1
            else:
                try:
                    obj = parse_legacy(response) if arm == 'legacy_with_facts' else parse_response(response)
                    save(str(stem)+'_parsed.json', obj)
                    report = guard_output(obj, bundle) if arm == 'legacy_with_facts' else compose(bundle, obj)
                    save(str(stem)+'_report.json', report)
                    row['status'] = 'parsed'
                    consecutive[arm] = 0
                except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                    row.update(status='invalid_output', error=repr(exc))
                    consecutive[arm] += 1
            if consecutive[arm] >= plan['max_consecutive_output_failures']:
                stopped.add(arm)
            checkpoint('running')
            print(json.dumps(row), flush=True)
    except BaseException as exc:
        checkpoint('budget_exhausted' if isinstance(exc, TimeoutError) else 'failed', error=repr(exc))
        raise
    finally:
        signal.alarm(0)
    checkpoint('stopped_output_failures' if stopped else 'complete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'verify', 'run'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'verify':
        verify(read(PLAN)); print('Frozen source and input hashes verified')
    elif args.output:
        run(args.output)
    else:
        parser.error('run requires --output')
