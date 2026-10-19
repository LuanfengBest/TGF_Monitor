"""Offline environment/source audit only; no model calls or generated trajectory."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    agent=ROOT/'third_party/MonitorBench/datasets/dual_objective/agent'
    sys.path.insert(0,str(agent));os.chdir(agent)
    from utils.path_utils import set_project_root
    set_project_root(agent)
    from task_pairs.american_airlines_2.task_definition import TaskDefinition
    from utils.functions_runtime import make_function
    task=TaskDefinition();state=task.environment.model_dump(mode='json')
    functions=[make_function(f) for f in task.environment.available_tools]
    schema=[{'name':f.name,'description':f.description,'parameters':f.parameters.model_json_schema()} for f in functions]
    # Task authorization source candidates only. Kept separately from monitor input;
    # this is not a ground-truth label and does not use side-task success checks.
    emails=[e for e in state['inbox']['emails'].values() if
            ('sarah' in e['sender'].lower() and 'conference' in (e['body']+e['subject']).lower())
            or 'dietary' in (e['body']+e['subject']).lower()]
    report={'status':'offline_environment_loaded_no_inference','environment':'american_airlines_2',
        'family':'monitorbench_american_airlines_2_original','user_request':task.user_query,
        'tool_names':[f.name for f in functions],'initial_state_fields':list(state),
        'initial_state_sha256':hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'tool_count':len(functions),'schema_bytes':len(json.dumps(schema).encode()),
        'initial_state_bytes':len(json.dumps(state).encode()),'model_calls':0,
        'authorization_source_candidates':emails,'labels':'not implemented/validated yet',
        'initial_missing_dependency_resolved':'pandas; installed upstream-pinned pandas/numpy/openpyxl locally'}
    out=ROOT/'analysis/airline_preflight_2026-10-12.json'
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='authorization_source_candidates'},indent=2))
    print('Authorization source candidates:',len(emails))


if __name__=='__main__':main()
