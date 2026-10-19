"""Full public trace/ledger with call-ID binding; no execution or label answers.

The legacy paired adapter assumed one assistant call immediately before each result.
This adapter supports batched tool calls without discarding any original message.
Its shared use changes transport bookkeeping, not the frozen question policy.
"""
from copy import deepcopy
from paired_protocol import READ_ONLY


def shared_bundle(view):
    if set(view) != {'user_request','policy','messages'}:
        raise ValueError('Only the public view is accepted')
    if not isinstance(view['messages'],list):
        raise ValueError('Invalid message list')
    allowed={'role','content','thinking','tool_calls','tool_name','event_id','tool_call_id','source_type'}
    calls,returned,event_ids,ledger={},set(),set(),[]
    for i,msg in enumerate(view['messages']):
        if set(msg)-allowed or msg.get('role') not in ('assistant','tool'):
            raise ValueError('Non-public message metadata or role')
        if msg['role']=='assistant':
            for call in msg.get('tool_calls',[]):
                cid=call.get('id');fn=call.get('function',{})
                if set(call)-{'id','function'} or set(fn)-{'index','name','arguments'}:
                    raise ValueError('Non-public call metadata')
                if not isinstance(cid,str) or not cid or cid in calls or not isinstance(fn.get('arguments'),dict):
                    raise ValueError('Missing/duplicate call ID or invalid arguments')
                calls[cid]=(i,fn)
        else:
            cid=msg.get('tool_call_id');eid=msg.get('event_id')
            if cid not in calls or cid in returned or not isinstance(eid,str) or not eid or eid in event_ids:
                raise ValueError('Missing call or duplicate return/event')
            ci,fn=calls[cid]
            if ci>=i or msg.get('tool_name')!=fn.get('name'):
                raise ValueError('Call/result identity mismatch')
            if msg.get('source_type') not in ('tool_return','harness_execution_record'):
                raise ValueError('Unrecognized return provenance')
            returned.add(cid);event_ids.add(eid)
            ledger.append({'event_id':eid,'tool_name':fn['name'],'arguments':deepcopy(fn['arguments']),
                'call_source':f'message_{ci:04d}','result_source':f'message_{i:04d}',
                'candidate':fn['name'] not in READ_ONLY,
                'candidate_note':'potential change/attempt, not proof of execution'})
    if set(calls)-returned:
        raise ValueError('Incomplete call/result view retained separately, not silently dropped')
    return {'user_request':view['user_request'],'policy':view['policy'],
            'original_messages':{f'message_{i:04d}':deepcopy(m) for i,m in enumerate(view['messages'])},
            'ledger':ledger}
