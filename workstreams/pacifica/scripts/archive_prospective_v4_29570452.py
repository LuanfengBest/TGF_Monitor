"""Archive one completed v4 job without changing its original artifacts."""
import datetime
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

job = '29570452'
root = Path.cwd()
run = Path('results') / ('prospective_actor_v4_' + job)
accounting = subprocess.check_output(['sacct', '-j', job, '--noheader', '--parsable2',
    '--format=JobID,State,ExitCode,ElapsedRaw,AllocTRES'], text=True)
line = next(x.split('|') for x in accounting.splitlines() if x.startswith(job + '|'))
assert line[1] in {'COMPLETED', 'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'CANCELLED'}, accounting
queue = subprocess.check_output(['squeue', '-u', 'hpcllm_rz377', '--noheader'], text=True)
assert job not in queue, 'Job still in queue'
receipt = Path('results/prospective_v4_29570452_closeout.json')
with receipt.open('x') as f:
    json.dump({'observed_at': datetime.datetime.now().astimezone().isoformat(),
        'job_id': job, 'sacct': accounting, 'squeue': queue}, f, indent=2)
paths = [p for p in run.rglob('*') if p.is_file()]
paths += [receipt, Path('logs/prospective_actor_v4-' + job + '.log'),
    Path('logs/prospective_preflight_v4.log'), Path('results/prospective_actor_v4_preflight.json'),
    Path('results/prospective_actor_v4_submission.json'), Path('results/prospective_actor_v4.reservation.json'),
    Path('results/prospective_actor_v4_sync_receipt_20261014.json'),
    Path('results/prospective_v4_preflight_supplement_receipt.json')]
assert all(p.is_file() and not p.is_symlink() for p in paths)
manifest = {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
target = Path('results/prospective_actor_v4_' + job + '_archive.zip')
with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for name in manifest:
        z.write(name, name)
    z.writestr('MANIFEST.json', json.dumps(manifest, indent=2))
print(json.dumps({'archive': str(target), 'files': len(manifest), 'bytes': target.stat().st_size,
    'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'sacct': accounting, 'squeue': queue}))
