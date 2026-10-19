#!/bin/bash -l
#SBATCH --job-name=monitor-v2-preflight
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_v2_preflight-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
python - <<'PY'
from pathlib import Path, PurePosixPath
import hashlib, json, tarfile, datetime, subprocess, shutil, os, traceback
sha = lambda b: hashlib.sha256(b).hexdigest()
now = lambda: datetime.datetime.now().astimezone().isoformat()
receipt = Path('results/monitor_v2_upload_receipt_20261013.json')
attempt = Path('results/monitor_v2_preflight_ood_20261013.json')
assert not receipt.exists() and not attempt.exists(), 'Do not duplicate completed or partial preflight'
r = {'started_at': now(), 'job_id': os.environ.get('SLURM_JOB_ID'), 'status': 'started',
     'interface': 'Open OnDemand Project Manager', 'checks': [], 'training_runs': 0, 'model_calls': 0}
attempt.write_text(json.dumps(r, indent=2)+'\n')
try:
    ap = Path('monitor_v2_upload_20261013.tar.gz')
    assert sha(ap.read_bytes()) == '8feb9af51af017df4a131c36cfcc98e33a170b47ecb6070df503649710dcc3d8'
    mp = 'configs/monitor_v2_upload_20261013_manifest.json'
    with tarfile.open(ap) as t:
        members = t.getmembers()
        assert len({m.name for m in members}) == len(members)
        assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members)
        data = {m.name: t.extractfile(m).read() for m in members}
    assert sha(data[mp]) == '31409f20c042d1b64a6bf193e054e6ad6fab4050f548127b2a5b40e24c5f31d2'
    m = json.loads(data[mp])
    assert set(data) == set(m['files']) | {mp}
    for p, h in m['files'].items():
        assert sha(data[p]) == h, p
        if Path(p).exists():
            assert sha(Path(p).read_bytes()) in {h, m['allowed_remote_previous_sha256'].get(p)}, p
    if Path(mp).exists():
        assert Path(mp).read_bytes() == data[mp]
    changed, new = [], []
    for p, b in data.items():
        target = Path(p)
        if target.exists() and target.read_bytes() == b:
            continue
        if target.exists():
            dest = Path(m['backup_root']) / p
            assert not dest.exists(), str(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            changed.append(p)
        else:
            new.append(p)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b)
    r.update(archive_sha256=sha(ap.read_bytes()), manifest_sha256=sha(data[mp]),
             files_verified=len(m['files']), archive_members=len(data),
             new_files=new, backed_up_and_changed=changed)
    commands = [['.venv/bin/python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v']
                for pattern in ['test_monitor_v2_task_adapters.py', 'test_monitor_v2_audit_v1.py', '*monitor_v2_baseline_v1.py']]
    commands += [['.venv/bin/python', 'scripts/prepare_monitor_v2_audit_v1.py', 'verify'],
                 ['.venv/bin/python', 'scripts/monitor_v2_baseline_v1.py', 'verify']]
    for args in commands:
        c = subprocess.run(args, text=True, capture_output=True, timeout=80)
        r['checks'].append({'argv': args, 'returncode': c.returncode, 'stdout': c.stdout, 'stderr': c.stderr})
        print('CHECK', args, c.returncode, flush=True)
        assert c.returncode == 0, c.stderr
    r.update(status='completed', completed_at=now())
    receipt.write_text(json.dumps(r, indent=2)+'\n')
    print('SYNC_OK', sha(receipt.read_bytes()), len(m['files']), len(changed), len(new), flush=True)
except BaseException:
    r.update(status='failed', failed_at=now(), error=traceback.format_exc())
    raise
finally:
    attempt.write_text(json.dumps(r, indent=2)+'\n')
PY
