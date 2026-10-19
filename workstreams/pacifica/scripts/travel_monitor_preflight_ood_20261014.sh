#!/bin/bash -l
#SBATCH --job-name=travel-monitor-preflight
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/travel_monitor_preflight-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
python - '6ad2b04c92b55a7f999843671f95e6af1ed3866c074027eccbe8b6b0535ad477' '0b376ed825b8b3a16a741e5ced764c7fcde5862b0be991058ae409a405bc5e1d' <<'PREFLIGHT_PY'
"""Bounded OOD CPU installation and verification; never submits a GPU job."""
from pathlib import Path, PurePosixPath
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile


def main(archive_sha, manifest_sha):
    root = Path.cwd().resolve()
    if str(root) != '/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf':
        raise ValueError('Unexpected destination')
    sha = lambda b: hashlib.sha256(b).hexdigest()
    now = lambda: datetime.datetime.now().astimezone().isoformat()
    receipt = root / 'results/travel_monitor_preflight_receipt_20261014.json'
    reservation = root / 'results/travel_monitor_preflight_20261014.reservation.json'
    with reservation.open('x') as f:
        json.dump({'job_id': os.environ.get('SLURM_JOB_ID'), 'created_at': now()}, f)
        f.flush(); os.fsync(f.fileno())
    if receipt.exists():
        raise ValueError('Preflight receipt already exists')
    result = {'created_at': now(), 'job_id': os.environ.get('SLURM_JOB_ID'), 'status': 'running',
              'checks': [], 'model_calls': 0, 'training_runs': 0, 'new_files': [], 'backed_up_files': []}
    try:
        archive = root / 'travel_monitor_upload_20261014.tar.gz'
        mp = 'configs/travel_monitor_upload_20261014_manifest.json'
        if sha(archive.read_bytes()) != archive_sha:
            raise ValueError('Archive hash mismatch')
        with tarfile.open(archive) as t:
            members = t.getmembers()
            if len(members) != len({m.name for m in members}):
                raise ValueError('Duplicate archive path')
            if not all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members):
                raise ValueError('Unsafe archive member')
            data = {m.name: t.extractfile(m).read() for m in members}
        if sha(data[mp]) != manifest_sha:
            raise ValueError('Manifest hash mismatch')
        manifest = json.loads(data[mp])
        if set(data) != set(manifest['files']) | {mp}:
            raise ValueError('Archive coverage differs')
        for p, b in data.items():
            dest = root / p
            if not dest.resolve().is_relative_to(root) or dest.is_symlink():
                raise ValueError('Unsafe destination: ' + p)
            if p != mp and sha(b) != manifest['files'][p]:
                raise ValueError('Member hash differs: ' + p)
            if dest.exists() and dest.read_bytes() != b:
                allowed = manifest['allowed_remote_previous_sha256'].get(p, [])
                if sha(dest.read_bytes()) not in allowed:
                    raise ValueError('Unknown remote content: ' + p)
                backup = root / manifest['backup_root'] / p
                if backup.exists() or not backup.resolve().is_relative_to(root):
                    raise ValueError('Unsafe/existing backup: ' + p)
        for p, b in data.items():
            dest = root / p
            if dest.exists() and dest.read_bytes() == b:
                continue
            if dest.exists():
                backup = root / manifest['backup_root'] / p
                backup.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(dest, backup)
                result['backed_up_files'].append(p)
            else:
                result['new_files'].append(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open('wb') as f:
                f.write(b); f.flush(); os.fsync(f.fileno())
        for p, h in manifest['files'].items():
            if sha((root / p).read_bytes()) != h:
                raise ValueError('Written member hash differs: ' + p)
        result.update(files_verified=len(manifest['files']), archive_sha256=archive_sha,
                      manifest_sha256=manifest_sha,
                      plan_sha256=sha((root / 'configs/travel_monitor_baseline_v1.json').read_bytes()))
        commands = [
            ['.venv/bin/python', 'scripts/monitor_v2_baseline_v1.py', 'verify'],
            ['.venv/bin/python', 'scripts/prepare_travel_projection_v1.py', 'verify'],
            ['.venv/bin/python', 'scripts/analyze_travel_projection_v1.py'],
            ['.venv/bin/python', 'scripts/travel_monitor_baseline_v1.py', 'verify'],
            ['.venv/bin/python', 'scripts/analyze_travel_monitor_baseline_v1.py', 'verify'],
            ['.venv/bin/python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_travel_monitor_baseline_v1.py', '-v'],
        ]
        for argv in commands:
            c = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            result['checks'].append({'argv': argv, 'returncode': c.returncode, 'stdout': c.stdout, 'stderr': c.stderr})
            if c.returncode:
                raise ValueError('Remote check failed: ' + repr(argv))
        result['status'] = 'completed'
    except BaseException as exc:
        result.update(status='failed', error=repr(exc)); raise
    finally:
        result['finished_at'] = now()
        with receipt.open('x') as f:
            f.write(json.dumps(result, indent=2) + '\n'); f.flush(); os.fsync(f.fileno())
        print(json.dumps({k: v for k, v in result.items() if k != 'checks'}), flush=True)


if __name__ == '__main__': main(*sys.argv[1:])

PREFLIGHT_PY
