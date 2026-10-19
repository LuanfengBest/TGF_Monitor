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
import prospective_actor_smalltasks_v1 as actor
PLAN = ROOT/'configs/pilot_smalltasks_v1.json'
PREFIX = 'pilot_smalltasks_v1'
BATCH = None


def artifact(suffix):
    return ROOT/'results'/f'{PREFIX}_{suffix}.json'


def verify():
    plan=actor.read(PLAN);parent=actor.read(original.PLAN);registry=original.verify(parent)
    for name,digest in plan['source_hashes'].items():
        if actor.sha(ROOT/name)!=digest:raise ValueError('Frozen small-task source changed: '+name)
    auth=actor.read(ROOT/plan['authorization'])
    if auth['user_message']!='好的，允许把原长任务拆成明确的小任务，保持环境和模型不变，先做30条、最多60 GPU分钟的验收。数据门槛通过再推进，没过就及时告诉我，有明确结果邮件汇报。':raise ValueError('Explicit 30-case approval missing')
    if (plan['max_gpu_seconds'],plan['max_actor_calls'],plan['runner_deadline_seconds'],plan['automatic_retries'],plan['max_new_jobs'],plan['max_attempts'],plan['monitor_calls'],plan['training_runs'],plan['max_no_tool_reminders'])!=(3600,1200,3450,0,1,30,0,0,5):raise ValueError('Budget or scope changed')
    if plan['parent_plan_sha256']!=actor.sha(original.PLAN):raise ValueError('Parent config changed')
    tasks=actor.read(ROOT/'data/pilot_smalltasks_v1/public_tasks.json')['instances']
    if len(tasks)!=6 or len(plan['attempts'])!=30:raise ValueError('All30 positions and six tasks required')
    for i,a in enumerate(plan['attempts']):
        t=tasks[i%6]
        expected={'attempt_id':f"smalltasks1_{i+1:03d}_{t['task_id']}_ordinary",'candidate_id':t['candidate_id'],'task_id':t['task_id'],'condition':'ordinary','seed':27001+i,'secondary_objective':actor.load_original(t['candidate_id']).secondary_objective}
        if a!=expected:raise ValueError('Sampling sequence changed')
    from pilot_smalltasks_adapter_v1 import load_small,require_small_ready
    for a in plan['attempts'][:6]:require_small_ready(load_small(a),registry)
    return plan,parent,registry


def preflight():
    target=artifact('preflight');original.create(target,{'status':'started','at':original.now()})
    start=time.monotonic();receipt={'status':'failed','plan_sha256':actor.sha(PLAN),'model_calls':0,'gpu_jobs':0,'checks':[]}
    try:
        verify()
        for test in ['test_pilot_smalltasks_v1.py','test_actor_reminder_v1.py','test_pilot_collection_recovery_v1.py','test_reminder_citation_compat.py']:
            cp=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',test,'-q'],cwd=ROOT,timeout=max(1,120-(time.monotonic()-start)),capture_output=True,text=True)
            receipt['checks'].append({'test':test,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr});cp.check_returncode()
        cp=subprocess.run(['bash','-n','scripts/pilot_smalltasks_v1.sbatch'],cwd=ROOT,timeout=10);cp.check_returncode()
        if time.monotonic()-start>120:raise ValueError('Preflight time cap exceeded')
        receipt['status']='passed'
    except BaseException as exc: receipt['error']=repr(exc);raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-start;target.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


def submit():
    verify()
    if any(p.exists() for p in [artifact('submission'),artifact('reservation')]):raise ValueError('Batch already submitted/reserved; never retry')
    pre=actor.read(artifact('preflight'))
    if pre.get('status')!='passed' or pre.get('plan_sha256')!=actor.sha(PLAN):raise ValueError('Preflight missing/stale')
    queue=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    if queue.strip():raise ValueError('Active user queue')
    intent={'status':'submission_started','at':original.now(),'plan_sha256':actor.sha(PLAN),'batch':'smalltasks1','queue_before':queue,'smalltasks_prefix':PREFIX}
    original.create(artifact('submission'),intent)
    receipt=dict(intent)
    try:
        cp=subprocess.run(['sbatch','--parsable','scripts/pilot_smalltasks_v1.sbatch'],cwd=ROOT,capture_output=True,text=True,timeout=30)
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
    actor.save(output / 'plan.json', {**parent, 'attempts': plan['attempts'], 'smalltasks_plan_sha256': actor.sha(PLAN), 'collector_version': 'focused_original_assets_v1'})
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('Actor deadline')))
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(143)))
    started = time.monotonic(); deadline = started + plan['runner_deadline_seconds']
    client = actor.DeadlineOllama(output / 'metadata_calls', deadline, 30)
    rows = []; status = 'preflight'
    def checkpoint():
        actor.save(output / 'summary.json', {'status': status, 'batch': 'smalltasks1', 'collector_version': 'focused_original_assets_v1',
                   'job_id': os.environ['SLURM_JOB_ID'], 'prior_jobs': ['29672744', '29691597', '29703222', '29720251'], 'attempts': rows,
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
    if a.command=='verify':verify();print('30-case focused-task sources verified; zero inference')
    elif a.command=='preflight':preflight()
    elif a.command=='submit':submit()
    elif a.command=='archive':archive()
    elif a.output is not None:run(a.output.resolve())
    else:p.error('run requires --output')
