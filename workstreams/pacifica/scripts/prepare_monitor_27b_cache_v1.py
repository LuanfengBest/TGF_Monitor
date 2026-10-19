"""Bounded official weight-cache preparation; no inference or training."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.request
from ollama_client import save

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT/'configs/monitor_27b_cache_v1.json'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''): h.update(chunk)
    return h.hexdigest()


def main():
    plan=json.loads(PLAN.read_text());job=os.environ['SLURM_JOB_ID']
    out=ROOT/'results'/f'monitor_27b_cache_v1_{job}';out.mkdir(parents=True,exist_ok=False)
    with (ROOT/'results/monitor_27b_cache_v1.reservation.json').open('x') as f:
        json.dump({'job_id':job,'output':str(out),'plan_sha256':digest(PLAN)},f)
    save(out/'plan.json',plan);rows=[];start=time.monotonic()
    try:
        for p,h in plan['source_hashes'].items(): assert digest(ROOT/p)==h,p
        manifest_path=ROOT/plan['manifest'];assert digest(manifest_path)==plan['model_digest']
        manifest=json.loads(manifest_path.read_text());cache=Path(plan['cache']);blobs=cache/'blobs';blobs.mkdir(parents=True,exist_ok=True)
        assert shutil.disk_usage(cache).free > plan['total_registry_bytes']+1024**3
        for layer in [manifest['config'],*manifest['layers']]:
            name=layer['digest'].replace(':','-');expected=layer['digest'].removeprefix('sha256:')
            assert re.fullmatch('[0-9a-f]{64}',expected)
            path=blobs/name;old=Path(plan['reuse_cache'])/'blobs'/name
            row={'digest':layer['digest'],'bytes':layer['size'],'status':'started'};rows.append(row)
            save(out/'summary.json',{'status':'running','layers':rows})
            if path.exists():
                assert path.stat().st_size==layer['size'] and digest(path)==expected
                row['status']='verified_existing'
            elif old.exists():
                assert old.stat().st_size==layer['size'] and digest(old)==expected
                path.symlink_to(old);row['status']='verified_reused_symlink'
            else:
                part=path.with_name(name+'.'+job+'.partial');h=hashlib.sha256();size=0
                with urllib.request.urlopen('https://registry.ollama.ai/v2/library/qwen3.5/blobs/'+layer['digest'],timeout=120) as response,part.open('xb') as f:
                    for chunk in iter(lambda:response.read(8*1024**2),b''):
                        f.write(chunk);h.update(chunk);size+=len(chunk)
                        assert size<=layer['size']
                        if time.monotonic()-start>plan['wall_timeout_seconds']:raise TimeoutError('Download budget exceeded')
                assert size==layer['size'] and h.hexdigest()==expected
                os.link(part,path);part.unlink();row['status']='downloaded_verified'
            save(out/'summary.json',{'status':'running','layers':rows});print(json.dumps(row),flush=True)
        tag=cache/'manifests/registry.ollama.ai/library/qwen3.5/27b';tag.parent.mkdir(parents=True,exist_ok=True)
        if tag.exists():assert tag.read_bytes()==manifest_path.read_bytes()
        else:
            with tag.open('xb') as f:f.write(manifest_path.read_bytes())
        assert digest(tag)==plan['model_digest']
        save(out/'summary.json',{'status':'complete','layers':rows,'model_digest':digest(tag),'wall_seconds':time.monotonic()-start,'inference_calls':0})
    except Exception as exc:
        save(out/'summary.json',{'status':'failed','layers':rows,'error':repr(exc),'inference_calls':0});raise


if __name__=='__main__':main()
