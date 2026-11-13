"""One-use deployment admission/submission for the already frozen Jev experiment."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

NAME = 'jev_2x2_20261112_a6559538'
BASE = Path('/nfs/roberts/project/cpsc4880/cpsc4880_rz377')
ROOT = BASE / NAME
BUNDLE = ROOT / 'project/jev_monitor_2x2_2026-11-11'
SEAL = 'a65595380ebfa9fe4a8342c1f906215ec940599573f085d301e7d0478a570b63'
ASSETS = BASE / 'authorization_cpsc4880_20261105_879a8821d635/runtime_assets'
DEPS = BASE / 'new_data_20261105_v1/python_dependencies'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save_once(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def call(argv, timeout=30):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    value = {'argv': argv, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    if result.returncode:
        raise RuntimeError(json.dumps(value))
    return value

def frozen_check():
    assert digest(BUNDLE / 'manifest.json') == SEAL, 'Manifest differs'
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert digest(ROOT / name) == expected, 'Frozen file differs: ' + name
    smoke = json.loads((BUNDLE / 'results/jev_smoke_passed.json').read_text())
    assert smoke['manifest_sha256'] == SEAL and smoke['interface_valid'] == 4
    for rid, expected in smoke['result_hashes'].items():
        assert digest(BUNDLE / 'results' / rid / 'result.json') == expected

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'submit', 'status'])
    parser.add_argument('--archive-sha256')
    args = parser.parse_args()
    assert os.environ.get('USER') == 'cpsc4880_rz377', 'Wrong live account'
    if args.action == 'status':
        submission = json.loads((ROOT / 'submission_receipt.json').read_text())
        job = submission['job_id']
        print(json.dumps(call(['squeue', '-j', job, '-o', '%.18i %.12P %.20j %.8T %.10M %R'])))
        print(json.dumps(call(['sacct', '-j', job, '--parsable2', '--noheader', '--format=JobID,State,ExitCode,Elapsed,AllocTRES'])))
        print(json.dumps({'result_files': len(list((BUNDLE/'results').glob('*/result.json'))), 'qwen_ready': (BUNDLE/'results/qwen_ready.json').exists(), 'qwen_smoke': (BUNDLE/'results/qwen_smoke_passed.json').exists(), 'allocation_finished': json.loads((BUNDLE/'results/allocation_finished.json').read_text()) if (BUNDLE/'results/allocation_finished.json').exists() else None}))
        logs = sorted((ROOT/'logs').glob('*.log'))
        if logs:
            print(logs[-1].read_text(errors='replace')[-6000:])
        return
    if args.action == 'prepare':
        archive = Path.home() / (NAME + '.zip')
        assert args.archive_sha256 and digest(archive) == args.archive_sha256, 'Archive SHA-256 mismatch'
        ROOT.mkdir(exist_ok=False)
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                name = Path(member.filename)
                assert not name.is_absolute() and '..' not in name.parts and name.parts[0] == NAME
                target = ROOT.joinpath(*name.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as output:
                    output.write(source.read(member))
        frozen_check()
        queue = call(['squeue', '-h', '-u', os.environ['USER']])
        assert not queue['stdout'].strip(), 'Existing job requires review'
        associations = call(['sacctmgr', '-nP', 'show', 'assoc', 'where', 'user='+os.environ['USER'], 'format=User,Account,Partition,QOS'])
        assert 'cpsc4880_rz377|cpsc4880|' in associations['stdout'] and 'normal' in associations['stdout']
        image = ASSETS / 'vllm_0.13.0.sif'
        assert image.is_file() and DEPS.is_dir()
        config = json.loads((BUNDLE/'config.json').read_text())
        snapshot = Path(config['qwen']['snapshot'])
        inventory = json.loads((BUNDLE/'qwen_assets.json').read_text())
        for name, expected in inventory['files'].items():
            asset = snapshot/name
            assert asset.is_file() and asset.stat().st_size == expected['bytes'], 'Missing/changed model asset: '+name
        cpu_code = "import json; from pathlib import Path; from jev_monitor_v1 import qwen_native; from prospective_monitoring import native_backend as n; p=Path('project/jev_monitor_2x2_2026-11-11'); c=json.loads((p/'config.json').read_text()); print(json.dumps({'runtime':n.runtime_check(c['qwen']),'snapshot':str(n.snapshot_check(c['qwen']['snapshot'],'monitor'))}))"
        runtime = call(['apptainer','exec','--cleanenv','--bind',str(ROOT)+':'+str(ROOT),'--bind',str(ASSETS)+':'+str(ASSETS)+':ro','--bind',str(DEPS)+':'+str(DEPS)+':ro','--pwd',str(ROOT),'--env','PYTHONPATH='+str(ROOT)+':'+str(DEPS),'--env','HF_HUB_OFFLINE=1','--env','TRANSFORMERS_OFFLINE=1',str(image),'/usr/bin/python3','-c',cpu_code], timeout=120)
        (ROOT/'logs').mkdir()
        admission = call(['sbatch','--test-only','--chdir='+str(ROOT),str(ROOT/'jev_monitor_v1/run.sbatch')])
        receipt = {'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'archive_sha256':args.archive_sha256,'manifest_sha256':SEAL,'user':os.environ['USER'],'queue':queue,'associations':associations,'model_asset_count':len(inventory['files']),'model_asset_sizes_match':True,'runtime':runtime,'scheduler_admission':admission,'gpu_jobs_submitted':0,'model_inference_calls':0}
        save_once(ROOT/'cluster_admission.json', receipt)
        print(json.dumps(receipt),flush=True)
        print('JEV_ADMISSION_PASSED',flush=True)
    else:
        frozen_check()
        receipt = json.loads((ROOT/'cluster_admission.json').read_text())
        assert receipt['manifest_sha256'] == SEAL
        queue = call(['squeue','-h','-u',os.environ['USER']])
        assert not queue['stdout'].strip(), 'Existing job requires review'
        assert not (ROOT/'allocation_once_jev_2x2').exists()
        save_once(ROOT/'submission_claim.json',{'manifest_sha256':SEAL,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        result = call(['sbatch','--parsable','--chdir='+str(ROOT),str(ROOT/'jev_monitor_v1/run.sbatch')])
        job = result['stdout'].strip().split(';')[0]
        assert job.isdigit(), 'Unexpected scheduler response; inspect before any retry'
        submission = {'job_id':job,'manifest_sha256':SEAL,'submission':result,'gpu_count':1,'wall_limit_minutes':90,'account':'cpsc4880','new_actor_calls':0}
        save_once(ROOT/'submission_receipt.json',submission)
        print(json.dumps(submission),flush=True)

if __name__ == '__main__':
    main()
