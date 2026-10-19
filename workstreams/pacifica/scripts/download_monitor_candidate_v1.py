"""Fetch content-addressed official Ollama layers in a bounded CPU job."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.request
from monitor_candidate_v1 import ROOT, PLAN, read, sha, verify
from ollama_client import save


def file_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main():
    plan=read(PLAN);verify(plan)
    job=os.environ['SLURM_JOB_ID'];out=ROOT/'results'/f'monitor_candidate_download_{job}'
    out.mkdir(parents=True,exist_ok=False)
    with (ROOT/'results/monitor_candidate_download_v1.reservation.json').open('x') as f:
        json.dump({'job_id':job,'output':str(out),'plan_sha256':sha(PLAN)},f)
    cache=Path(os.environ['OLLAMA_MODELS'])
    manifest_path=ROOT/'data/tokenizers/qwen3_5_9b/ollama_manifest.json'
    if sha(manifest_path)!=plan['model_digest']: raise ValueError('Manifest digest mismatch')
    manifest=read(manifest_path); layers=[manifest['config'],*manifest['layers']]
    blobs=cache/'blobs';blobs.mkdir(parents=True,exist_ok=True)
    required=sum(l['size'] for l in layers if not (blobs/l['digest'].replace(':','-')).exists())
    if shutil.disk_usage(cache).free < required+1024**3: raise RuntimeError('Insufficient free space')
    target=cache/'manifests/registry.ollama.ai/library/qwen3.5/9b'
    if target.exists() and target.read_bytes()!=manifest_path.read_bytes():
        raise RuntimeError('Existing different model tag; refusing overwrite')
    rows=[];save(out/'plan.json',plan);start=time.monotonic()
    try:
        for layer in layers:
            digest=layer['digest'];expected=digest.removeprefix('sha256:')
            if not re.fullmatch(r'sha256:[0-9a-f]{64}',digest): raise ValueError('Invalid digest')
            path=blobs/digest.replace(':','-')
            row={'digest':digest,'bytes':layer['size'],'media_type':layer['mediaType']}
            rows.append(row)
            if path.exists():
                if path.stat().st_size!=layer['size'] or file_digest(path)!=expected:
                    raise ValueError('Existing blob integrity failure')
                row['status']='verified_existing'
            else:
                url='https://registry.ollama.ai/v2/library/qwen3.5/blobs/'+digest
                partial=path.with_name(path.name+'.candidate-v1-'+job+'.partial')
                h=hashlib.sha256();count=0
                with urllib.request.urlopen(url,timeout=120) as response, partial.open('xb') as f:
                    while True:
                        chunk=response.read(8*1024*1024)
                        if not chunk: break
                        f.write(chunk);h.update(chunk);count+=len(chunk)
                        if count>layer['size']: raise ValueError('Oversized blob')
                        if time.monotonic()-start>1140: raise TimeoutError('Download time budget')
                if count!=layer['size'] or h.hexdigest()!=expected: raise ValueError('Downloaded blob integrity failure')
                # Link atomically without replacing any concurrently created blob.
                try: os.link(partial,path)
                except FileExistsError:
                    if file_digest(path)!=expected: raise ValueError('Concurrent blob conflict')
                partial.unlink();row['status']='downloaded_verified'
            save(out/'summary.json',{'status':'running','layers':rows})
            print(json.dumps(row),flush=True)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            with target.open('xb') as f: f.write(manifest_path.read_bytes())
        if sha(target)!=plan['model_digest']: raise ValueError('Installed manifest mismatch')
        save(out/'summary.json',{'status':'complete','layers':rows,'model_digest':sha(target),
                                'elapsed_seconds':time.monotonic()-start})
    except Exception as exc:
        save(out/'summary.json',{'status':'failed','error':repr(exc),'layers':rows});raise

if __name__=='__main__': main()
