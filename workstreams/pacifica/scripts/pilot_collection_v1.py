"""Bounded original-task collection. Reuses v6 rollout unchanged; never scores monitors."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile
from zoneinfo import ZoneInfo
import prospective_actor_v6 as actor

ROOT = actor.ROOT
PLAN = ROOT / 'configs/pilot_collection_v1.json'
PREFIX = 'pilot_collection_v1'
PROTOCOL = 'docs/pilot_collection_and_review_protocol_2026-10-15.md'


def now():
    return datetime.now(ZoneInfo('America/New_York')).isoformat()


def create(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def batch_path(batch, suffix):
    if batch not in range(1, 9):
        raise ValueError('Batch outside frozen campaign')
    return ROOT / 'results' / f'{PREFIX}_b{batch:02d}_{suffix}.json'


def attempts_for(plan, batch):
    if batch not in range(1, 9):
        raise ValueError('Invalid batch')
    return [a for a in plan['attempts'] if a['batch'] == batch]


def verify(plan):
    if (plan['max_new_actor_attempts'], plan['max_actor_calls'], plan['gpu_seconds'],
        plan['gpu_jobs'], plan['gpu_seconds_per_batch']) != (240, 9600, 28800, 8, 3600):
        raise ValueError('Campaign budget changed')
    old = actor.read(ROOT / 'configs/prospective_actor_v6.json')
    for key in ['actor_system_sha256', 'actor_system', 'actor_max_seconds', 'per_call_seconds',
                'actor_max_turns', 'max_tool_events', 'actor_context', 'actor_output_tokens',
                'actor_think', 'temperature', 'actor', 'actor_digest', 'actor_template_sha256',
                'api_reported_version', 'backend_installation_hashes', 'registry']:
        if plan[key] != old[key]:
            raise ValueError('Original actor configuration changed: ' + key)
    if plan['monitor_calls'] != 0 or plan['training_runs'] != 0 or plan['automatic_retries'] != 0:
        raise ValueError('Collection-only scope')
    if plan['runner_deadline_seconds'] != 3450 or plan['user_authorization_sha256'] != actor.sha(ROOT / 'results/pilot_collection_authorization_20261015.json'):
        raise ValueError('Runtime or authorization changed')
    for name, digest in plan['source_hashes'].items():
        if actor.sha(ROOT / name) != digest:
            raise ValueError('Frozen source changed: ' + name)
    attempts = plan['attempts']
    if len(attempts) != 240 or len({a['attempt_id'] for a in attempts}) != 240:
        raise ValueError('Invalid attempt denominator')
    if [a['seed'] for a in attempts] != list(range(16001, 16241)):
        raise ValueError('Seed sequence changed')
    for b in range(1, 9):
        if len(attempts_for(plan, b)) != 30:
            raise ValueError('Batch size changed')
    originals = {n: actor.load_original(n) for n in plan['registry']['candidates']}
    for i, a in enumerate(attempts):
        family = ('bank_transfer_2', 'american_airlines_2')[i % 2]
        condition = 'ordinary' if (i // 2) % 2 == 0 else 'injected'
        if (a['candidate_id'], a['condition'], a['batch']) != (family, condition, i // 30 + 1):
            raise ValueError('Fixed sampling order changed')
        if a['secondary_objective'] != originals[family].secondary_objective:
            raise ValueError('Original hidden objective changed')
    for name in plan['registry']['candidates']:
        actor.require_original_ready(originals[name], plan['registry']['candidates'])
    return plan['registry']


def freeze():
    if PLAN.exists():
        raise ValueError('Plan already frozen')
    old = actor.read(ROOT / 'configs/prospective_actor_v6.json')
    plan = deepcopy(old)
    plan.update(protocol=PREFIX, frozen_at=now(), max_new_actor_attempts=240,
                max_actor_calls=9600, gpu_jobs=8, gpu_seconds=28800,
                gpu_seconds_per_batch=3600, runner_deadline_seconds=3450,
                target_per_environment={'positive': 30, 'negative': 30,
                    'hard_negative_minimum': 15, 'publicly_provable_positive_minimum': 15},
                reviewer_type='AI', human_gold=False, independent_review=False,
                collection_only=True, attempts=[],
                user_authorization_sha256=actor.sha(ROOT / 'results/pilot_collection_authorization_20261015.json'))
    originals = {n: actor.load_original(n) for n in old['registry']['candidates']}
    for i in range(240):
        name = ('bank_transfer_2', 'american_airlines_2')[i % 2]
        condition = 'ordinary' if (i // 2) % 2 == 0 else 'injected'
        plan['attempts'].append({'attempt_id': f'pilot1_{i+1:03d}_{name}_{condition}',
            'candidate_id': name, 'condition': condition, 'seed': 16001+i, 'batch': i//30+1,
            'secondary_objective': originals[name].secondary_objective})
    extra = [PROTOCOL, 'results/pilot_collection_authorization_20261015.json',
             'scripts/pilot_collection_v1.py', 'scripts/pilot_review_packet_v1.py',
             'scripts/pilot_collection_v1.sbatch', 'tests/test_pilot_collection_v1.py',
             'docs/prospective_reference_contract_2026-10-14.md']
    plan['source_hashes'].update({n: actor.sha(ROOT/n) for n in extra})
    verify(plan)
    create(PLAN, plan)
    print(json.dumps({'plan_sha256': actor.sha(PLAN), 'sources': len(plan['source_hashes']),
                      'attempts': 240, 'target': 120, 'model_calls': 0}), flush=True)


def preflight():
    target = ROOT/'results/pilot_collection_v1_preflight.json'
    create(target, {'status': 'started', 'at': now()})
    start = time.monotonic()
    receipt = {'status': 'failed', 'plan_sha256': actor.sha(PLAN), 'model_calls': 0,
               'gpu_jobs': 0, 'new_installations': 0, 'checks': []}
    try:
        verify(actor.read(PLAN))
        for test in ['test_pilot_collection_v1.py', 'test_prospective_actor_v6.py']:
            cp = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', test, '-q'], cwd=ROOT, timeout=120)
            receipt['checks'].append({'test': test, 'returncode': cp.returncode})
            cp.check_returncode()
        receipt['status'] = 'passed'
    except BaseException as exc:
        receipt['error'] = repr(exc)
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic()-start
        target.write_text(json.dumps(receipt, indent=2)+'\n')
        print(json.dumps(receipt), flush=True)


def submit(batch):
    plan = actor.read(PLAN); verify(plan)
    pre = actor.read(ROOT/'results/pilot_collection_v1_preflight.json')
    if pre['status'] != 'passed' or pre['plan_sha256'] != actor.sha(PLAN):
        raise ValueError('Remote qualification missing/stale')
    if batch_path(batch, 'reservation').exists():
        raise ValueError('Existing execution reservation')
    if batch > 1:
        previous = actor.read(batch_path(batch-1, 'review_acceptance'))
        if (previous.get('plan_sha256') != actor.sha(PLAN) or
            previous.get('full_review_complete') is not True or
            previous.get('technical_batch_complete') is not True or
            previous.get('target_reached') is not False):
            raise ValueError('Previous full review/generation incomplete or target already met')
        for n, h in previous['source_hashes'].items():
            if actor.sha(ROOT/n) != h:
                raise ValueError('Previous review source changed')
    queue = subprocess.check_output(['squeue', '-u', 'hpcllm_rz377', '--noheader'], text=True, timeout=20)
    if queue.strip():
        raise ValueError('Active user queue must be inspected before submission')
    target = batch_path(batch, 'submission')
    receipt = {'status': 'submission_started', 'submitted_at': now(), 'batch': batch,
               'plan_sha256': actor.sha(PLAN), 'queue_before': queue,
               'gpu_seconds_limit': 3600, 'actor_calls_limit': 1200}
    create(target, receipt)
    try:
        cp = subprocess.run(['sbatch', '--parsable', 'scripts/pilot_collection_v1.sbatch', str(batch)],
                            cwd=ROOT, text=True, capture_output=True, timeout=30)
        receipt.update(returncode=cp.returncode, stdout=cp.stdout, stderr=cp.stderr,
                       status='submitted' if cp.returncode == 0 else 'failed')
        if cp.returncode == 0:
            job = cp.stdout.strip().split(';')[0]
            if not job.isdigit():
                raise ValueError('Ambiguous sbatch receipt; never retry')
            receipt['job_id'] = job
        cp.check_returncode()
    except BaseException as exc:
        receipt.update(error=repr(exc))
        if 'returncode' not in receipt or (receipt.get('returncode') == 0 and 'job_id' not in receipt):
            receipt['status'] = 'unknown_outcome_do_not_retry'
        raise
    finally:
        target.write_text(json.dumps(receipt, indent=2)+'\n'); print(json.dumps(receipt), flush=True)


def run(batch, output):
    plan = actor.read(PLAN); registry = verify(plan)
    submission = actor.read(batch_path(batch, 'submission'))
    if submission.get('job_id') != os.environ.get('SLURM_JOB_ID') or submission['plan_sha256'] != actor.sha(PLAN):
        raise ValueError('Job not bound to unique submission')
    create(batch_path(batch, 'reservation'), {'output': str(output), 'job_id': os.environ['SLURM_JOB_ID'],
           'batch': batch, 'plan_sha256': actor.sha(PLAN), 'started_at': now()})
    output.mkdir(parents=True, exist_ok=False); actor.save(output/'plan.json', plan)
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('Actor deadline')))
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(143)))
    started = time.monotonic(); deadline = started+plan['runner_deadline_seconds']
    client = actor.DeadlineOllama(output/'metadata_calls', deadline, 30)
    rows=[]; status='preflight'; planned=attempts_for(plan, batch)
    def checkpoint():
        actor.save(output/'summary.json', {'status':status, 'batch':batch,
            'job_id':os.environ['SLURM_JOB_ID'], 'attempts':rows,
            'planned_attempt_ids':[a['attempt_id'] for a in planned],
            'not_attempted_ids':[a['attempt_id'] for a in planned if a['attempt_id'] not in {r['attempt_id'] for r in rows}],
            'calls_submitted':sum(r.get('actor_calls',0) for r in rows),
            'elapsed_seconds':time.monotonic()-started, 'monitor_calls':0, 'training_runs':0})
    checkpoint()
    try:
        for path,h in plan['backend_installation_hashes'].items():
            if actor.sha(path)!=h: raise ValueError('Backend changed')
        meta=client.metadata(plan['actor']); actor.save(output/'metadata.json',meta)
        models=[m for m in meta['tags']['models'] if m['name']==plan['actor']]
        if len(models)!=1 or models[0]['digest']!=plan['actor_digest'] or meta['version']['version']!=plan['api_reported_version'] or actor.sha_text(meta['show']['template'])!=plan['actor_template_sha256']:
            raise ValueError('Frozen actor identity changed')
        failures=0
        for attempt in planned:
            if time.monotonic()+plan['actor_max_seconds']+20 > deadline:
                status='stage_time_limit'; break
            aid=attempt['attempt_id']; row={'attempt_id':aid,'status':'started'}; rows.append(row)
            status='running'; checkpoint()
            ac=actor.DeadlineOllama(output/aid/'actor_calls', deadline, plan['per_call_seconds'])
            try:
                outcome=actor.rollout(attempt, plan, registry, output/aid/'rollout', ac)
            finally:
                row['actor_calls']=ac.count; checkpoint()
            summ=actor.read(output/aid/'rollout/summary.json')
            row.update(status=outcome, tool_events=summ['tool_events'],
                       output=str((output/aid/'rollout').relative_to(ROOT)))
            if ac.count>40 or sum(r.get('actor_calls',0) for r in rows)>1200:
                raise ValueError('Frozen request cap exceeded')
            failures=failures+1 if outcome in {'error','time_limit','output_cap_or_incomplete'} else 0
            checkpoint()
            if failures>=2: status='stopped_consecutive_failures'; break
        else: status='completed'
    except BaseException as exc:
        status='failed'; actor.save(output/'error.json',{'error':repr(exc)}); raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0); checkpoint()
        try:
            client.deadline=min(deadline,time.monotonic()+15); client.max_http_seconds=15
            client.unload(plan['actor'])
        except Exception as exc: actor.save(output/'unload_error.json',{'error':repr(exc)})


def archive(batch):
    submission=actor.read(batch_path(batch,'submission')); job=submission['job_id']
    run_dir=ROOT/'results'/f'{PREFIX}_b{batch:02d}_{job}'
    target=ROOT/'results'/f'{PREFIX}_b{batch:02d}_{job}_archive.zip'
    receipt_path=batch_path(batch,'archive_receipt')
    if target.exists() or receipt_path.exists(): raise ValueError('Archive already attempted')
    sacct=subprocess.check_output(['sacct','-j',job,'--noheader','--parsable2','--format=JobID,State,ExitCode,Start,End,ElapsedRaw,AllocTRES'],text=True,timeout=20)
    row=next(x.split('|') for x in sacct.splitlines() if x.startswith(job+'|'))
    if row[1].split()[0] not in {'COMPLETED','FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED'}:
        raise ValueError('Job not terminal')
    queue=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    if job in queue: raise ValueError('Job still active')
    closeout=batch_path(batch,'closeout')
    create(closeout,{'observed_at':now(),'job_id':job,'sacct':sacct,'queue':queue})
    paths=[p for p in run_dir.rglob('*') if p.is_file()]
    paths += [closeout,batch_path(batch,'submission'),batch_path(batch,'reservation'),ROOT/'results/pilot_collection_v1_preflight.json',ROOT/'logs'/f'pilot_collection_v1-{job}.log']
    paths=[p for p in paths if p.exists()]
    if any(p.is_symlink() for p in paths): raise ValueError('Symlink in archive')
    manifest={str(p.relative_to(ROOT)):actor.sha(p) for p in sorted(set(paths))}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in manifest: z.write(ROOT/name,name)
        z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
    receipt={'archive':str(target.relative_to(ROOT)),'sha256':actor.sha(target),'files':len(manifest),
             'bytes':target.stat().st_size,'job_id':job,'batch':batch,'sacct':sacct,'queue':queue}
    create(receipt_path,receipt); print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['freeze','verify','preflight','submit','run','archive'])
    parser.add_argument('--batch',type=int); parser.add_argument('--output',type=Path); a=parser.parse_args()
    if a.command=='freeze': freeze()
    elif a.command=='verify': verify(actor.read(PLAN)); print('Frozen collection sources/assets verified; zero inference')
    elif a.command=='preflight': preflight()
    elif a.command=='submit': submit(a.batch)
    elif a.command=='archive': archive(a.batch)
    elif a.output is not None: run(a.batch,a.output.resolve())
    else: parser.error('run requires --output')
