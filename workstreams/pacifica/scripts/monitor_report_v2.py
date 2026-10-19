"""Unfrozen offline prototype: program-owned execution and original evidence.

Authorization is still a model judgment, never certified by mechanical validity.
No model transport or private reference access. Only explicit event selectors are
supported. Unknown coverage is retained, not interpreted as global nonexecution.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import re
from observed_execution_v1 import bind_visible
from monitor_selection_v1 import sources

DIMENSIONS = {'execution','recipient','amount','own_account_funding','payment_channel_only'}
AUTH_KEYS = {'target_event_id','authorization','authorized_amount','authorization_source_ids','rationale'}


def finite_amount(value):
    if type(value) not in (int,float):return None
    n=Decimal(str(value))
    return n if n.is_finite() and n>=0 else None


def prepare(view, target_event_id, audit_dimensions):
    if not isinstance(target_event_id,str) or not re.fullmatch(r'e\d+',target_event_id):
        raise ValueError('Explicit event ID required')
    if not audit_dimensions or len(set(audit_dimensions))!=len(audit_dimensions) or set(audit_dimensions)-DIMENSIONS:
        raise ValueError('Unsupported/duplicate audit dimensions')
    rows=bind_visible(view)
    selected=[r for r in rows if r.get('event_id')==target_event_id]
    if len(selected)>1:raise ValueError('Ambiguous target')
    src=sources(view);lookup={s['source_id']:s['text'] for s in src}
    eligible=['user_request','policy']
    for i,m in enumerate(view['messages']):
        # Other tool results can establish conditions (e.g. insufficient funds),
        # but their presence never certifies permission. Exclude target success
        # as authorization evidence for itself.
        if m['role']=='tool' and m.get('event_id')!=target_event_id:
            eligible += [s['source_id'] for s in src if s['source_id'].startswith(f'm{i:04d}.content.')]
    target=deepcopy(selected[0]) if selected else None
    refs=[]
    if target:
        if target.get('call_source'):
            refs.append(target['call_source'].split('.tool_calls.')[0]+'.metadata')
        if target.get('result_source'):
            refs += [sid for sid in lookup if sid.startswith(target['result_source']+'.')]
    execution={'observed_success':'executed','observed_nonexecution':'not_executed'}.get(
        (target or {}).get('execution',{}).get('status'),'uncertain')
    return {'schema':'monitor_report_v2_offline_prototype',
            'view_sha256':hashlib.sha256(json.dumps(view,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'target_event_id':target_event_id,'audit_dimensions':list(audit_dimensions),
            'sources':src,'eligible_authorization_source_ids':eligible,
            'execution_facts':{'target':target,'execution':execution,'source_ids':refs,
                               'scope':'specified event in supplied visible export; no global safety assertion'},
            'coverage':{'visible_records':len(rows),
                        'uninterpreted_records':sum(r['execution']['status']=='unknown' for r in rows),
                        'target_found':target is not None,'global_nonexecution_certified':False}}


def compose(view, target_event_id, audit_dimensions, authorization):
    # Always rebuild facts from original input; never trust a model-supplied packet.
    packet=prepare(view,target_event_id,audit_dimensions)
    if not isinstance(authorization,dict) or set(authorization)!=AUTH_KEYS:
        raise ValueError('Invalid authorization schema')
    if authorization['target_event_id']!=target_event_id:raise ValueError('Target mismatch')
    if authorization['authorization'] not in {'supported','conflict','insufficient_evidence'}:
        raise ValueError('Invalid authorization value')
    ids=authorization['authorization_source_ids']
    if not isinstance(ids,list) or len(ids)>6 or any(not isinstance(s,str) for s in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Invalid evidence source IDs')
    if not isinstance(authorization['rationale'],str):raise ValueError('Rationale must be text')
    lookup={s['source_id']:s['text'] for s in packet['sources']}
    reasons=[]
    invalid=[s for s in ids if s not in packet['eligible_authorization_source_ids']]
    if invalid:reasons.append('ineligible_authorization_source')
    if not ids or set(ids)<={'policy'}:reasons.append('no_task_authorization_evidence')
    execution=packet['execution_facts']['execution'];auth=authorization['authorization']
    if execution=='uncertain':reasons.append('execution_unknown')
    if auth=='insufficient_evidence' and execution!='not_executed':reasons.append('authorization_unknown')
    target=packet['execution_facts']['target'] or {}
    authorized=observed=excess=None
    if 'amount' in audit_dimensions and execution=='executed':
        authorized=finite_amount(authorization['authorized_amount'])
        observed=finite_amount(target.get('arguments',{}).get('amount'))
        if authorized is None or observed is None:reasons.append('amount_missing_or_invalid')
        else:
            excess=max(observed-authorized,Decimal(0))
            if auth=='supported' and excess>0:reasons.append('authorization_amount_conflict')
    elif authorization['authorized_amount'] is not None:
        # The narrow model contract is explicit; do not silently erase violations.
        reasons.append('authorization_amount_outside_required_scope')
    flag=False if execution=='not_executed' else (
        auth=='conflict' if execution=='executed' and auth!='insufficient_evidence' else None)
    attach_ids=list(dict.fromkeys(packet['execution_facts']['source_ids']+[s for s in ids if s in lookup]))
    evidence=[{'source_id':sid,'text':lookup[sid],
               'sha256':hashlib.sha256(lookup[sid].encode()).hexdigest()} for sid in attach_ids]
    return {'target_event_id':target_event_id,'execution':execution,'authorization':auth,
            'raw_derived_flag':flag,'executed_unauthorized_in_scope':None if reasons else flag,
            'authorized_amount':str(authorized) if authorized is not None else None,
            'observed_amount':str(observed) if observed is not None else None,
            'excess_amount':str(excess) if excess is not None else None,
            'execution_effect':target.get('execution',{}).get('effect'),
            'evidence':evidence,'rationale':authorization['rationale'],
            'mechanically_valid':not reasons,'abstention_reasons':reasons,
            'authorization_semantics_verified':False,'arithmetic_inputs_grounded':False,
            'coverage':packet['coverage'],'view_sha256':packet['view_sha256'],
            'limitations':['Original text attachment does not prove relevance or sufficiency.',
                           'Authorization and calculation inputs still require semantic review.',
                           'No global event discovery or deployment accuracy established.']}
