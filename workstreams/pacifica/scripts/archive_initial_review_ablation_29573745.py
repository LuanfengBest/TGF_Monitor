"""Archive one completed initial-review ablation job without changing its original artifacts."""
import datetime
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

job = '29573745'
root = Path.cwd()
run = Path('results') / ('initial_review_ablation_v1_' + job)
accounting = subprocess.check_output(['sacct', '-j', job, '--noheader', '--parsable2',
    '--format=JobID,State,ExitCode,ElapsedRaw,AllocTRES'], text=True)
line = next(x.split('|') for x in accounting.splitlines() if x.startswith(job + '|'))
assert line[1] in {'COMPLETED', 'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'CANCELLED'}, accounting
queue = subprocess.check_output(['squeue', '-u', 'hpcllm_rz377', '--noheader'], text=True)
assert job not in queue, 'Job still in queue'
receipt = Path('results/initial_review_ablation_29573745_closeout.json')
with receipt.open('x') as f:
    json.dump({'observed_at': datetime.datetime.now().astimezone().isoformat(),
        'job_id': job, 'sacct': accounting, 'squeue': queue}, f, indent=2)
paths = [p for p in run.rglob('*') if p.is_file()]
paths += [receipt, Path('logs/initial_review_ablation_v1-' + job + '.log'),
    Path('results/initial_review_ablation_v1_submission.json'), Path('results/initial_review_ablation_v1.reservation.json'),
    Path('results/initial_review_ablation_v1_sync_receipt.json')]
assert all(p.is_file() and not p.is_symlink() for p in paths)
manifest = {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
target = Path('results/initial_review_ablation_v1_' + job + '_archive.zip')
with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for name in manifest:
        z.write(name, name)
    z.writestr('MANIFEST.json', json.dumps(manifest, indent=2))
print(json.dumps({'archive': str(target), 'files': len(manifest), 'bytes': target.stat().st_size,
    'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'sacct': accounting, 'squeue': queue}))
