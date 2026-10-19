"""Shared public facts from pinned tool contracts; never an authorization oracle."""
from copy import deepcopy
import json
import re
import jsonschema
from public_event_contract_v2 import READS, READ_FLAGS
from paired_protocol import risk
from tgf_evidence_eval_v1 import citation_audit
from observed_execution_v1 import decode_contract as bank_contract
from observed_airline_execution_v1 import decode_contract as airline_contract, TOOLS as AIRLINE_TOOLS

BANK_TOOLS = {'schedule_transaction', 'send_money_zelle', 'send_money_venmo',
              'transfer_bank_to_venmo', 'transfer_bank_to_zelle'}
CONTROL_TOOLS = {'end_task'}


def public_observation(shared, event):
    out = {'event_id': event['event_id'], 'status': 'unresolved', 'effect': None,
           'source_ids': [event['call_source'], event['result_source']],
           'scope': 'reported_by_bound_public_tool_return_not_authorization'}
    ret = shared['original_messages'][event['result_source']]
    if ret.get('source_type') != 'tool_return':
        return out
    tool, args, content = event['tool_name'], event['arguments'], ret.get('content')
    if tool in BANK_TOOLS:
        fact = bank_contract(tool, args, content)
    elif tool in AIRLINE_TOOLS:
        fact = airline_contract(tool, args, content)
    else:
        return out
    states = {'observed_success': 'reported_executed',
              'observed_nonexecution': 'reported_not_executed', 'unknown': 'unresolved'}
    out.update(status=states[fact['status']], effect=fact['effect'])
    return out


def prepare(shared):
    citation_audit(shared, {'evidence': []})
    revised = deepcopy(shared)
    for event in revised['ledger']:
        event['candidate'] = event['tool_name'] not in READS | READ_FLAGS | CONTROL_TOOLS
        event['candidate_note'] = 'question allocation only; original reads/control remain auditable; no authorization verdict implied'
    return revised, [public_observation(revised, e) for e in revised['ledger']]


def select(shared, review, facts):
    # Revalidate public provenance and candidate flags; do not trust caller facts.
    checked, expected = prepare(shared)
    if checked != shared or expected != facts:
        raise ValueError('Observation/candidate facts differ from the public trace')
    candidates = [e for e in shared['ledger'] if e['candidate']]
    if set(review['reviews']) != {e['event_id'] for e in candidates}:
        raise ValueError('Review must cover exact candidate set')
    by_id = {f['event_id']: f for f in facts}
    execution_rank = {'reported_executed': 0, 'unresolved': 1, 'reported_not_executed': 2}
    authority_rank = {'unresolved': 0, 'conflict': 1, 'supported': 2}
    candidates.sort(key=lambda e: (execution_rank[by_id[e['event_id']]['status']],
                    authority_rank[review['reviews'][e['event_id']]['authorization']],
                    risk(e['tool_name']), e['event_id']))
    return deepcopy(candidates[0]) if candidates else None


def parse_public_json(raw, schema):
    match = re.fullmatch(r'```(?:json)?\r?\n([\s\S]*?)\r?\n```', raw.strip())
    normalized = match[1] if match else raw
    obj = json.loads(normalized)
    jsonschema.validate(obj, schema)
    return obj, bool(match)
