"""Audit and export the completed allocation; performs no model calls."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import jev_deploy_20261112 as deploy

ROOT, BUNDLE, SEAL = deploy.ROOT, deploy.BUNDLE, deploy.SEAL
JOB = '33071622'
sys.path.insert(0, str(ROOT))
from jev_monitor_v1 import core
from jev_monitor_v1.run import planned, verify_manifest, ensure_smoke, read, filehash

assert verify_manifest(BUNDLE) == SEAL
ensure_smoke(BUNDLE, 'jev', SEAL)
ensure_smoke(BUNDLE, 'qwen', SEAL)
requests = planned(BUNDLE)
qwen = [r for r in requests if r['model'] == 'qwen']
assert len(qwen) == 124
ready = read(BUNDLE/'results/qwen_ready.json')
finish = read(BUNDLE/'results/allocation_finished.json')
assert ready['job_id'] == finish['job_id'] == JOB
assert finish['exit_code'] == 0 and finish['gpus'] == 1
assert 0 < finish['allocation_wall_seconds'] <= 5400
local_capacity = {r['request_id']:r for r in read(BUNDLE/'capacity_LOCAL.json')['requests']}
status_counts = {}
input_tokens = output_tokens = 0
for req in qwen:
    rid = req['request_id']
    slot = BUNDLE/'results'/rid
    dispatch, result, raw = [read(slot/name) for name in ('dispatch.json','result.json','raw.json')]
    assert dispatch['manifest_sha256'] == SEAL and dispatch['request_sha256'] == core.digest(req)
    assert dispatch['job_id'] == JOB and dispatch['attempt'] == 1
    assert result['request_id'] == rid and result['model'] == 'qwen'
    assert result['raw_sha256'] == filehash(slot/'raw.json')
    parsed = core.parse_response('qwen', raw)
    assert all(result.get(key) == value for key,value in parsed.items())
    assert result['status'] in ('valid','abstention'), (rid, result['status'])
    assert result['usage_complete'] and result['returned_model'] == 'Qwen/Qwen3-32B'
    assert result['native_prompt_sha256'] == ready['capacity'][rid]['prompt_sha256'] == local_capacity[rid]['prompt_sha256']
    assert result['usage']['input_tokens'] == ready['capacity'][rid]['prompt_tokens']
    assert 0 <= result['usage']['output_tokens'] <= 2048
    status_counts[result['status']] = status_counts.get(result['status'],0) + 1
    input_tokens += result['usage']['input_tokens']
    output_tokens += result['usage']['output_tokens']
all_dispatches = list((BUNDLE/'results').glob('*/dispatch.json'))
assert len(all_dispatches) == 128
assert sum(read(p)['model']=='qwen' for p in all_dispatches) == 124
cmd = ['sacct','-j',JOB,'--parsable2','--noheader','--format=JobID,State,ExitCode,ElapsedRaw,Start,End,AllocTRES']
completed = subprocess.run(cmd,capture_output=True,text=True,timeout=30,check=True)
accounting = [dict(zip(['job_id','state','exit_code','elapsed_seconds','start','end','allocated_tres'],line.split('|'))) for line in completed.stdout.splitlines() if line.strip()]
main = next(row for row in accounting if row['job_id'] == JOB)
assert main['state'] == 'COMPLETED' and main['exit_code'] == '0:0', main
assert 0 < int(main['elapsed_seconds']) <= 5400
assert 'gres/gpu=1' in main['allocated_tres'] and 'gres/gpu:h200=1' in main['allocated_tres']
assert all(row['state']=='COMPLETED' and row['exit_code']=='0:0' for row in accounting)
audit = {'job_id':JOB,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':SEAL,'qwen_requests':124,'qwen_smoke':4,'qwen_development':120,'qwen_status_counts':status_counts,'input_tokens':input_tokens,'output_tokens':output_tokens,'scheduler_accounting':accounting,'allocation_finished':finish,'request_raw_parse_usage_and_prompt_hashes_verified':True,'frozen_sources_verified':True,'qwen_smoke_verified':True,'ready_for_jev_development':True}
audit_path = ROOT/'qwen_collection_audit.json'
with audit_path.open('x') as stream:
    json.dump(audit,stream,indent=2); stream.write('\n')
files = {}
for path in (BUNDLE/'results').rglob('*'):
    if path.is_file(): files[path.relative_to(ROOT).as_posix()] = path
for path in (ROOT/'logs').glob('*.log'):
    files['deployment/cluster_33071622/'+path.name] = path
for name in ['cluster_admission.json','submission_claim.json','submission_receipt.json','qwen_collection_audit.json']:
    files['deployment/cluster_33071622/'+name] = ROOT/name
manifest = {'job_id':JOB,'files':{name:{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for name,path in sorted(files.items())}}
archive = Path.home()/'jev_results_33071622.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as output:
    for name,path in sorted(files.items()): output.write(path,name)
    output.writestr('collection_manifest.json',json.dumps(manifest,indent=2)+'\n')
print(json.dumps(audit),flush=True)
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(files)}),flush=True)
