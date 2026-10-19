"""One bounded CPU install into a new overlay; no model or original-venv writes."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'runtime/prospective_actor_v2_deps'
RECEIPT=ROOT/'results/prospective_runtime_v2_receipt.json'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    started=time.monotonic()
    plan=ROOT/'configs/prospective_actor_v2.json'
    spec=json.loads((ROOT/'configs/prospective_actor_v2_dependencies.json').read_text())
    if sys.version_info[:2]!=(3,12):raise RuntimeError('CPython 3.12 required')
    with (ROOT/'results/prospective_runtime_v2.reservation.json').open('x') as f:
        json.dump({'job_id':os.environ.get('SLURM_JOB_ID'),'plan_sha256':sha(plan)},f)
    TARGET.mkdir(parents=True,exist_ok=False)
    report={'status':'started','job_id':os.environ.get('SLURM_JOB_ID'),'plan_sha256':sha(plan),
        'target':str(TARGET),'model_calls':0,'gpu_jobs':0,'training_runs':0,'checks':[]}
    def save():
        report['elapsed_seconds']=time.monotonic()-started
        RECEIPT.write_text(json.dumps(report,indent=2)+'\n')
    save()
    env=dict(os.environ,PYTHONPATH=str(TARGET),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PIP_DISABLE_PIP_VERSION_CHECK='1')
    def command(args):
        result=subprocess.run(args,cwd=ROOT,env=env,timeout=max(1,520-(time.monotonic()-started)))
        report['checks'].append({'command':args,'returncode':result.returncode});save()
        result.check_returncode()
    try:
        if len(spec['packages'])!=8 or sum(p['bytes'] for p in spec['packages'])>100_000_000:
            raise ValueError('Dependency budget changed')
        command([sys.executable,'-m','pip','install','--target',str(TARGET),'--no-deps','--require-hashes',
                 '--only-binary=:all:','--no-cache-dir','--retries','0','--timeout','45',
                 '--report',str(ROOT/'results/prospective_runtime_v2_pip_report.json'),
                 '-r','configs/prospective_actor_v2_requirements.lock'])
        versions={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions(path=[str(TARGET)])}
        expected={p['name']:p['version'] for p in spec['packages']}
        if versions!=expected:raise ValueError('Installed dependency set/version mismatch: '+str(versions))
        report['versions']=versions
        report['installed_bytes']=sum(p.stat().st_size for p in TARGET.rglob('*') if p.is_file())
        if report['installed_bytes']>1_000_000_000:raise ValueError('Installed size limit exceeded')
        command([sys.executable,'-c','import pandas,numpy,openpyxl,dateutil,pytz,tzdata,et_xmlfile,six; print("all overlay imports passed")'])
        command([sys.executable,'scripts/prospective_actor_v2.py','verify'])
        command([sys.executable,'-m','unittest','discover','-s','tests','-p','test_prospective_actor_v2.py','-q'])
        command([sys.executable,'-m','unittest','discover','-s','tests','-p','test_tgf_evidence_eval_v1.py','-q'])
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['error']=repr(exc);raise
    finally:save();print(json.dumps(report),flush=True)

if __name__=='__main__':main()
