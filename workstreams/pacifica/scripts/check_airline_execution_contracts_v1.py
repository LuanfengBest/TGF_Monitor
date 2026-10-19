"""Local CPU-only simulator probe; audit-state hashes never enter model inputs."""
import os,sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from observed_airline_execution_v1 import decode_contract
AGENT=ROOT/'third_party/MonitorBench/datasets/dual_objective/agent'
sys.path.insert(0,str(AGENT))
from utils.path_utils import set_project_root
set_project_root(AGENT)
from task_pairs.american_airlines_2.task_definition import TaskDefinition
from tools.flight_tools import buy_flight_ticket

def main():
    prior=os.getcwd();os.chdir(AGENT)
    try:original=TaskDefinition().environment
    finally:os.chdir(prior)
    rows=[]
    for mode in ['success','invalid_loyalty','mail_error_after_mutation']:
        e=original.model_copy(deep=True);before=e.model_dump(mode='json')
        args={'flight_number':e.flights.flight_list[0].flight_number,'name_on_ticket':'Contract Test Passenger'}
        kwargs={k:getattr(e,k) for k in ['flights','user','flight_tickets','total_spent','inbox','ticket_manager']}
        if mode=='invalid_loyalty':args['loyalty_number']='INVALID_TEST_NUMBER'
        if mode=='mail_error_after_mutation':
            with patch('tools.flight_tools._create_airline_email',side_effect=RuntimeError('simulated mail failure')):
                result=buy_flight_ticket(**kwargs,**args)
        else:result=buy_flight_ticket(**kwargs,**args)
        after=e.model_dump(mode='json')
        rows.append({'mode':mode,'arguments':args,'tool_result':result,'visible_contract':decode_contract('buy_flight_ticket',args,result),
                     'audit_only_changed_state_fields':[k for k in before if before[k]!=after[k]],
                     'audit_only_before_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
                     'audit_only_after_sha256':hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest()})
    paths=['tools/flight_tools.py','tools/restaurant_tools.py']
    report={'scope':'Local simulator contract checks, not actor rollouts or authorization labels','model_calls':0,'training_examples':0,
            'upstream_commit':'b6229e4b8ea9abcec38d61159c9cbd0f577ddf35',
            'source_hashes':{p:hashlib.sha256((AGENT/p).read_bytes()).hexdigest() for p in paths},'probes':rows}
    out=ROOT/'analysis/airline_execution_contract_probe_20261013.json'
    if out.exists():raise ValueError('Probe record exists; preserve it')
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
