#!/bin/bash -l
#SBATCH --job-name=monitor-v2-recover
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_v2_recover-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
python - <<'PY'
from pathlib import Path
import datetime, hashlib, json, subprocess, tarfile, os
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.datetime.now().astimezone().isoformat()
base = Path('results/monitor_v2_baseline_v1_29488284')
archive = Path('monitor_v2_baseline_recovery_20261013.tar.gz')
manifest = Path('configs/monitor_v2_baseline_recovery_20261013_manifest.json')
assert not archive.exists() and not manifest.exists(), 'Do not replace recovery artifacts'
out = subprocess.run(['sacct','-j','29488038,29488284','--parsable2','--noheader',
    '--format=JobIDRaw,JobName,State,ExitCode,ElapsedRaw,AllocTRES,Submit,Start,End,NodeList'],
    text=True,capture_output=True,timeout=30)
assert out.returncode == 0, out.stderr
rows = [x.split('|') for x in out.stdout.splitlines()]
main = [x for x in rows if x[0]=='29488284']
assert len(main)==1 and main[0][2].split()[0] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'}, out.stdout
account = {'recorded_at':now(),'recovery_job_id':os.environ.get('SLURM_JOB_ID'),
    'sacct_argv':out.args,'sacct_stdout':out.stdout,'sacct_stderr':out.stderr,
    'baseline_gpu_seconds':int(main[0][4]),'preflight_cpu_seconds':sum(int(x[4]) for x in rows if x[0]=='29488038'),
    'baseline_state':main[0][2],'baseline_exit_code':main[0][3]}
queue = subprocess.run(['squeue','-u',os.environ['USER'],'-h','-o','%i|%j|%T|%M|%R'],text=True,capture_output=True,timeout=30)
account['queue_stdout']=queue.stdout
account['queue_returncode']=queue.returncode
acc = Path('results/monitor_v2_baseline_v1_29488284_accounting.json')
acc.write_text(json.dumps(account,indent=2)+'\n')
analysis = Path('analysis/monitor_v2_baseline_v1_29488284.json')
an = subprocess.run(['.venv/bin/python','scripts/analyze_monitor_v2_baseline_v1.py','analyze',
    '--directory',str(base),'--output',str(analysis)],text=True,capture_output=True,timeout=90)
attempt = Path('results/monitor_v2_baseline_v1_29488284_analysis_attempt.json')
attempt.write_text(json.dumps({'argv':an.args,'returncode':an.returncode,'stdout':an.stdout,'stderr':an.stderr},indent=2)+'\n')
plan = json.loads(Path('configs/monitor_v2_baseline_v1.json').read_text())
paths = set(plan['source_hashes']) | {x['path'] for x in plan['inputs']} | {x['view_path'] for x in plan['trajectories']}
paths.update(str(p) for p in base.rglob('*') if p.is_file())
paths.update(['configs/monitor_v2_baseline_v1.json','configs/monitor_v2_baseline_evaluation_v1.json',
    'results/monitor_v2_baseline_v1_submission.json','results/monitor_v2_baseline_v1.reservation.json',
    'results/monitor_v2_upload_receipt_20261013.json','results/monitor_v2_preflight_ood_20261013.json',
    'logs/monitor_v2_baseline-29488284.log','logs/monitor_v2_preflight-29488038.log',str(acc),str(attempt)])
ev=json.loads(Path('configs/monitor_v2_baseline_evaluation_v1.json').read_text())
paths.update(ev['reference_artifacts'])
if analysis.exists(): paths.add(str(analysis))
ood = Path('/home/hpcllm_rz377/ondemand/data/sys/dashboard/projects/vjd0pem5')
for name in ['monitor_v2_preflight_ood_20261013.sh','monitor_v2_baseline_ood_20261013.sh','monitor_v2_recover_ood_20261013.sh']:
    src=ood/name;dst=Path('scripts')/name
    if dst.exists(): assert dst.read_bytes()==src.read_bytes()
    else: dst.write_bytes(src.read_bytes())
    paths.add(str(dst))
missing=sorted(p for p in paths if not Path(p).is_file())
m={'created_at':now(),'job_id':'29488284','recovery_job_id':os.environ.get('SLURM_JOB_ID'),
   'analysis_returncode':an.returncode,'missing_files':missing,
   'files':{p:sha(p) for p in sorted(paths) if Path(p).is_file()}}
manifest.write_text(json.dumps(m,indent=2)+'\n')
with tarfile.open(archive,'w:gz') as t:
    for p in list(m['files'])+[str(manifest)]:t.add(p,arcname=p,recursive=False)
receipt={'created_at':now(),'archive':str(archive),'archive_sha256':sha(archive),
    'manifest':str(manifest),'manifest_sha256':sha(manifest),'file_count':len(m['files']),
    'analysis_returncode':an.returncode,'missing_files':missing,'training_runs':0,'extra_model_calls':0}
Path('results/monitor_v2_baseline_recovery_receipt_20261013.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2),flush=True)
PY
