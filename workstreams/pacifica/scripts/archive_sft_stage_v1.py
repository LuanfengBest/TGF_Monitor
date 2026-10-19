"""Archive one terminal stage, preserving adapter binaries remotely with hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=('preflight', 'ordinary_sft', 'evidence_sft', 'evaluation'))
    args = p.parse_args()
    submission = ROOT / 'results' / f'sft_three_arm_v1_{args.stage}_submission.json'
    receipt = json.loads(submission.read_text())
    assert receipt['status'] == 'submitted'
    job = receipt['stdout'].strip().split(';')[0]
    assert job.isdigit()
    queue = subprocess.check_output(['squeue', '-j', job, '-h'], text=True)
    assert not queue.strip(), 'Job is still queued/running; archive only terminal state'
    accounting = subprocess.check_output([
        'sacct', '-j', job, '-n', '-P', '-o',
        'JobID,State,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocTRES,NodeList'
    ], text=True)
    main_row = next(x.split('|') for x in accounting.splitlines() if x.split('|')[0] == job)
    assert main_row[1].split()[0] in {
        'COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED', 'OUT_OF_MEMORY',
        'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'
    }, main_row
    stage_dir = ROOT / 'results/sft_three_arm_v1' / args.stage
    files = [submission] + sorted(stage_dir.rglob('*'))
    files += sorted((ROOT / 'logs').glob(f'sft_three_arm_v1_{args.stage}-{job}.log'))
    files = [x for x in files if x.is_file()]
    archived, retained = {}, {}
    for f in files:
        name = str(f.relative_to(ROOT))
        entry = {'sha256': sha(f), 'bytes': f.stat().st_size}
        if f.suffix in ('.safetensors', '.bin'):
            retained[name] = entry
        else:
            archived[name] = entry
    out = ROOT / 'results' / f'sft_three_arm_v1_{args.stage}_{job}_terminal.zip'
    manifest = {
        'stage': args.stage, 'job_id': job, 'sacct': accounting,
        'files': archived, 'adapter_binaries_retained_remote': retained,
        'stage_receipt_present': (stage_dir / 'receipt.json').exists(),
        'training_or_inference_calls_by_archiver': 0,
    }
    with zipfile.ZipFile(out, 'x', zipfile.ZIP_DEFLATED) as z:
        for name in archived:
            z.write(ROOT / name, name)
        z.writestr('stage_archive_manifest.json', json.dumps(manifest, indent=2))
    print(json.dumps({'archive': str(out.relative_to(ROOT)), 'sha256': sha(out),
                      'archived_files': len(archived), 'retained_binaries': len(retained),
                      'sacct': accounting}), flush=True)


if __name__ == '__main__':
    main()
