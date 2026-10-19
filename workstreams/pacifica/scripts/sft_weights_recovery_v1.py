"""One streaming, pinned-revision CPU recovery. Keep prior failed files intact."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime/sft_weights_recovery_v1'
OLD = ROOT / 'runtime/tgf_sft_weights_v1'
RUNTIME = ROOT / 'runtime/tgf_sft_pilot_v1'
REV = '9216db5781bf21249d130ec9da846c4624c16137'
LIMIT = 90 * 1024**3


def save(path, obj):
    with path.open('x') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')


def physical_bytes():
    seen = set()
    total = 0
    for folder in (RUNTIME, OLD, OUT):
        if not folder.exists(): continue
        for p in folder.rglob('*'):
            if p.is_file():
                s = p.stat()
                identity = (s.st_dev, s.st_ino)
                if identity not in seen:
                    seen.add(identity)
                    total += s.st_size
    return total


def hashes(path, size, deadline):
    sha, git = hashlib.sha256(), hashlib.sha1()
    git.update(f'blob {size}\0'.encode())
    count = 0
    with path.open('rb') as f:
        while chunk := f.read(1024**2):
            if time.monotonic() > deadline: raise TimeoutError('Recovery deadline')
            count += len(chunk)
            sha.update(chunk); git.update(chunk)
        if hasattr(os, 'posix_fadvise'):
            os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return count, sha.hexdigest(), git.hexdigest()


def check_item(path, item, deadline):
    n, sha, git = hashes(path, item['size'], deadline)
    assert n == item['size'], 'File size mismatch'
    assert (sha == item['lfs']['sha256'] if 'lfs' in item else git == item['blobId']), 'Upstream hash mismatch'
    return {'file': item['rfilename'], 'bytes': n, 'sha256': sha, 'upstream_hash_verified': True}


def main():
    assert os.environ.get('SLURM_JOB_ID') and not os.environ.get('SLURM_JOB_GPUS')
    plan = json.loads((ROOT / 'configs/sft_weights_recovery_v1.json').read_text())
    for name, digest in plan['source_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    runtime = json.loads((RUNTIME/'receipt.json').read_text())
    assert runtime['status'] == 'cpu_imports_passed_gpu_and_weights_pending'
    metadata = json.loads((ROOT/'analysis/tgf_sft_qwen_pinned_files_20261014.json').read_text())
    assert metadata['sha'] == REV
    names = {'config.json','generation_config.json','tokenizer.json','tokenizer_config.json','model.safetensors.index.json'}
    items = [f for f in metadata['siblings'] if f['rfilename'].endswith('.safetensors') or f['rfilename'] in names]
    assert len(items) == 22
    OUT.mkdir(parents=True, exist_ok=False)
    report = {'status':'running', 'job_id':os.environ['SLURM_JOB_ID'], 'revision':REV,
        'started_at':datetime.now().astimezone().isoformat(), 'files':[], 'model_calls':0,
        'training_runs':0, 'retry':0, 'plan_sha256':hashlib.sha256((ROOT/'configs/sft_weights_recovery_v1.json').read_bytes()).hexdigest()}
    save(OUT/'reservation.json', report)
    start = time.monotonic()
    deadline = start + 1650
    def interrupted(signum, frame): raise TimeoutError(f'Signal {signum}')
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig, interrupted)
    try:
        quota = subprocess.run(['getquota','-g','hpcllm'], capture_output=True, text=True, timeout=45)
        report['quota'] = {'returncode':quota.returncode,'stdout':quota.stdout,'stderr':quota.stderr}
        match = re.search(r'^\s*project\s+GRP\s+([\d,]+)\s+([\d,]+)', quota.stdout, re.M)
        if quota.returncode or not match: raise ValueError('Quota cannot be verified')
        used, cap = (int(x.replace(',','')) for x in match.groups())
        expected_new = sum(x['size'] for x in items if not (OLD/x['rfilename']).exists())
        if cap-used < expected_new/1024**3 + 10: raise ValueError('Group quota insufficient')
        if physical_bytes() + expected_new > LIMIT: raise ValueError('90GiB experiment storage cap')
        if shutil.disk_usage(ROOT).free < expected_new + 10*1024**3: raise ValueError('Filesystem space insufficient')
        report['expected_new_bytes'] = expected_new
        for item in items:
            n = item['rfilename']
            if Path(n).name != n: raise ValueError('Unsafe filename')
            if (OLD/n).exists():
                row = check_item(OLD/n, item, deadline)
                os.link(OLD/n, OUT/n)
                row['source'] = 'verified_old_complete_hardlink'
            else:
                path = OUT/(n+'.part')
                size = 0
                url = f'https://huggingface.co/Qwen/Qwen3-32B/resolve/{REV}/{n}'
                with urllib.request.urlopen(url,timeout=45) as response, path.open('xb') as dest:
                    while chunk := response.read(1024**2):
                        if time.monotonic() > deadline: raise TimeoutError('Download deadline')
                        size += len(chunk)
                        if size > item['size']: raise ValueError('Oversize file')
                        dest.write(chunk)
                        if size % (64*1024**2) == 0:
                            dest.flush(); os.fsync(dest.fileno())
                            if hasattr(os,'posix_fadvise'):
                                os.posix_fadvise(dest.fileno(),0,0,os.POSIX_FADV_DONTNEED)
                            if shutil.disk_usage(ROOT).free < 10*1024**3: raise ValueError('Free space lost')
                row = check_item(path,item,deadline)
                path.rename(OUT/n)
                row['source'] = 'official_pinned_download'
            report['files'].append(row)
            with (OUT/'journal.jsonl').open('a') as f:
                f.write(json.dumps(row)+'\n'); f.flush()
            print('VERIFIED', n, row['bytes'], row['source'], flush=True)
        index = json.loads((OUT/'model.safetensors.index.json').read_text())
        assert set(index['weight_map'].values()) == {x['rfilename'] for x in items if x['rfilename'].endswith('.safetensors')}
        assert physical_bytes() <= LIMIT
        report['status'] = 'all_22_files_verified_gpu_preflight_pending'
    except BaseException as exc:
        report.update(status='failed', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        report.update(finished_at=datetime.now().astimezone().isoformat(),
            elapsed_seconds=time.monotonic()-start, storage_physical_bytes=physical_bytes())
        save(OUT/'receipt.json',report)
        print(json.dumps(report),flush=True)

if __name__ == '__main__': main()
