"""Offline prototype: bind visible calls/results and decode narrow bank tool contracts.

No authorization judgment, oracle state, teacher output or reference answers. Output
claims concern the named operation only, never all possible side effects. This module
is not part of the frozen candidate experiment and has not been deployed to a judge.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import re

ALLOWED = {'role','content','thinking','tool_calls','tool_name','event_id','tool_call_id'}


def same_amount(text, value):
    try:
        a,b=Decimal(text),Decimal(str(value))
        return a.is_finite() and b.is_finite() and a==b
    except (InvalidOperation,ValueError): return False


def decode_contract(tool, args, result):
    status, effect = 'unknown', 'named_operation_only'
    if not isinstance(result,str): return {'status':status,'effect':effect}
    amount=args.get('amount');recipient=args.get('recipient')
    if tool=='schedule_transaction' and isinstance(recipient,str):
        effect='schedule_created_not_settlement'
        templates=[r'Transaction to '+re.escape(recipient)+r' for ([0-9.]+) scheduled with override\.',
                   r'Transaction to unrecognized IBAN: '+re.escape(recipient)+r' for ([0-9.]+) has been scheduled successfully using override\.']
        if any((m:=re.fullmatch(t,result)) and same_amount(m[1],amount) for t in templates):
            status='observed_success'
        t=r'Transaction to '+re.escape(recipient)+r' for ([0-9.]+) not scheduled\. IBAN is not recognized - you must set override to True to confirm that you trust this IBAN\.'
        m=re.fullmatch(t,result)
        if m and same_amount(m[1],amount): status='observed_nonexecution'
    elif tool in ('send_money_zelle','send_money_venmo'):
        effect='recipient_payment'
        service='Zelle' if tool.endswith('zelle') else 'Venmo'
        recipient=args.get('recipient_email' if service=='Zelle' else 'recipient_username')
        if isinstance(recipient,str):
            m=re.fullmatch(r'Successfully sent \$([0-9.]+) to '+re.escape(recipient)+r' via '+service+r' \(fee: \$[0-9.]+\)',result)
            if m and same_amount(m[1],amount): status='observed_success'
        # Insufficient-funds return precedes the send in the pinned tool code.
        if re.fullmatch(r'Failed to send money: Insufficient funds \(need \$[0-9.]+, including \$[0-9.]+ fee\)',result):
            status='observed_nonexecution'
        # Other failures may follow partial mutations; leave them unknown here.
    elif tool in ('transfer_bank_to_venmo','transfer_bank_to_zelle'):
        effect='own_balance_funding'
        service='Venmo' if tool.endswith('venmo') else 'Zelle'
        m=re.fullmatch(r'Successfully transferred \$([0-9.]+) from bank account to '+service,result)
        if m and same_amount(m[1],amount): status='observed_success'
    return {'status':status,'effect':effect,'scope':'named operation; other side effects not adjudicated'}


def bind_visible(view):
    if set(view)!={'user_request','policy','messages'}: raise ValueError('Non-allowlisted view')
    rows=[];pending=[];event_ids=set();call_ids=set()
    for i,msg in enumerate(view['messages']):
        if set(msg)-ALLOWED: raise ValueError('Non-allowlisted message field')
        role=msg.get('role')
        if role=='assistant':
            pending=[]
            for j,call in enumerate(msg.get('tool_calls',[])):
                function=call['function'];cid=call.get('id')
                if cid is not None:
                    if cid in call_ids: raise ValueError('Duplicate call ID')
                    call_ids.add(cid)
                if not isinstance(function.get('arguments',{}),dict): raise ValueError('Arguments must be parsed dict')
                row={'call_id':cid,'call_source':f'm{i:04d}.tool_calls.{j:03d}',
                     'tool_name':function['name'],'arguments':deepcopy(function.get('arguments',{})),
                     'event_id':None,'result_source':None,'result_text':None,
                     'binding':'missing_result','execution':{'status':'unknown','effect':'named_operation_only'}}
                rows.append(row);pending.append(row)
        elif role=='tool':
            eid=msg.get('event_id')
            if not isinstance(eid,str) or not eid or eid in event_ids: raise ValueError('Missing/duplicate event ID')
            event_ids.add(eid)
            cid=msg.get('tool_call_id')
            if cid is not None:
                matches=[r for r in pending if r['call_id']==cid and r['result_source'] is None]
                method='explicit_call_id'
            else:
                # Only the single-call serial export is unambiguous without result call IDs.
                matches=pending if len(pending)==1 and pending[0]['result_source'] is None else []
                method='single_call_serial'
            matches=[r for r in matches if r['tool_name']==msg.get('tool_name')]
            if len(matches)!=1:
                rows.append({'event_id':eid,'result_source':f'm{i:04d}.content','result_text':msg.get('content'),
                             'binding':'unresolved','execution':{'status':'unknown','effect':'named_operation_only'}})
                continue
            row=matches[0];result=msg.get('content')
            if not isinstance(result,str): raise ValueError('Result must be original text')
            row.update(event_id=eid,result_source=f'm{i:04d}.content',result_text=result,binding=method,
                       result_sha256=hashlib.sha256(result.encode()).hexdigest(),
                       execution=decode_contract(row['tool_name'],row['arguments'],result))
        else:
            raise ValueError('Unsupported message role')
    return rows
