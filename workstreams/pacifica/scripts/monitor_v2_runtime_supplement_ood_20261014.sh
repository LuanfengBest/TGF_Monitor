#!/bin/bash -l
#SBATCH --job-name=monitor-v2-runtime-supplement
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_v2_runtime_readonly-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
.venv/bin/python - <<'PY'
from pathlib import Path
import subprocess, json, os, datetime, importlib.metadata, hashlib
p=Path('results/monitor_v2_runtime_supplement_20261014.json')
# Exclusive reservation prevents repeated sampling on timer retries.
reservation=Path('results/monitor_v2_runtime_supplement_20261014.reservation.json')
with reservation.open('x') as f:json.dump({'job_id':os.environ.get('SLURM_JOB_ID')},f)
commands=[['getquota','-g','hpcllm'],['sinfo','-p','gpu_devel','-o','%P|%a|%l|%G|%m'],
          ['scontrol','show','partition','gpu_devel'],['squeue','--me','-o','%i|%j|%T|%M|%l'],
          ['sacct','-j','29493425','--parsable2','--noheader','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocTRES,Start,End']]
checks=[]
for argv in commands:
    try:
        c=subprocess.run(argv,text=True,capture_output=True,timeout=45)
        checks.append({'argv':argv,'returncode':c.returncode,'stdout':c.stdout,'stderr':c.stderr})
    except Exception as e:checks.append({'argv':argv,'error':str(e)})
deps={}
for name in ['torch','transformers','peft','trl','bitsandbytes','datasets','accelerate']:
    try:deps[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:deps[name]=None
roots=[Path.home()/'.cache/huggingface/hub/models--Qwen--Qwen3-32B']
if os.environ.get('HF_HOME'):roots.append(Path(os.environ['HF_HOME'])/'hub/models--Qwen--Qwen3-32B')
if os.environ.get('HUGGINGFACE_HUB_CACHE'):roots.append(Path(os.environ['HUGGINGFACE_HUB_CACHE'])/'models--Qwen--Qwen3-32B')
cache=[{'path':str(x),'exists':x.exists(),'scope':'Only explicitly configured or default HF model cache; not exhaustive filesystem search.'} for x in dict.fromkeys(roots)]
r={'checked_at':datetime.datetime.now().astimezone().isoformat(),'job_id':os.environ.get('SLURM_JOB_ID'),
   'read_only_system_checks':True,'checks':checks,'installed_distributions':deps,'qwen_hf_cache_presence':cache,
   'training_runs':0,'model_calls':0,'gpu_allocated':False,'weights_downloaded':False,
   'training_memory_or_gradients_verified':False,'training_eligible':False}
with p.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
print('READONLY_REPORT',str(p),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
PY
