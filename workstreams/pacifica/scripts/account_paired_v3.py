"""Append new v3 inference and Slurm costs; never rebill the reused prefix."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from paired_protocol_v3 import ROOT, read
from ollama_client import save
from summarize_costs import summarize


def account(outputs):
    previous=read(ROOT/'results/costs_total_through_paired_attempts.json')
    combined=deepcopy(previous['by_model']);new_runs=[]
    for output in outputs:
        output=Path(output).resolve()
        job=output.name.rsplit('_',1)[-1]
        stage='recover' if '_recover_' in output.name else 'remaining'
        lines=(ROOT/f'logs/slurm_paired_native_{stage}_{job}.txt').read_text().splitlines()
        fields=next(line.split('|') for line in lines if line.startswith(job+'|'))
        costs=summarize(output)
        for model,values in costs['by_model'].items():
            for key,value in values.items():combined[model][key]=combined[model].get(key,0)+value
        new_runs.append({'directory':str(output.relative_to(ROOT)),'job_id':job,'state':fields[1],
            'exit_code':fields[2],'gpu_seconds':int(fields[3]),'start':fields[4],'end':fields[5],
            'by_model':costs['by_model']})
    new_calls=sum(sum(m['requests'] for m in r['by_model'].values()) for r in new_runs)
    gpu_seconds=sum(r['gpu_seconds'] for r in new_runs)
    return {'previous_snapshot':'results/costs_total_through_paired_attempts.json','new_runs':new_runs,
        'by_model':combined,'new_inference_requests':new_calls,'total_inference_requests':previous['total_inference_requests']+new_calls,
        'new_gpu_seconds':gpu_seconds,'major_gpu_allocations_through_this_run_seconds':previous['major_gpu_allocations_through_this_run_seconds']+gpu_seconds,
        'paired_stage_including_failed_attempts':{'calls':16+new_calls,'gpu_seconds':531+gpu_seconds,
            'maximum_calls':50,'maximum_gpu_seconds':2700},
        'currency_cost_usd':None,
        'note':'New v3 call directories only. The reused v2 prefix and failed v1 attempt were already charged in the previous snapshot. CPU replay/verification is not inference. GPU allocation includes setup, model switching and idle time.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outputs',nargs='+',type=Path,required=True);p.add_argument('--save',type=Path,required=True);a=p.parse_args()
    report=account(a.outputs);save(a.save,report)
    print(json.dumps({k:report[k] for k in ('new_inference_requests','new_gpu_seconds','total_inference_requests','paired_stage_including_failed_attempts')},indent=2))
