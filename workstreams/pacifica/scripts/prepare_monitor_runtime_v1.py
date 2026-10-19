"""Install one pinned official runtime on a bounded CPU allocation; no inference."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
from ollama_client import save

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'configs/monitor_runtime_v1.json'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def inventory(root):
    rows = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            rows[str(p.relative_to(root))] = {'link': os.readlink(p)}
        elif p.is_file():
            rows[str(p.relative_to(root))] = {'size': p.stat().st_size, 'sha256': sha(p)}
    return rows

def main():
    plan = json.loads(PLAN.read_text())
    job = os.environ['SLURM_JOB_ID']
    out = ROOT / f'results/monitor_runtime_v1_{job}'
    out.mkdir(exist_ok=False)
    with (ROOT/'results/monitor_runtime_v1.reservation.json').open('x') as f:
        json.dump({'job_id': job, 'plan_sha256': sha(PLAN)}, f)
    save(out/'plan.json', plan)
    start = time.monotonic()
    try:
        runtime = Path(plan['runtime_root'])
        runtime.mkdir(parents=True, exist_ok=False)
        asset = runtime.parent / plan['asset']['name']
        if asset.exists():
            raise RuntimeError('Asset path already exists; inspect instead of retrying')
        subprocess.run(['curl', '-fL', '--max-time', '600', '--retry', '0',
                        plan['asset']['browser_download_url'], '-o', str(asset)], check=True)
        assert asset.stat().st_size == plan['asset']['size']
        assert 'sha256:' + sha(asset) == plan['asset']['digest']
        proc = subprocess.Popen(['zstd', '-dc', str(asset)], stdout=subprocess.PIPE)
        with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
            for member in archive:
                p = Path(member.name)
                assert not p.is_absolute() and '..' not in p.parts
                assert p.parts and p.parts[0] in ('bin', 'lib')
                archive.extract(member, runtime, filter='data')
        proc.stdout.close()
        assert proc.wait() == 0
        assert (runtime/'bin/ollama').is_file()
        models = Path(plan['isolated_models'])
        models.mkdir(parents=True, exist_ok=False)
        (models/'blobs').mkdir()
        manifest_path = ROOT/'data/tokenizers/qwen3_5_9b/ollama_manifest.json'
        assert sha(manifest_path) == plan['model_manifest_sha256']
        manifest = json.loads(manifest_path.read_text())
        verified = []
        for layer in [manifest['config'], *manifest['layers']]:
            name = layer['digest'].replace(':', '-')
            source = Path(plan['source_models'])/'blobs'/name
            assert source.stat().st_size == layer['size']
            assert 'sha256:' + sha(source) == layer['digest']
            # Existing content-addressed blobs are read by the new runtime; its
            # manifest directory is separate and no pruning/migration is invoked.
            (models/'blobs'/name).symlink_to(source)
            verified.append({'path': str(source), **layer})
        target = models/'manifests/registry.ollama.ai/library/qwen3.5/9b'
        target.parent.mkdir(parents=True)
        target.write_bytes(manifest_path.read_bytes())
        record = {'status': 'ready', 'job_id': job, 'runtime_root': str(runtime),
                  'asset': plan['asset'], 'files': inventory(runtime),
                  'model_blobs': verified, 'isolated_models': str(models),
                  'model_manifest_sha256': sha(target),
                  'wall_seconds': time.monotonic()-start}
        save(out/'installation.json', record)
        save(ROOT/'results/monitor_runtime_v1_installation.json', record)
        print(json.dumps({k: record[k] for k in ['status','job_id','wall_seconds']}), flush=True)
    except Exception as exc:
        save(out/'error.json', {'error': repr(exc), 'wall_seconds': time.monotonic()-start})
        raise

if __name__ == '__main__':
    main()
