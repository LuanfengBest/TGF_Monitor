"""Reduced-tool candidate environment adapters; generation disabled until reviewed.

Uses original simulator implementations and FunctionsRuntime. This does not expose
private probe modes, audit state or reference answers to a model.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
AGENT=ROOT/'third_party/MonitorBench/datasets/dual_objective/agent'
sys.path.insert(0,str(AGENT))
from environments.base_environment import BaseEnvironment
from environment_classes.bank_accounts import BankAccount
from environment_classes.cloud_drive import CloudDrive
from environment_classes.travel_booking import Flights,User
from environment_classes.inbox import Inbox
from environment_classes.ticket import TicketManager
from tools.drive_tools import get_file_by_id
from tools.financial_transfer import get_scheduled_transactions,schedule_transaction
from tools.flight_tools import get_flights_between_locations,buy_flight_ticket,cancel_flight_booking
from utils.functions_runtime import FunctionsRuntime,make_function

DIRECTORIES={'bank_invoice_release':'bank_invoice_release_v1',
             'airline_single_passenger_rebooking':'airline_rebooking_v1'}


class InvoiceEnvironment(BaseEnvironment):
    bank_account:BankAccount
    cloud_drive:CloudDrive

    def model_post_init(self,__context):
        self.add_tools([get_file_by_id,get_scheduled_transactions,schedule_transaction])

    @property
    def environment_type(self):return 'BankInvoiceCandidate'

    @classmethod
    def create(cls):
        state=json.loads((ROOT/'data/task_design/bank_invoice_release_v1/simulator_initial_state.json').read_text())
        return cls(**state)


class RebookingEnvironment(BaseEnvironment):
    flights:Flights
    user:User
    flight_tickets:dict[str,list[str]]
    total_spent:dict
    inbox:Inbox
    ticket_manager:TicketManager

    def model_post_init(self,__context):
        self.add_tools([get_flights_between_locations,buy_flight_ticket,cancel_flight_booking])

    @property
    def environment_type(self):return 'SinglePassengerRebookingCandidate'

    @classmethod
    def create(cls):
        state=json.loads((ROOT/'data/task_design/airline_rebooking_v1/simulator_initial_state.json').read_text())
        return cls(**state)


@dataclass
class Candidate:
    candidate_id:str
    user_request:str
    policy:str
    environment:BaseEnvironment
    runtime:FunctionsRuntime
    schemas:list
    fixture_hashes:dict
    split:object=None
    training_eligible:bool=False


def load_candidate(candidate_id):
    directory=ROOT/'data/task_design'/DIRECTORIES[candidate_id]
    audit=json.loads((directory/'design_audit.json').read_text())
    for name,digest in audit['source_hashes'].items():
        assert hashlib.sha256((AGENT/name).read_bytes()).hexdigest()==digest,name
    task=json.loads((directory/'task.json').read_text())
    env=(InvoiceEnvironment if candidate_id=='bank_invoice_release' else RebookingEnvironment).create()
    functions=[make_function(f) for f in env.available_tools]
    schemas=[{'type':'function','function':{'name':f.name,'description':f.description,'parameters':f.parameters.model_json_schema()}} for f in functions]
    assert {s['function']['name'] for s in schemas}==set(task['tool_subset'])|{'end_task'}
    # task.json and initial state are design assets, not labels. Privileged fields
    # are dependency-injected locally and never appear among public tool parameters.
    for schema in schemas:
        assert not set(schema['function']['parameters'].get('properties',{})) & set(type(env).model_fields)
    hashes={n:hashlib.sha256((directory/n).read_bytes()).hexdigest() for n in ['task.json','simulator_initial_state.json']}
    return Candidate(candidate_id,task['user_request'],task['policy'],env,FunctionsRuntime(functions),schemas,hashes)


def require_generation_ready(candidate, registry):
    # In this revision there is no registered reviewed family. Callers cannot turn
    # a candidate into training data by merely inventing a split string.
    row=registry.get(candidate.candidate_id)
    if not row or not row.get('family_independence_verified') or not row.get('task_semantics_reviewed'):
        raise ValueError('Candidate needs task/family review before actor generation')
    if row.get('split') not in {'development','train','validation','test'}:
        raise ValueError('Family split must be frozen before actor generation')
    if row.get('fixture_hashes')!=candidate.fixture_hashes or not row.get('frozen_at'):
        raise ValueError('Reviewed fixture hashes and split freeze are required')
    if row['split']=='test':
        raise ValueError('These design candidates were exposed during development; not unseen final tests')
    return row['split']
