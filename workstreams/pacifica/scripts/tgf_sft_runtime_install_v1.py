"""One CPU-only, isolated, hash-locked official-wheel runtime install. No model weights."""
import hashlib, importlib.metadata, json, os, re, shutil, signal, subprocess, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path('/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf')
BUNDLE = Path(__file__).resolve().parent
OUT = ROOT / 'runtime/tgf_sft_pilot_v1'
PINS = ['torch==2.8.0','transformers==4.57.1','peft==0.17.1','bitsandbytes==0.48.1',
        'accelerate==1.10.1','huggingface-hub==0.35.3','tokenizers==0.22.2',
        'safetensors==0.6.2','Jinja2==3.1.6']
LIMIT = 20 * 1024**3  # Includes wheel cache, temp and installed env, within total 90 GiB.

def write_new(path, obj):
    with path.open('x') as f: json.dump(obj,f,indent=2);f.write('\n')

def lock_lines(report):
    rows=[]; names=set()
    for item in report['install']:
        name=item['metadata']['name']; version=item['metadata']['version']
        url=item['download_info']['url']; digest=item['download_info']['archive_info']['hashes']['sha256']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or not re.fullmatch(r'[A-Za-z0-9_.+!-]+',version):
            raise ValueError('Invalid distribution identity')
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname!='files.pythonhosted.org' or not parsed.path.endswith('.whl'):
            raise ValueError('Nonofficial or nonwheel source')
        if not re.fullmatch(r'[a-f0-9]{64}',digest) or name.lower() in names: raise ValueError('Invalid lock hash/duplicate')
        names.add(name.lower()); rows.append(f'{name} @ {url} --hash=sha256:{digest}')
    if not rows: raise ValueError('Empty runtime lock')
    return sorted(rows)

def usage():
    return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file() and not p.is_symlink())

def main():
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_JOB_GPUS'):
        raise RuntimeError('CPU Slurm job required')
    manifest=json.loads((BUNDLE/'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        if Path(name).name!=name or hashlib.sha256((BUNDLE/name).read_bytes()).hexdigest()!=digest: raise ValueError('Source hash mismatch')
    if shutil.disk_usage(ROOT).free < 100*1024**3: raise RuntimeError('Less than 100 GiB available before install')
    OUT.mkdir(parents=True, exist_ok=False) # Reservation; no repeated install or old environment mutation.
    report={'started_at':datetime.now().astimezone().isoformat(),'job_id':os.environ['SLURM_JOB_ID'],
            'pins':PINS,'commands':[],'model_calls':0,'gpu_allocated':False,'training_runs':0,
            'weights_downloaded':False,'gradient_verified':False,'status':'running'}
    write_new(OUT/'reservation.json',report)
    env=os.environ.copy(); env.update(PIP_NO_INPUT='1',PIP_DISABLE_PIP_VERSION_CHECK='1',
                                     TMPDIR=str(OUT/'tmp'),PYTHONNOUSERSITE='1')
    (OUT/'tmp').mkdir(); started=time.monotonic(); active=None
    def interrupted(signum, frame): raise RuntimeError(f'Interrupted signal {signum}')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    def run(argv, timeout):
        nonlocal active
        n=len(report['commands']); row={'argv':argv,'log':f'command_{n}.log'};report['commands'].append(row)
        with (OUT/row['log']).open('xb') as log:
            active=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            t=time.monotonic()
            while active.poll() is None:
                if time.monotonic()-t>timeout or time.monotonic()-started>1650: raise RuntimeError('Install time budget reached')
                if usage()>LIMIT or shutil.disk_usage(ROOT).free<10*1024**3: raise RuntimeError('Install disk budget reached')
                time.sleep(3)
            row['returncode']=active.returncode;row['seconds']=time.monotonic()-t;active=None
            if row['returncode']: raise RuntimeError('Subprocess failed: '+row['log'])
    try:
        run([sys.executable,'-m','venv',str(OUT/'venv')],60)
        py=str(OUT/'venv/bin/python');pip=[py,'-m','pip','--isolated','--disable-pip-version-check']
        run(pip+['install','--dry-run','--ignore-installed','--no-cache-dir','--only-binary=:all:',
                 '--index-url','https://pypi.org/simple','--report',str(OUT/'resolution.json'),*PINS],600)
        resolved=json.loads((OUT/'resolution.json').read_text()); lines=lock_lines(resolved)
        with (OUT/'requirements.lock').open('x') as f:f.write('\n'.join(lines)+'\n')
        report['lock_sha256']=hashlib.sha256((OUT/'requirements.lock').read_bytes()).hexdigest()
        run(pip+['install','--no-cache-dir','--only-binary=:all:','--require-hashes','--no-deps',
                 '-r',str(OUT/'requirements.lock')],750)
        run(pip+['check'],60)
        code="import torch,transformers,peft,bitsandbytes,accelerate,tokenizers,safetensors,jinja2,json,importlib.metadata as m; from transformers import Qwen3Config; from peft import LoraConfig; print(json.dumps({'versions':{x:m.version(x) for x in ['torch','transformers','peft','bitsandbytes','accelerate','tokenizers','safetensors','Jinja2','huggingface-hub']},'cuda_available':torch.cuda.is_available(),'qwen3_config':Qwen3Config().model_type,'lora_target':LoraConfig(r=8,lora_alpha=16,target_modules='all-linear').target_modules})); assert not torch.cuda.is_available()"
        run([py,'-c',code],120)
        report['status']='cpu_imports_passed_gpu_and_weights_pending'
    except BaseException as e:
        report['status']='failed';report['error']=type(e).__name__+': '+str(e)
        raise
    finally:
        if active and active.poll() is None:
            os.killpg(active.pid,signal.SIGTERM)
            try:active.wait(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(active.pid,signal.SIGKILL);active.wait()
        report.update(finished_at=datetime.now().astimezone().isoformat(),elapsed_seconds=time.monotonic()-started,storage_bytes=usage())
        write_new(OUT/'receipt.json',report)
        print(json.dumps(report),flush=True)
if __name__=='__main__':main()
