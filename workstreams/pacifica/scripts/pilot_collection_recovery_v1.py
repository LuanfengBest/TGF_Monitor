"""One explicitly approved recovery of unattempted cases; no failed-case retry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import zipfile
import pilot_collection_v1 as original

ROOT = original.ROOT
actor = original.actor
PLAN = ROOT / 'configs/pilot_collection_recovery_v1.json'
PREFIX = 'pilot_collection_recovery_v1'


def artifact(suffix):
    return ROOT / 'results' / f'{PREFIX}_{suffix}.json'


def selected_attempts(parent, summary):
    planned = original.attempts_for(parent, 1)
    tried = [r['attempt_id'] for r in summary['attempts']]
    if tried != [a['attempt_id'] for a in planned[:10]]:
        raise ValueError('Unexpected parent attempted order')
    remaining = [a for a in planned if a['attempt_id'] not in tried]
    if len(remaining) != 20 or summary['not_attempted_ids'] != [a['attempt_id'] for a in remaining]:
        raise ValueError('Recovery must contain exactly the original unattempted twenty')
    return remaining


def verified_guard_exclusion(attempt_dir, plan):
    """Certify only the existing guard's exact before-submit failure, not API errors."""
    d = Path(attempt_dir)
    error = actor.read(d / 'rollout/error.json')['error']
    match = re.fullmatch(r"ValueError\('Context guard: (\d+)\+(\d+)\+(\d+)>(\d+); no messages discarded'\)", error)
    if not match:
        return False
    summary = actor.read(d / 'rollout/summary.json')
    if summary['status'] != 'error' or not summary['calls'] or summary['calls'][-1]['submitted'] is not False:
        return False
    if summary['view_integrity'] != 'complete_generated_messages':
        return False
    context = actor.read(d / 'rollout/raw/actor_context.json')
    first = actor.read(d / 'actor_calls/call_0001_request.json')
    schemas = first.get('tools', [])
    size = len(json.dumps({'messages': context, 'tools': schemas}, ensure_ascii=False).encode())
    overhead = 4096 + 128 * len(context) + 256 * len(schemas)
    expected = (size, overhead, plan['actor_output_tokens'], plan['actor_context'])
    if tuple(map(int, match.groups())) != expected or sum(expected[:3]) <= expected[3]:
        return False
    # The failed request must not have a durable submitted request or response.
    requests = list((d / 'actor_calls').glob('call_*_request.json'))
    responses = list((d / 'actor_calls').glob('call_*_response.json'))
    return len(requests) == len(responses) == summary['actor_calls'] == summary['calls'][-1]['client_count_before']


def verify():
    plan = actor.read(PLAN)
    parent = actor.read(original.PLAN)
    registry = original.verify(parent)
    for name, digest in plan['source_hashes'].items():
        if actor.sha(ROOT / name) != digest:
            raise ValueError('Frozen recovery source changed: ' + name)
    auth = actor.read(ROOT / plan['authorization'])
    if auth['user_answer'] != '同意这次有界恢复' or (auth['max_new_attempts'], auth['max_actor_calls'], auth['max_gpu_seconds'], auth['max_new_jobs']) != (20, 800, 2993, 1):
        raise ValueError('Explicit bounded recovery approval missing')
    if (plan['max_gpu_seconds'], plan['max_actor_calls'], plan['runner_deadline_seconds'], plan['automatic_retries']) != (2993, 800, 2840, 0):
        raise ValueError('Recovery budget changed')
    summary = actor.read(ROOT / plan['parent_run'] / 'summary.json')
    if summary['status'] != 'stopped_consecutive_failures':
        raise ValueError('Unexpected parent disposition')
    attempts = selected_attempts(parent, summary)
    if attempts != plan['attempts']:
        raise ValueError('Frozen recovery candidate order changed')
    for row in summary['attempts'][-2:]:
        if not verified_guard_exclusion(ROOT / plan['parent_run'] / row['attempt_id'], parent):
            raise ValueError('Parent errors are not proven before-submit guard failures')
    return plan, parent, registry


def submit():
    plan, _, _ = verify()
    if artifact('submission').exists() or artifact('reservation').exists():
        raise ValueError('Recovery already submitted or reserved')
    queue = subprocess.check_output(['squeue', '-u', 'hpcllm_rz377', '--noheader'], text=True, timeout=20)
    if queue.strip():
        raise ValueError('User queue must be empty')
    original.create(artifact('submission'), {'status': 'submitting', 'plan_sha256': actor.sha(PLAN), 'at': original.now()})
    result = subprocess.run(['sbatch', '--parsable', 'scripts/pilot_collection_recovery_v1.sbatch'], cwd=ROOT, capture_output=True, text=True, timeout=30)
    receipt = {'status': 'submitted' if result.returncode == 0 else 'submission_failed',
               'submitted_at': original.now(), 'plan_sha256': actor.sha(PLAN), 'queue_before': queue,
               'stdout': result.stdout, 'stderr': result.stderr, 'returncode': result.returncode}
    if result.returncode == 0:
        job = result.stdout.strip().split(';')[0]
        if not job.isdigit():
            raise ValueError('Ambiguous submission; check accounting, never resubmit')
        receipt['job_id'] = job
    artifact('submission').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


def run(output):
    plan, parent, registry = verify()
    submission = actor.read(artifact('submission'))
    if submission.get('job_id') != os.environ.get('SLURM_JOB_ID') or submission['plan_sha256'] != actor.sha(PLAN):
        raise ValueError('Job is not bound to unique approved recovery')
    original.create(artifact('reservation'), {'job_id': os.environ['SLURM_JOB_ID'], 'output': str(output),
                    'plan_sha256': actor.sha(PLAN), 'at': original.now()})
    output.mkdir(parents=True, exist_ok=False)
    actor.save(output / 'plan.json', {**parent, 'attempts': plan['attempts'], 'recovery_plan_sha256': actor.sha(PLAN)})
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('Actor deadline')))
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(143)))
    started = time.monotonic(); deadline = started + plan['runner_deadline_seconds']
    client = actor.DeadlineOllama(output / 'metadata_calls', deadline, 30)
    rows = []; status = 'preflight'
    def checkpoint():
        actor.save(output / 'summary.json', {'status': status, 'batch': 1, 'recovery': True,
                   'job_id': os.environ['SLURM_JOB_ID'], 'parent_job': '29672744', 'attempts': rows,
                   'planned_attempt_ids': [a['attempt_id'] for a in plan['attempts']],
                   'not_attempted_ids': [a['attempt_id'] for a in plan['attempts'] if a['attempt_id'] not in {r['attempt_id'] for r in rows}],
                   'calls_submitted': sum(r.get('actor_calls', 0) for r in rows),
                   'elapsed_seconds': time.monotonic() - started, 'monitor_calls': 0, 'training_runs': 0})
    checkpoint()
    try:
        for name, digest in parent['backend_installation_hashes'].items():
            if actor.sha(name) != digest: raise ValueError('Backend changed')
        meta = client.metadata(parent['actor']); actor.save(output / 'metadata.json', meta)
        models = [m for m in meta['tags']['models'] if m['name'] == parent['actor']]
        if len(models) != 1 or models[0]['digest'] != parent['actor_digest'] or meta['version']['version'] != parent['api_reported_version'] or actor.sha_text(meta['show']['template']) != parent['actor_template_sha256']:
            raise ValueError('Frozen actor identity changed')
        for attempt in plan['attempts']:
            if time.monotonic() + parent['actor_max_seconds'] + 20 > deadline:
                status = 'stage_time_limit'; break
            aid = attempt['attempt_id']; d = output / aid
            row = {'attempt_id': aid, 'status': 'started'}; rows.append(row)
            status = 'running'; checkpoint()
            ac = actor.DeadlineOllama(d / 'actor_calls', deadline, parent['per_call_seconds'])
            try:
                outcome = actor.rollout(attempt, parent, registry, d / 'rollout', ac)
            finally:
                row['actor_calls'] = ac.count; checkpoint()
            result = actor.read(d / 'rollout/summary.json')
            row.update(status=outcome, tool_events=result['tool_events'], output=str((d / 'rollout').relative_to(ROOT)))
            if ac.count > 40 or sum(r['actor_calls'] for r in rows) > 800:
                raise ValueError('Request budget exceeded')
            if outcome == 'error' and verified_guard_exclusion(d, parent):
                row.update(disposition='context_guard_excluded', eligible_for_P_N_target=False)
            elif outcome in {'error', 'time_limit', 'output_cap_or_incomplete'}:
                status = 'stopped_runtime_failure'; checkpoint(); break
            else:
                row['disposition'] = 'awaiting_full_AI_reference_review'
            checkpoint()
        else:
            status = 'completed_with_guard_exclusions' if any(r.get('disposition') == 'context_guard_excluded' for r in rows) else 'completed'
    except BaseException as exc:
        status = 'failed'; actor.save(output / 'error.json', {'error': repr(exc)}); raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); checkpoint()
        try:
            client.deadline = min(deadline, time.monotonic() + 15); client.max_http_seconds = 15
            client.unload(parent['actor'])
        except Exception as exc: actor.save(output / 'unload_error.json', {'error': repr(exc)})


def archive():
    job = actor.read(artifact('submission'))['job_id']
    target = ROOT / 'results' / f'{PREFIX}_{job}_archive.zip'
    if target.exists() or artifact('archive_receipt').exists(): raise ValueError('Archive already attempted')
    sacct = subprocess.check_output(['sacct', '-j', job, '--noheader', '--parsable2', '--format=JobID,State,ExitCode,Start,End,ElapsedRaw,AllocTRES'], text=True, timeout=20)
    row = next(x.split('|') for x in sacct.splitlines() if x.startswith(job + '|'))
    if row[1].split()[0] not in {'COMPLETED', 'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'CANCELLED'}: raise ValueError('Not terminal')
    queue = subprocess.check_output(['squeue', '-u', 'hpcllm_rz377', '--noheader'], text=True, timeout=20)
    if job in queue: raise ValueError('Job still active')
    original.create(artifact('closeout'), {'at': original.now(), 'job_id': job, 'sacct': sacct, 'queue': queue})
    paths = [p for p in (ROOT / 'results' / f'{PREFIX}_{job}').rglob('*') if p.is_file()]
    paths += [artifact(k) for k in ['submission', 'reservation', 'closeout']]
    paths += [ROOT / 'logs' / f'{PREFIX}-{job}.log']
    if any(p.is_symlink() for p in paths): raise ValueError('Symlink in archive')
    manifest = {str(p.relative_to(ROOT)): actor.sha(p) for p in sorted(set(paths)) if p.exists()}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name in manifest: z.write(ROOT / name, name)
        z.writestr('MANIFEST.json', json.dumps(manifest, indent=2))
    receipt = {'archive': str(target.relative_to(ROOT)), 'sha256': actor.sha(target), 'files': len(manifest),
               'bytes': target.stat().st_size, 'job_id': job, 'sacct': sacct, 'queue': queue}
    original.create(artifact('archive_receipt'), receipt); print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=['verify', 'submit', 'run', 'archive'])
    p.add_argument('--output', type=Path); a = p.parse_args()
    if a.command == 'verify': verify(); print('Recovery verified; zero model calls')
    elif a.command == 'submit': submit()
    elif a.command == 'archive': archive()
    elif a.output is not None: run(a.output.resolve())
    else: p.error('run requires --output')
