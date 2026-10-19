"""One bounded next original batch, with preserved verified guard exclusions."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile
import pilot_collection_v1 as original
from pilot_collection_recovery_v1 import verified_guard_exclusion
ROOT = original.ROOT
actor = original.actor
PLAN = ROOT/'configs/pilot_collection_continuation_b02.json'
PREFIX = 'pilot_collection_continuation_b02'
BATCH = 2


def artifact(suffix):
    return ROOT/'results'/f'{PREFIX}_{suffix}.json'


def validate_prior(prior, parent):
    expected = [a['attempt_id'] for a in original.attempts_for(parent, 1)]
    if ([x['attempt_id'] for x in prior['rows']] != expected or
        prior['planned'] != 30 or prior['attempted'] != 30 or prior['not_attempted'] != 0 or
        prior['events_reviewed'] != 455 or prior['full_planned_available_review_complete'] is not True or
        prior['source_hashes_and_public_projection_and_state_chains_valid'] is not True or
        prior['runtime_guard_excluded'] != 4 or prior['eligible_non_error_attempts'] != 26 or
        prior['technical_batch_all_attempts_successful'] is not False or
        prior['ready_for_monitor_comparison'] is not False or prior['ready_for_training'] is not False or
        prior['human_gold'] is not False or prior['independent_review'] is not False):
        raise ValueError('Prior data audit incomplete, altered, or misrepresented')


def verify():
    plan=actor.read(PLAN);parent=actor.read(original.PLAN);registry=original.verify(parent)
    for name,digest in plan['source_hashes'].items():
        if actor.sha(ROOT/name)!=digest: raise ValueError('Continuation source changed: '+name)
    auth=actor.read(ROOT/plan['authorization'])
    if auth['user_answer']!='就是还没采集完数据是吧 能不能努力采集完': raise ValueError('Continuation approval missing')
    if (plan['max_gpu_seconds'],plan['max_actor_calls'],plan['runner_deadline_seconds'],plan['automatic_retries'],plan['max_new_jobs'],plan['batch'])!=(3600,1200,3450,0,1,2): raise ValueError('Budget changed')
    if plan['attempts']!=original.attempts_for(parent,2) or len(plan['attempts'])!=30: raise ValueError('Frozen next batch changed')
    validate_prior(actor.read(ROOT/plan['prior_audit']),parent)
    for path,digest in plan['prior_archives'].items():
        if actor.sha(ROOT/path)!=digest: raise ValueError('Prior original archive changed')
    return plan,parent,registry


def preflight():
    target=artifact('preflight');original.create(target,{'status':'started','at':original.now()})
    start=time.monotonic();receipt={'status':'failed','plan_sha256':actor.sha(PLAN),'model_calls':0,'gpu_jobs':0,'checks':[]}
    try:
        verify()
        for test in ['test_pilot_collection_continuation_b02.py','test_pilot_collection_recovery_v1.py']:
            cp=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',test,'-q'],cwd=ROOT,timeout=max(1,120-(time.monotonic()-start)),capture_output=True,text=True)
            receipt['checks'].append({'test':test,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr});cp.check_returncode()
        cp=subprocess.run(['bash','-n','scripts/pilot_collection_continuation_b02.sbatch'],cwd=ROOT,timeout=10);cp.check_returncode()
        if time.monotonic()-start>120:raise ValueError('Preflight time cap exceeded')
        receipt['status']='passed'
    except BaseException as exc: receipt['error']=repr(exc);raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-start;target.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


def submit():
    verify()
    if any(p.exists() for p in [artifact('submission'),artifact('reservation'),original.batch_path(2,'submission'),original.batch_path(2,'reservation')]):raise ValueError('Batch already submitted/reserved; never retry')
    pre=actor.read(artifact('preflight'))
    if pre.get('status')!='passed' or pre.get('plan_sha256')!=actor.sha(PLAN):raise ValueError('Preflight missing/stale')
    queue=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    if queue.strip():raise ValueError('Active user queue')
    intent={'status':'submission_started','at':original.now(),'plan_sha256':actor.sha(PLAN),'batch':2,'queue_before':queue,'continuation_prefix':PREFIX}
    # Shared original-batch lock also prevents the old submitter from running batch 2.
    original.create(original.batch_path(2,'reservation'),intent)
    original.create(artifact('submission'),intent)
    receipt=dict(intent)
    try:
        cp=subprocess.run(['sbatch','--parsable','scripts/pilot_collection_continuation_b02.sbatch'],cwd=ROOT,capture_output=True,text=True,timeout=30)
        receipt.update(returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr,status='submitted' if cp.returncode==0 else 'submission_failed')
        if cp.returncode==0:
            job=cp.stdout.strip().split(';')[0]
            if not job.isdigit():raise ValueError('Ambiguous submission; accounting first')
            receipt['job_id']=job
        cp.check_returncode()
    except BaseException as exc:
        receipt['error']=repr(exc)
        if 'returncode' not in receipt or (receipt['returncode']==0 and 'job_id' not in receipt):receipt['status']='unknown_outcome_do_not_retry'
        raise
    finally:
        artifact('submission').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


def run(output):
    plan, parent, registry = verify()
    submission = actor.read(artifact('submission'))
    if submission.get('job_id') != os.environ.get('SLURM_JOB_ID') or submission['plan_sha256'] != actor.sha(PLAN):
        raise ValueError('Job is not bound to unique approved continuation')
    original.create(artifact('reservation'), {'job_id': os.environ['SLURM_JOB_ID'], 'output': str(output),
                    'plan_sha256': actor.sha(PLAN), 'at': original.now()})
    output.mkdir(parents=True, exist_ok=False)
    actor.save(output / 'plan.json', {**parent, 'attempts': plan['attempts'], 'continuation_plan_sha256': actor.sha(PLAN)})
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('Actor deadline')))
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(143)))
    started = time.monotonic(); deadline = started + plan['runner_deadline_seconds']
    client = actor.DeadlineOllama(output / 'metadata_calls', deadline, 30)
    rows = []; status = 'preflight'
    def checkpoint():
        actor.save(output / 'summary.json', {'status': status, 'batch': 2, 'continuation': True,
                   'job_id': os.environ['SLURM_JOB_ID'], 'prior_jobs': ['29672744', '29691597'], 'attempts': rows,
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
            if ac.count > 40 or sum(r['actor_calls'] for r in rows) > 1200:
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
    p=argparse.ArgumentParser();p.add_argument('command',choices=['verify','preflight','submit','run','archive']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='verify':verify();print('Continuation batch 2 sources verified; zero inference')
    elif a.command=='preflight':preflight()
    elif a.command=='submit':submit()
    elif a.command=='archive':archive()
    elif a.output is not None:run(a.output.resolve())
    else:p.error('run requires --output')
