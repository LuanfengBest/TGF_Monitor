#!/bin/bash -l
#SBATCH --job-name=travel-projection-sync
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/travel_projection_sync-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
python - <<'PY'
from pathlib import Path, PurePosixPath
import hashlib,json,tarfile,datetime,subprocess,shutil,os
sha=lambda b:hashlib.sha256(b).hexdigest()
rp=Path('results/travel_projection_sync_receipt_20261014.json')
assert not rp.exists(), 'Closeout already completed'
reservation=Path('results/travel_projection_sync_20261014.reservation.json')
with reservation.open('x') as f:json.dump({'job_id':os.environ.get('SLURM_JOB_ID'),'created_at':datetime.datetime.now().astimezone().isoformat()},f)
a=Path('travel_projection_upload_20261014.tar.gz')
assert sha(a.read_bytes())=='46dde301985191c96a03bd15e724aadd0841d5710a1957d2b1215115cd96f410'
mp='configs/travel_projection_upload_20261014_manifest.json'
with tarfile.open(a) as t:
    ms=t.getmembers()
    assert len(ms)==len({m.name for m in ms})
    assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in ms)
    data={m.name:t.extractfile(m).read() for m in ms}
assert sha(data[mp])=='29ffbbd270e80ef4178efbc159e6c0e6a50a1397691a5310b4f3a0fdb19d464d'
m=json.loads(data[mp]);assert set(data)==set(m['files'])|{mp}
for p,h in m['files'].items():
    assert sha(data[p])==h
    if Path(p).exists():assert sha(Path(p).read_bytes()) in {h,m['allowed_remote_previous_sha256'].get(p)},p
if Path(mp).exists():assert Path(mp).read_bytes()==data[mp]
changed=[];new=[]
for p,b in data.items():
    target=Path(p)
    if target.exists() and target.read_bytes()==b:continue
    if target.exists():
        backup=Path(m['backup_root'])/p;assert not backup.exists()
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup);changed.append(p)
    else:new.append(p)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
for p,h in m['files'].items():assert sha(Path(p).read_bytes())==h
checks=[]
for args in [['.venv/bin/python','scripts/monitor_v2_baseline_v1.py','verify'],
             ['.venv/bin/python','scripts/prepare_travel_projection_v1.py','verify'],
             ['.venv/bin/python','scripts/analyze_travel_projection_v1.py'],
             ['sacct','-j','29494474','--parsable2','--noheader',
              '--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocTRES,Start,End']]:
    c=subprocess.run(args,text=True,capture_output=True,timeout=60)
    checks.append({'argv':args,'returncode':c.returncode,'stdout':c.stdout,'stderr':c.stderr})
    assert c.returncode==0,c.stderr
src=Path('/home/hpcllm_rz377/ondemand/data/sys/dashboard/projects/vjd0pem5/travel_projection_sync_ood_20261014.sh')
dst=Path('scripts/travel_projection_sync_ood_20261014.sh')
if dst.exists():assert dst.read_bytes()==src.read_bytes()
else:dst.write_bytes(src.read_bytes())
r={'completed_at':datetime.datetime.now().astimezone().isoformat(),'job_id':os.environ.get('SLURM_JOB_ID'),
   'status':'completed','archive_sha256':sha(a.read_bytes()),'manifest_sha256':sha(data[mp]),
   'files_verified':len(m['files']),'new_files':new,'backed_up_and_changed':changed,'checks':checks,
   'closeout_script_sha256':sha(src.read_bytes()),'training_runs':0,'model_calls':0}
rp.write_text(json.dumps(r,indent=2)+'\n')
print('CLOSEOUT_OK',sha(rp.read_bytes()),flush=True)
PY
