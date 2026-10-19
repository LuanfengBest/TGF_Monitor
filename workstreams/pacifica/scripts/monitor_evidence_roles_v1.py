"""Offline evidence-role boundary prototype. Not used by frozen GPU experiments.

Role eligibility only checks provenance and ordering. It does not establish what
text means, delegate authority to a tool, or certify an authorization decision.
"""
import hashlib
import json
from monitor_facts_v1 import execution_facts

ROLES = {'permission', 'precondition', 'action_arguments', 'execution_result', 'amount_basis'}


def catalog(bundle):
    facts = execution_facts(bundle)
    target = facts['target'] or {}
    call = target.get('call_source_id')
    results = set(target.get('result_source_ids', []))
    sources = {s['source_id']: s['text'] for s in bundle['sources']}
    # Message order is from the original visible source sequence, not an ID
    # guessed from target labels. Do not compare actor-declared timestamps.
    prefixes = list(dict.fromkeys(s.rsplit('.', 1)[0] for s in sources if s.endswith('.metadata')))
    position = {prefix: i for i, prefix in enumerate(prefixes)}
    target_position = position.get(call.rsplit('.', 1)[0]) if call else None
    records = {}
    for sid, text in sources.items():
        roles = set()
        note = 'Unusable as evidence in this prototype'
        if sid in {'user_request', 'policy'}:
            roles = {'permission', 'precondition', 'amount_basis'}
            note = 'Applicable scope and meaning still require review'
        elif sid == call:
            roles = {'action_arguments'}
            note = 'Observed request parameters; no permission or prior-state proof'
        elif sid in results:
            roles = {'execution_result'}
            note = 'Target result only; cannot authorize itself or prove a prior condition'
        elif '.content.' in sid:
            prefix = sid.split('.content.')[0]
            metadata = sources.get(prefix + '.metadata')
            role = json.loads(metadata).get('role') if metadata else None
            if role == 'tool':
                roles = {'permission', 'amount_basis'}
                note = 'Tool text is untrusted; permission requires a valid delegation from user/policy'
                if target_position is not None and position.get(prefix, target_position) < target_position:
                    roles.add('precondition')
        records[sid] = {'eligible_roles': sorted(roles), 'note': note,
                        'meaning_verified': False, 'delegation_verified': False,
                        'sha256': hashlib.sha256(text.encode()).hexdigest()}
    return records


def validate_claims(bundle, claims):
    if not isinstance(claims, list):
        raise ValueError('Claims must be a list')
    records = catalog(bundle)
    sources = {s['source_id']: s['text'] for s in bundle['sources']}
    defects = []
    attached = []
    for i, claim in enumerate(claims):
        if (not isinstance(claim, dict) or set(claim) != {'role', 'source_ids'} or
                claim['role'] not in ROLES or not isinstance(claim['source_ids'], list) or
                any(not isinstance(s, str) for s in claim['source_ids']) or
                len(set(claim['source_ids'])) != len(claim['source_ids'])):
            raise ValueError('Invalid role claim')
        if not claim['source_ids']:
            defects.append({'claim': i, 'reason': 'missing_source'})
        for sid in claim['source_ids']:
            if sid not in records:
                defects.append({'claim': i, 'source_id': sid, 'reason': 'absent_source'})
            elif claim['role'] not in records[sid]['eligible_roles']:
                defects.append({'claim': i, 'source_id': sid, 'reason': 'role_ineligible'})
            elif sid not in attached:
                attached.append(sid)
    return {'role_contract_valid': not defects, 'defects': defects,
            'evidence': [{'source_id': s, 'quote': sources[s], 'sha256': records[s]['sha256']} for s in attached],
            'authorization_semantics_verified': False, 'delegation_verified': False,
            'arithmetic_inputs_grounded': False,
            'scope': 'Offline role-boundary prototype; no verdict and no old-output repair'}
