"""Single-use CPU preflight and one authorized second GPU allocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

NAME='authorization_timing_jev_v02_recovery01_20261112'
BASE=Path('/nfs/roberts/project/cpsc4880/cpsc4880_rz377')
ROOT=BASE/NAME
REL=Path('project/authorization_timing_jev_2026-11-12/recovery_01')
BUNDLE=ROOT/REL
ASSETS=BASE/'authorization_cpsc4880_20261105_879a8821d635/runtime_assets'
DEPS=BASE/'new_data_20261105_v1/python_dependencies'


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def call(argv,timeout=30):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
    result={'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    if p.returncode:raise RuntimeError(json.dumps(result))
    return result

def account(job):
    result=call(['sacct','-j',job,'--parsable2','--noheader','--format=JobID,State,ExitCode,ElapsedRaw,AllocTRES'])
    line=next(x for x in result['stdout'].splitlines() if x.startswith(job+'|'))
    fields=line.split('|')
    return {'job_id':job,'state':fields[1],'exit_code':fields[2],'elapsed_seconds':int(fields[3]),'tres':fields[4],'raw':result}

def idle():
    q=call(['squeue','-h','-u','cpsc4880_rz377'])
    if q['stdout'].strip():raise RuntimeError('Existing queued/running job; no additional submission')
    return q

def validate_old():
    result=account('33137525')
    if result['state']!='FAILED' or result['elapsed_seconds']!=1237 or 'gres/gpu:h200=1' not in result['tres']:
        raise ValueError('Original GPU accounting changed')
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','cpu','gpu','status','export'])
    ap.add_argument('--archive-sha256');ap.add_argument('--seal');args=ap.parse_args()
    if os.environ.get('USER')!='cpsc4880_rz377':raise PermissionError('Wrong account')
    if args.action=='prepare':
        archive=Path.home()/(NAME+'.zip')
        if not args.archive_sha256 or sha(archive)!=args.archive_sha256:raise ValueError('Transfer hash differs')
        ROOT.mkdir(exist_ok=False)
        with zipfile.ZipFile(archive) as z:
            if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate archive entry')
            for item in z.infolist():
                path=Path(item.filename)
                if path.is_absolute() or '..' in path.parts or path.parts[0]!=NAME:raise ValueError('Unsafe archive')
                target=ROOT.joinpath(*path.parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as f:f.write(z.read(item))
    sys.path.insert(0,str(ROOT))
    from authorization_timing_recovery_v1.common import verify_inputs,check_fresh
    a,cfg,rows,seal=verify_inputs()
    if args.action=='prepare':
        if seal!=args.seal:raise ValueError('Manifest does not match local freeze')
        queue=idle(); old=validate_old();(ROOT/'logs').mkdir()
        code="import json; from pathlib import Path; from prospective_monitoring.native_backend import runtime_check,snapshot_check; c=json.loads(Path('project/authorization_timing_jev_2026-11-12/run_01/config.json').read_text()); print(json.dumps({'runtime':runtime_check(c['qwen']),'snapshot':str(snapshot_check(c['qwen']['snapshot'],'monitor'))}))"
        runtime=call(['apptainer','exec','--cleanenv','--bind',f'{ROOT}:{ROOT}','--bind',f'{ASSETS}:{ASSETS}:ro','--bind',f'{DEPS}:{DEPS}:ro','--pwd',str(ROOT),'--env',f'PYTHONPATH={ROOT}:{DEPS}','--env','HF_HUB_OFFLINE=1','--env','TRANSFORMERS_OFFLINE=1',str(ASSETS/'vllm_0.13.0.sif'),'/usr/bin/python3','-c',code],120)
        # CPU-only import check: hook installs, no CUDA/model initialization.
        guard_code="from vllm.compilation.backends import CompilerManager; assert CompilerManager._timing_warm_only; print('warm_cache_guard_import_passed')"
        guard=call(['apptainer','exec','--cleanenv','--bind',f'{ROOT}:{ROOT}','--pwd',str(ROOT),'--env',f'PYTHONPATH={ROOT}/authorization_timing_recovery_v1/guard_bootstrap:{ROOT}:{DEPS}','--env','TIMING_REQUIRE_WARM_CACHE=1',str(ASSETS/'vllm_0.13.0.sif'),'/usr/bin/python3','-c',guard_code],120)
        admission=call(['sbatch','--test-only','--chdir='+str(ROOT),str(ROOT/'authorization_timing_recovery_v1/cpu.sbatch')])
        receipt={'manifest_sha256':seal,'archive_sha256':args.archive_sha256,'queue':queue,'prior_gpu':old,'runtime':runtime,'guard_import':guard,'cpu_admission':admission}
        save(BUNDLE/'cluster/admission.json',receipt);print(json.dumps(receipt))
    elif args.action in {'cpu','gpu'}:
        admission=read(BUNDLE/'cluster/admission.json')
        if admission['manifest_sha256']!=seal:raise ValueError('Wrong admission')
        idle();validate_old()
        kind=args.action
        claim={'manifest_sha256':seal}
        if kind=='gpu':
            cpureceipt=read(BUNDLE/'cluster/cpu_submission.json');ca=account(cpureceipt['job_id'])
            if ca['state']!='COMPLETED' or ca['exit_code']!='0:0' or ca['elapsed_seconds']>840 or 'gres/gpu' in ca['tres']:
                raise ValueError('CPU preflight allocation did not complete within limits')
            preflight=read(BUNDLE/'cluster/cpu_preflight.json');check_fresh(preflight)
            if not preflight['passed'] or preflight['manifest_sha256']!=seal or preflight['job_id']!=ca['job_id']:
                raise ValueError('Missing/foreign CPU preflight')
            claim['cpu_preflight_sha256']=sha(BUNDLE/'cluster/cpu_preflight.json')
            claim['cpu_accounting']=ca
            claim['gpu_admission']=call(['sbatch','--test-only','--chdir='+str(ROOT),str(ROOT/'authorization_timing_recovery_v1/run.sbatch')])
        save(BUNDLE/'cluster'/f'{kind}_submission_claim.json',claim)
        script='cpu.sbatch' if kind=='cpu' else 'run.sbatch'
        result=call(['sbatch','--parsable','--chdir='+str(ROOT),str(ROOT/'authorization_timing_recovery_v1'/script)])
        job=result['stdout'].strip().split(';')[0]
        if not job.isdigit():raise ValueError('Uncertain submission; no retry')
        receipt={'manifest_sha256':seal,'job_id':job,'submission':result,'gpu_count':0 if kind=='cpu' else 1,'wall_seconds':840 if kind=='cpu' else 540}
        save(BUNDLE/'cluster'/f'{kind}_submission.json',receipt);print(json.dumps(receipt))
    else:
        status={'queue':call(['squeue','-h','-u','cpsc4880_rz377']),'prior_gpu':validate_old()}
        for kind in ['cpu','gpu']:
            path=BUNDLE/'cluster'/f'{kind}_submission.json'
            if path.exists():status[kind]=account(read(path)['job_id'])
        status.update(qwen_results=len(list((BUNDLE/'results').glob('qwen.*/result.json'))),qwen_ready=(BUNDLE/'results/qwen_ready.json').exists(),qwen_finished=(BUNDLE/'results/qwen_all_finished.json').exists(),stop=read(BUNDLE/'results/STOP.json') if (BUNDLE/'results/STOP.json').exists() else None,cpu_preflight=(BUNDLE/'cluster/cpu_preflight.json').exists())
        print(json.dumps(status))
        if args.action=='status':
            logs=sorted((ROOT/'logs').glob('*.log'),key=lambda p:p.stat().st_mtime)
            if logs:print(json.dumps({'log_tail':logs[-1].read_text(errors='replace')[-1600:]}))
        else:
            if status['queue']['stdout'].strip():raise RuntimeError('Run still active')
            save(BUNDLE/'cluster/accounting_final.json',status)
            files=[p for d in (BUNDLE/'cluster',BUNDLE/'results',ROOT/'logs') for p in d.rglob('*') if p.is_file()]
            save(BUNDLE/'cluster/export_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in files})
            files.append(BUNDLE/'cluster/export_hashes.json')
            output=Path.home()/(NAME+'_results.zip')
            with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as z:
                for p in files:z.write(p,str(p.relative_to(ROOT)))
            print(json.dumps({'archive':str(output),'sha256':sha(output),'files':len(files)}))

if __name__=='__main__':main()
