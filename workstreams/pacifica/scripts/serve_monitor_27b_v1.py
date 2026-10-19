"""Verify and supervise an isolated, job-scoped official Ollama process."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from ollama_client import save
from prepare_monitor_runtime_v1 import inventory, sha
from monitor_27b_v1 import ROOT, PLAN, verify, read

def main():
    plan=read(PLAN);verify(plan)
    setup=read(ROOT/'configs/monitor_runtime_v1.json')
    record=read(ROOT/'results/monitor_runtime_v1_installation.json')
    out=ROOT/f'results/monitor_27b_v1_{os.environ["SLURM_JOB_ID"]}'
    out.mkdir(exist_ok=False)
    save(out/'lifecycle.json',{'status':'verifying','job_id':os.environ['SLURM_JOB_ID']})
    assert record['status']=='ready' and record['asset']==plan['runtime_asset']
    runtime=Path(setup['runtime_root']);models=Path(plan['model_cache'])
    assert inventory(runtime)==record['files'], 'Runtime files changed after installation'
    manifest=models/'manifests/registry.ollama.ai/library/qwen3.5/27b'
    assert sha(manifest)==plan['model_digest']
    cache=read(ROOT/'results/monitor_27b_cache_v1_29447985/summary.json')
    assert cache['status']=='complete' and cache['model_digest']==plan['model_digest']
    for layer in cache['layers']:
        assert (models/'blobs'/layer['digest'].replace(':','-')).stat().st_size==layer['bytes']
    save(out/'installation.json',{'asset':record['asset'],'runtime_root':str(runtime),
                                'files':record['files'],'model_manifest_sha256':sha(manifest),
                                'model_cache':str(models),'cache_record':cache})
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('OLLAMA_') or key in ('REAL_OLLAMA_BIN','TGF_OLLAMA_URL'):
            env.pop(key)
    env.update(OLLAMA_HOST=f'127.0.0.1:{port}',OLLAMA_MODELS=str(models),
               OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',
               OLLAMA_CONTEXT_LENGTH='32768',OLLAMA_NOPRUNE='1',
               OLLAMA_NO_CLOUD='1',OLLAMA_VULKAN='0')
    env['TGF_OLLAMA_URL']='http://'+env['OLLAMA_HOST']
    server=None;child=None;start=time.monotonic();status='starting';exitcode=1
    def terminated(signum,frame):
        raise RuntimeError(f'Supervisor received signal {signum}')
    signal.signal(signal.SIGTERM,terminated)
    try:
        with (out/'server.log').open('w') as log:
            server=subprocess.Popen([str(runtime/'bin/ollama'),'serve'],env=env,
                                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(out/'lifecycle.json',{'status':'starting','server_pid':server.pid,
                                      'job_id':os.environ['SLURM_JOB_ID'],
                                      'environment':{k:v for k,v in env.items() if k.startswith('OLLAMA_')}})
            while True:
                if server.poll() is not None: raise RuntimeError('Server exited at startup')
                if time.monotonic()-start>60: raise RuntimeError('Server readiness timeout')
                try:
                    with urllib.request.urlopen(env['TGF_OLLAMA_URL']+'/api/version',timeout=2) as r:
                        version=json.load(r)
                    if version!=plan['service_version_response']: raise ValueError('Unexpected API version')
                    break
                except OSError:
                    time.sleep(.25)
            child=subprocess.Popen([sys.executable,str(ROOT/'scripts/monitor_27b_v1.py'),
                                    '--output',str(out)],env=env)
            exitcode=child.wait(timeout=plan['runner_wall_seconds']+30)
            status='finished' if exitcode==0 else 'runner_failed'
    except Exception as exc:
        save(out/'supervisor_error.json',{'error':repr(exc)})
        status='supervisor_failed'
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill();child.wait()
        if server is not None:
            try: os.killpg(server.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid,signal.SIGKILL);server.wait()
        save(out/'lifecycle.json',{'status':status,'job_id':os.environ['SLURM_JOB_ID'],
                                  'runner_exitcode':exitcode,'server_stopped':server is None or server.poll() is not None,
                                  'wall_seconds':time.monotonic()-start,
                                  'model_manifest_unchanged':sha(manifest)==plan['model_digest']})
    return exitcode

if __name__=='__main__':
    sys.exit(main())
