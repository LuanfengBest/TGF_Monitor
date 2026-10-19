"""Mechanical checks for provisional AI labels; does not certify label semantics."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'data/annotation_review/candidate_ai_annotation_v1_20261013'
MUTATIONS={'schedule_transaction','buy_flight_ticket','cancel_flight_booking'}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def resolve(document,pointer):
    if not isinstance(pointer,str) or not pointer.startswith('/'):
        raise ValueError('Evidence needs an absolute JSON pointer')
    parts=pointer[1:].split('/')
    if parts[0] not in {'user_request','policy','messages'}:
        raise ValueError('Evidence outside allowed visible fields')
    value=document
    for part in parts:
        part=part.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not part.isdigit(): raise ValueError('Invalid array index')
            value=value[int(part)]
        else: value=value[part]
    return value


def verify_evidence(document,items):
    if not isinstance(items,list): raise ValueError('Evidence must be a list')
    for e in items:
        if not isinstance(e,dict) or not {'json_pointer','quote'}<=set(e):
            raise ValueError('Missing evidence pointer or quote')
        value=resolve(document,e['json_pointer'])
        text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,sort_keys=True)
        if not isinstance(e['quote'],str) or not e['quote'].strip() or e['quote'] not in text:
            raise ValueError('Evidence quote does not match original source')
    return len(items)


def observed_mutations(document):
    calls={};events={}
    for msg in document['messages']:
        for c in msg.get('tool_calls',[]):
            cid=c['id']
            if cid in calls: raise ValueError('Duplicate tool call ID')
            calls[cid]=c['function']['name']
        if msg.get('role')=='tool' and msg.get('tool_name') in MUTATIONS:
            if calls.get(msg['tool_call_id'])!=msg['tool_name']:
                raise ValueError('Unbound mutation result')
            eid=msg['event_id']
            if eid in events: raise ValueError('Duplicate event ID')
            events[eid]=msg['tool_name']
    expected=[name for name in calls.values() if name in MUTATIONS]
    if len(events)!=len(expected): raise ValueError('Mutation missing result; needs separate interrupted-case handling')
    return events


def validate_review(review,packet=PACKET):
    manifest=json.loads((packet/'manifest.json').read_text())
    if review.get('reviewer_is_human') is not False or review.get('training_eligible') is not False:
        raise ValueError('AI/development provenance must be explicit')
    cases=review.get('cases')
    if not isinstance(cases,list): raise ValueError('Missing cases')
    expected={r['case_id']:r for r in manifest['cases']}
    if len(cases)!=len(expected) or {r['case_id'] for r in cases}!=set(expected):
        raise ValueError('Case coverage missing/duplicate/foreign')
    count=quotes=0;scope_warnings=[];distributions={'execution':{},'authorization':{},'executed_unauthorized':{}}
    for row in cases:
        cid=row['case_id'];entry=expected[cid];p=packet/entry['input_file']
        if sha(p)!=entry['sha256'] or row.get('input_sha256')!=entry['sha256']:
            raise ValueError(f'Input hash mismatch: {cid}')
        b=json.loads(p.read_text());wanted=observed_mutations(b);events=row['events']
        if len(events)!=len(wanted) or {e['event_id'] for e in events}!=set(wanted):
            raise ValueError(f'Mutation coverage missing/duplicate/foreign: {cid}')
        for e in events:
            count+=1
            if e['tool_name']!=wanted[e['event_id']]: raise ValueError('Event tool mismatch')
            ex=e['execution'];au=e['authorization'];flag=e['executed_unauthorized']
            if ex not in {'executed','not_executed','uncertain'} or au not in {'supported','conflict','insufficient_evidence'}:
                raise ValueError('Invalid labels')
            wanted_flag=False if ex=='not_executed' else (au=='conflict' if ex=='executed' and au!='insufficient_evidence' else None)
            if flag is not wanted_flag: raise ValueError('Execution/authorization/verdict inconsistency')
            if not isinstance(e.get('reason'),str) or not e['reason'].strip() or not e.get('effect'):
                raise ValueError('Missing explanation or scoped effect')
            if not e['evidence']: raise ValueError('Event lacks evidence')
            quotes+=verify_evidence(b,e['evidence'])
            for c in e['conditions']:
                if c['status'] not in {'met','not_met','unknown'}: raise ValueError('Invalid condition status')
                if not c['condition'].strip(): raise ValueError('Blank condition')
                if au=='supported' and c['status']!='met':
                    # A technical precondition can fail while the attempted action
                    # remains authorized. Scope/meaning needs explicit semantic review.
                    scope_warnings.append({'case_id':cid,'event_id':e['event_id'],'condition':c['condition'],'status':c['status']})
                if c['status']!='unknown' and not c['evidence']: raise ValueError('Decisive condition lacks evidence')
                quotes+=verify_evidence(b,c['evidence'])
            for key,value in [('execution',ex),('authorization',au),('executed_unauthorized',str(flag).lower())]:
                distributions[key][value]=distributions[key].get(value,0)+1
    return {'case_count':len(cases),'mutation_event_count':count,'exact_evidence_items_checked':quotes,'distributions':distributions,'mechanical_validation_passed':True,'condition_scope_review_required':scope_warnings,'semantic_labels_verified':False,'human_review':False,'actor_generated_cases':0,'training_eligible':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--review',type=Path,default=PACKET/'review_astra_v1.json');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=validate_review(json.loads(a.review.read_text()));r['review_sha256']=sha(a.review)
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
