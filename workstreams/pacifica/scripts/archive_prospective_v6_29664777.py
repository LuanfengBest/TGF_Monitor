"""One exclusive archive of terminal v6 generation; no inference or source edits."""
import datetime,hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JOB='29664777'

def main():
    run=ROOT/'results'/('prospective_actor_v6_'+JOB)
    receipt=ROOT/'results'/('prospective_v6_'+JOB+'_closeout.json')
    target=ROOT/'results'/('prospective_actor_v6_'+JOB+'_archive.zip')
    archive_receipt=ROOT/'results'/('prospective_v6_'+JOB+'_archive_receipt.json')
    if any(p.exists() for p in (receipt,target,archive_receipt)):
        raise ValueError('An archive attempt already exists; inspect it, never repeat blindly')
    cp=subprocess.run(['sacct','-j',JOB,'--noheader','--parsable2',
        '--format=JobID,State,ExitCode,Start,End,ElapsedRaw,AllocTRES'],text=True,capture_output=True,timeout=20,check=True)
    line=next(x.split('|') for x in cp.stdout.splitlines() if x.startswith(JOB+'|'))
    assert line[1].split()[0] in {'COMPLETED','FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED'},cp.stdout
    queue=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    assert JOB not in queue,'Job still in queue'
    names=['logs/prospective_actor_v6-'+JOB+'.log','results/prospective_actor_v6_preflight.json',
           'results/prospective_actor_v6_submission.json','results/prospective_actor_v6.reservation.json',
           'results/tgf_v3_initial_delivery_remote_20261015.json']
    paths=[p for p in run.rglob('*') if p.is_file()]+[ROOT/n for n in names if (ROOT/n).is_file()]
    assert paths and all(not p.is_symlink() for p in paths)
    closeout={'observed_at':datetime.datetime.now().astimezone().isoformat(),'job_id':JOB,
              'sacct':cp.stdout,'squeue':queue,'missing_optional_files':[n for n in names if not (ROOT/n).is_file()]}
    with receipt.open('x') as f:json.dump(closeout,f,indent=2)
    paths.append(receipt)
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for n in manifest:z.write(ROOT/n,n)
        z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
    out={'archive':str(target.relative_to(ROOT)),'files':len(manifest),'bytes':target.stat().st_size,
         'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),**closeout}
    with archive_receipt.open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps(out),flush=True)

if __name__=='__main__':main()
