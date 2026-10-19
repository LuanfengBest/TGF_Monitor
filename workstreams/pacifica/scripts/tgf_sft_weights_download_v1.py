"""One bounded official fixed-revision model download; no model/GPU execution."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib,json,os,shutil,signal,threading,time,urllib.request
from pathlib import Path
ROOT=Path('/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf')
BUNDLE=Path(__file__).resolve().parent
REV='9216db5781bf21249d130ec9da846c4624c16137'
OUT=ROOT/'runtime/tgf_sft_weights_v1'
STOP=threading.Event()

def write_new(path,obj):
 with path.open('x') as f:json.dump(obj,f,indent=2);f.write('\n')

def main():
 if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_JOB_GPUS'):raise RuntimeError('CPU Slurm required')
 bundle=json.loads((BUNDLE/'manifest.json').read_text())
 for n,h in bundle['files'].items():
  if Path(n).name!=n or hashlib.sha256((BUNDLE/n).read_bytes()).hexdigest()!=h:raise ValueError('Bundle source hash mismatch')
 runtime=json.loads((ROOT/'runtime/tgf_sft_pilot_v1/receipt.json').read_text())
 if runtime['status']!='cpu_imports_passed_gpu_and_weights_pending':raise ValueError('Runtime not passed')
 metadata=json.loads((BUNDLE/'tgf_sft_qwen_pinned_files_20261014.json').read_text())
 if metadata['sha']!=REV:raise ValueError('Wrong base revision')
 names={'config.json','generation_config.json','tokenizer.json','tokenizer_config.json','model.safetensors.index.json'}
 files=[f for f in metadata['siblings'] if f['rfilename'].endswith('.safetensors') or f['rfilename'] in names]
 if len(files)!=22 or sum(f['rfilename'].endswith('.safetensors') for f in files)!=17:raise ValueError('Unexpected model files')
 expected=sum(f['size'] for f in files)
 if runtime['storage_bytes']+expected>90*1024**3 or shutil.disk_usage(ROOT).free<expected+10*1024**3:raise ValueError('Storage gate failed')
 OUT.mkdir(parents=True,exist_ok=False)
 report={'status':'running','job_id':os.environ['SLURM_JOB_ID'],'revision':REV,'files':[],'weights_expected_bytes':expected,
         'runtime_bytes_at_start':runtime['storage_bytes'],'started_at':datetime.now().astimezone().isoformat(),
         'model_calls':0,'training_runs':0,'gpu_allocated':False,'no_retry':True}
 write_new(OUT/'reservation.json',report)
 start=time.monotonic();deadline=start+1650
 def stop(signum,frame):STOP.set();raise RuntimeError('Interrupted '+str(signum))
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 def fetch(item):
  n=item['rfilename']
  if Path(n).name!=n:raise ValueError('Unsafe filename')
  sha=hashlib.sha256();git=hashlib.sha1();git.update(f'blob {item["size"]}\0'.encode());total=0
  path=OUT/(n+'.part');url=f'https://huggingface.co/Qwen/Qwen3-32B/resolve/{REV}/{n}'
  with path.open('xb') as dest, urllib.request.urlopen(url,timeout=45) as response:
   while True:
    if STOP.is_set() or time.monotonic()>deadline:raise RuntimeError('Download deadline/stop')
    if shutil.disk_usage(ROOT).free<10*1024**3:raise RuntimeError('Free space gate lost')
    chunk=response.read(8*1024**2)
    if not chunk:break
    total+=len(chunk)
    if total>item['size']:raise ValueError('Oversize download')
    dest.write(chunk);sha.update(chunk);git.update(chunk)
  if total!=item['size']:raise ValueError('Truncated download')
  if 'lfs' in item:
   if sha.hexdigest()!=item['lfs']['sha256']:raise ValueError('Official LFS SHA mismatch')
  elif git.hexdigest()!=item['blobId']:raise ValueError('Official Git blob mismatch')
  path.rename(OUT/n)
  return {'file':n,'bytes':total,'sha256':sha.hexdigest(),'upstream_hash_verified':True}
 try:
  with ThreadPoolExecutor(max_workers=2) as executor:
   pending={executor.submit(fetch,f):f['rfilename'] for f in files}
   try:
    for fut in as_completed(pending,timeout=1660):
     row=fut.result();report['files'].append(row)
     with (OUT/'download_journal.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
     print('VERIFIED',row['file'],row['bytes'],flush=True)
   except BaseException:
    STOP.set()
    for fut in pending:fut.cancel()
    raise
  index=json.loads((OUT/'model.safetensors.index.json').read_text())
  if set(index['weight_map'].values())!={r['file'] for r in report['files'] if r['file'].endswith('.safetensors')}:raise ValueError('Shard index mismatch')
  report['status']='all_22_files_verified_gpu_preflight_pending'
 except BaseException as e:
  report['status']='failed';report['error']=type(e).__name__+': '+str(e);raise
 finally:
  report.update(finished_at=datetime.now().astimezone().isoformat(),elapsed_seconds=time.monotonic()-start,
                storage_bytes=sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()))
  write_new(OUT/'receipt.json',report);print(json.dumps(report),flush=True)
if __name__=='__main__':main()
