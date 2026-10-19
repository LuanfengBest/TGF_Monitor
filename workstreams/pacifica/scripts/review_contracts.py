"""Offline-prepared stricter output contracts; NOT used in job 29351822.

Required event keys and citation enums narrow syntactic freedom. They do not prove
relevance, authorization, arithmetic, or backend enforcement; a future frozen model
diagnostic is still required. No prompts or existing results are modified here.
"""
from copy import deepcopy
from run_indexed_review import SELECT_SCHEMA, AUDIT_SCHEMA, validate_audits


def selection_contract(records, observed_events):
    record_ids=[r['record_id'] for r in records]
    event_ids=[r['event_id'] for r in observed_events]
    if not record_ids or not event_ids or len(set(record_ids))!=len(record_ids) or len(set(event_ids))!=len(event_ids):
        raise ValueError('Nonempty unique source/event IDs required')
    schema=deepcopy(SELECT_SCHEMA)
    # The frozen run's capped response looped in free-form limitations. This
    # proposed contract uses a bounded category; backend behavior is untested.
    schema['properties']['limitations']={'type':'string','enum':[
        'none','no_relevant_records_in_this_chunk','ambiguous_event_mapping',
        'insufficient_records_for_specific_event','selection_budget_limited']}
    item=schema['properties']['selections']['items']
    item['additionalProperties']=False
    item['properties']['record_id']={'type':'string','enum':record_ids}
    item['properties']['event_ids'].update(minItems=1,maxItems=min(40,len(event_ids)),uniqueItems=True)
    item['properties']['event_ids']['items']={'type':'string','enum':event_ids}
    schema['additionalProperties']=False
    return schema


def audit_contract(bundle):
    targets=[e['event_id'] for e in bundle['target_events']]
    sources=list(dict.fromkeys(r['record_id'] for r in bundle['governing_sources']+bundle['retrieved_records']))
    if not targets or len(set(targets))!=len(targets) or not sources:
        raise ValueError('Unique target events and provided sources required')
    row=deepcopy(AUDIT_SCHEMA['properties']['audits']['items'])
    del row['properties']['event_id'];row['required'].remove('event_id')
    row['properties']['source_ids']['items']={'type':'string','enum':sources}
    row['additionalProperties']=False
    return {'type':'object','properties':{'audits_by_event':{'type':'object',
        'properties':{e:deepcopy(row) for e in targets},'required':targets,
        'additionalProperties':False}},'required':['audits_by_event'],'additionalProperties':False}


def decode_event_map(obj,bundle):
    rows=obj.get('audits_by_event')
    expected=[e['event_id'] for e in bundle['target_events']]
    if set(obj)!={'audits_by_event'} or not isinstance(rows,dict) or set(rows)!=set(expected):
        raise ValueError('Missing or extra event key; no default verdict is inserted')
    required=set(AUDIT_SCHEMA['properties']['audits']['items']['required'])-{'event_id'}
    if any(not isinstance(r,dict) or set(r)!=required for r in rows.values()):
        raise ValueError('Missing or extra audit field')
    return validate_audits({'audits':[{'event_id':e,**rows[e]} for e in expected]},bundle)
