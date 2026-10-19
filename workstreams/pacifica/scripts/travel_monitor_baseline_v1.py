"""One frozen, six-call Qwen diagnostic. No labels or reference computation at runtime."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
from monitor_v2_baseline_v1 import BoundedClient
from native_ollama_tokenizer import NativeCounter
from travel_monitor_contract_v1 import SYSTEM, build_input, render, parse_response, guard
from travel_projection_v1 import ROOT, sha, strict_json, canonical, exact_equal

PLAN = ROOT / 'configs/travel_monitor_baseline_v1.json'
DATA = ROOT / 'data/diagnostics/travel_monitor_baseline_v1'
PACKET = ROOT / 'data/annotation_review/travel_projection_cpu_v1'
CPU_PLAN = ROOT / 'configs/travel_projection_cpu_v1.json'
RESERVATION = ROOT / 'results/travel_monitor_baseline_v1.reservation.json'
BUDGET = {'max_calls': 6, 'max_gpu_seconds': 900, 'runner_deadline_seconds': 760,
          'max_http_seconds': 120, 'max_consecutive_output_failures': 2,
          'automatic_retries': 0, 'max_gpu_jobs': 1, 'training_runs': 0}
CODE = ['scripts/travel_monitor_contract_v1.py', 'scripts/travel_monitor_baseline_v1.py',
        'scripts/travel_monitor_baseline_v1.sbatch', 'scripts/analyze_travel_monitor_baseline_v1.py',
        'tests/test_travel_monitor_baseline_v1.py', 'docs/travel_monitor_baseline_protocol_2026-10-14.md',
        'tools/ollama_tokenizer/provenance.json']


def read(path):
    return strict_json(Path(path).read_text())


def durable_save(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open('x') as f:
            f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            f.flush(); os.fsync(f.fileno())
    else:
        temporary = path.with_suffix(path.suffix + '.tmp')
        with temporary.open('w') as f:
            f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            f.flush(); os.fsync(f.fileno())
        os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def payload(bundle, plan):
    return {'model': plan['model'], 'prompt': render(bundle), 'raw': True, 'stream': False,
            'think': True, 'keep_alive': '10m', 'options': {'num_ctx': plan['num_ctx'],
            'num_predict': plan['num_predict'], 'seed': plan['seed'], **plan['sampling']}}


def prepare():
    if PLAN.exists() or DATA.exists():
        raise ValueError('Preparation already exists; never overwrite')
    from prepare_travel_projection_v1 import verify as verify_cpu
    cpu = verify_cpu()
    manifest_path = PACKET / 'manifest.json'
    manifest = read(manifest_path)
    if manifest['status'] != 'complete' or len(manifest['cases']) != 6 or manifest['plan_sha256'] != sha(CPU_PLAN):
        raise ValueError('CPU generation mismatch')
    old_path = ROOT / 'configs/monitor_v2_baseline_v1.json'
    old = read(old_path)
    p = {k: deepcopy(old[k]) for k in ('model', 'model_digest', 'num_ctx', 'num_predict', 'seed', 'sampling', 'backend_installation_hashes')}
    p.update(BUDGET)
    p.update(protocol='travel_monitor_baseline_v1', split='train_scripted_diagnostic',
             system_sha256=hashlib.sha256(SYSTEM.encode()).hexdigest(), inputs=[],
             reference_labels_in_prompt=False, execution_decoder_in_prompt=False,
             final_test_events=0, training_eligible=False,
             limits='One scripted train family, no independent test or training result. Common email contract, not prompt ablation versus older baselines.')
    paths = {ROOT / q for q in CODE} | {CPU_PLAN, manifest_path, old_path}
    # Freeze all imported repository Python dependencies, plus the original CPU closure.
    paths.update(ROOT / q for q in cpu['file_hashes'])
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            q = Path(filename).resolve()
            if q.suffix == '.py' and q.is_relative_to(ROOT) and '.venv' not in q.parts:
                paths.add(q)
    p['source_hashes'] = {str(q.relative_to(ROOT)): sha(q) for q in sorted(paths)}
    counter = NativeCounter()
    pending = []
    expected_ids = [f'p{i:03d}' for i in range(1, 7)]
    if [c['case_id'] for c in manifest['cases']] != expected_ids:
        raise ValueError('Unexpected case selection/order')
    for c in manifest['cases']:
        if c['split'] != 'train' or c['send_attempts'] != 1:
            raise ValueError('Split or event coverage changed')
        full = PACKET / c['input_file']; causal = PACKET / c['causal_file']
        if sha(full) != c['sha256'] or sha(causal) != c['causal_sha256']:
            raise ValueError('Raw/causal source changed')
        view = read(causal)
        original = read(full)
        original['messages'] = original['messages'][:len(view['messages'])]
        if not exact_equal(original, view):
            raise ValueError('Causal view is not original prefix')
        bundle = build_input(view, cpu['public_schemas'])
        if bundle['target_action'] != c['target_event']:
            raise ValueError('Target mismatch')
        dest = DATA / (c['case_id'] + '.json')
        count = counter.check(payload(bundle, p)['prompt'], p['num_predict'])
        p['inputs'].append({'input_id': c['case_id'], 'event_id': c['target_event'],
            'path': str(dest.relative_to(ROOT)), 'expected_prompt_tokens': count,
            'view_path': str(causal.relative_to(ROOT)), 'view_sha256': sha(causal),
            'raw_path': str(full.relative_to(ROOT)), 'raw_sha256': sha(full),
            'split': 'train', 'family_id': c['family_id']})
        pending.append((dest, bundle))
    DATA.mkdir(parents=True)
    for (dest, bundle), row in zip(pending, p['inputs']):
        durable_save(dest, bundle, exclusive=True); row['sha256'] = sha(dest)
    durable_save(PLAN, p, exclusive=True)
    print(json.dumps({'inputs': 6, 'plan_sha256': sha(PLAN), 'source_files': len(paths),
                      'prompt_tokens': [r['expected_prompt_tokens'] for r in p['inputs']], **BUDGET}))


def verify(p=None):
    p = read(PLAN) if p is None else p
    for k, v in BUDGET.items():
        if type(p[k]) is not type(v) or p[k] != v:
            raise ValueError('Changed budget: ' + k)
    if len(p['inputs']) != 6 or [x['input_id'] for x in p['inputs']] != [f'p{i:03d}' for i in range(1, 7)]:
        raise ValueError('Changed input coverage/order')
    if hashlib.sha256(SYSTEM.encode()).hexdigest() != p['system_sha256']:
        raise ValueError('System changed')
    for q, h in p['source_hashes'].items():
        if sha(ROOT / q) != h:
            raise ValueError('Source changed: ' + q)
    schemas = read(CPU_PLAN)['public_schemas']
    for row in p['inputs']:
        for pk, hk in [('path', 'sha256'), ('view_path', 'view_sha256'), ('raw_path', 'raw_sha256')]:
            if sha(ROOT / row[pk]) != row[hk]:
                raise ValueError('Input source changed: ' + pk)
        bundle = read(ROOT / row['path'])
        if not exact_equal(bundle, build_input(read(ROOT / row['view_path']), schemas)):
            raise ValueError('Input not derived solely from public causal evidence')
    return p


class DiagnosticInterrupted(BaseException):
    pass


def interrupted(signum, frame):
    raise DiagnosticInterrupted('Diagnostic signal ' + str(signum))


def execute(p, out, client, counter, deadline):
    """Bounded core, injectable only by local tests; never retries or uses labels."""
    rows = []; started = time.monotonic(); status = 'preflight'; failures = 0
    def checkpoint():
        durable_save(out / 'summary.json', {'status': status, 'calls': rows,
            'elapsed_seconds': time.monotonic() - started,
            'not_attempted': [e['input_id'] for e in p['inputs'] if e['input_id'] not in {r['input_id'] for r in rows}]})
    checkpoint()
    try:
        for name, expected in p['backend_installation_hashes'].items():
            if sha(name) != expected:
                raise ValueError('Pinned backend changed')
        meta = client.metadata(p['model']); durable_save(out / 'metadata.json', meta)
        matches = [m for m in meta['tags']['models'] if m['name'] == p['model']]
        if len(matches) != 1 or matches[0]['digest'] != p['model_digest'] or meta['version']['version'] != '0.0.0':
            raise ValueError('Model/backend identity mismatch')
        client.timeout = p['max_http_seconds']
        for e in p['inputs']:
            if deadline - time.monotonic() < p['max_http_seconds'] + 35:
                status = 'budget_stop'; break
            bundle = read(ROOT / e['path']); request = payload(bundle, p)
            count = counter.check(request['prompt'], p['num_predict'])
            if count != e['expected_prompt_tokens']:
                raise ValueError('Frozen tokenizer count changed')
            if len(rows) >= p['max_calls']:
                raise ValueError('Call budget exceeded')
            stem = out / 'calls' / e['input_id']
            durable_save(str(stem) + '_request.json', request, exclusive=True)
            row = {'input_id': e['input_id'], 'expected_prompt_tokens': count,
                   'status': 'dispatch_pending', 'final_usage_unknown': True}
            rows.append(row); status = 'running'; checkpoint()
            call_start = time.monotonic()
            try:
                r = client.api('generate', request)
            except BaseException as exc:
                row.update(status='transport_or_interruption', error=repr(exc),
                           wall_seconds=time.monotonic() - call_start)
                durable_save(str(stem) + '_error.json', row); raise
            durable_save(str(stem) + '_response.json', r, exclusive=True)
            row.update(status='response_received', final_usage_unknown=False,
                       wall_seconds=time.monotonic() - call_start,
                       **{k: v for k, v in r.items() if k.endswith(('_count', '_duration'))})
            durable_save(str(stem) + '_usage.json', row); checkpoint()
            if r.get('prompt_eval_count') != count:
                row['status'] = 'input_count_mismatch'; raise ValueError('Backend input count differs')
            if not r.get('done') or r.get('done_reason') == 'length' or r.get('eval_count', 0) >= p['num_predict']:
                row['status'] = 'output_cap_or_incomplete'; failures += 1
            else:
                try:
                    obj = parse_response(r); checks = guard(obj, bundle)
                    durable_save(str(stem) + '_parsed.json', obj)
                    durable_save(str(stem) + '_guard.json', checks)
                    row.update(status='parsed', **checks); failures = 0
                except (ValueError, TypeError, KeyError) as exc:
                    row.update(status='invalid_output', error=repr(exc)); failures += 1
            checkpoint(); print(json.dumps(row), flush=True)
            if failures >= p['max_consecutive_output_failures']:
                status = 'stopped_output_failures'; break
        else:
            status = 'complete'
    except BaseException as exc:
        status = 'failed'; durable_save(out / 'error.json', {'error': repr(exc)}); raise
    finally:
        checkpoint()


def run(out):
    p = verify(); out = Path(out)
    if out.exists():
        raise ValueError('Output exists')
    durable_save(RESERVATION, {'job_id': os.environ.get('SLURM_JOB_ID'),
        'output': str(out), 'plan_sha256': sha(PLAN)}, exclusive=True)
    out.mkdir(parents=True, exist_ok=False)
    durable_save(out / 'plan.json', p, exclusive=True)
    deadline = time.monotonic() + p['runner_deadline_seconds']
    old = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    for s in old:
        signal.signal(s, interrupted)
    signal.setitimer(signal.ITIMER_REAL, p['runner_deadline_seconds'])
    try:
        client = BoundedClient(out / 'calls', deadline)
        execute(p, out, client, NativeCounter(), deadline)
    except BaseException as exc:
        if not (out / 'summary.json').exists():
            durable_save(out / 'summary.json', {'status': 'failed_preflight', 'calls': [],
                'not_attempted': [e['input_id'] for e in p['inputs']], 'error': repr(exc)})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for s, handler in old.items():
            signal.signal(s, handler)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('command', choices=['prepare', 'verify', 'run'])
    ap.add_argument('--output', type=Path); a = ap.parse_args()
    if a.command == 'prepare': prepare()
    elif a.command == 'verify': verify(); print('Frozen six-input diagnostic verified; no inference')
    elif a.output: run(a.output)
    else: ap.error('run requires output')
