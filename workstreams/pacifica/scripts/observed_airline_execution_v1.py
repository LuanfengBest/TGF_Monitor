"""Narrow contracts from pinned MonitorBench tool code; visible input only.

Offline prototype. Generic errors can follow partial effects and stay unknown.
No authorization inference, pricing oracle, or hidden task reference is consumed.
"""
from copy import deepcopy
from datetime import datetime,timedelta
from decimal import Decimal
import re
from observed_execution_v1 import bind_visible

TOOLS={'buy_flight_ticket','cancel_flight_booking','reserve_restaurant'}

def decode_contract(tool,args,result):
    out={'status':'unknown','effect':'named_operation_only','scope':'named operation; no authorization conclusion'}
    if not isinstance(args,dict) or not isinstance(result,str):return out
    if tool in {'buy_flight_ticket','cancel_flight_booking'}:
        flight=args.get('flight_number');name=args.get('name_on_ticket')
        if not isinstance(flight,str) or not isinstance(name,str):return out
        if result==f'Flight {flight} not found':out['status']='observed_nonexecution';return out
    if tool=='buy_flight_ticket':
        out['effect']='ticket_created'
        loyalty=args.get('loyalty_number');upgrades=args.get('upgrades') or []
        if loyalty is not None and not isinstance(loyalty,str):return out
        if not isinstance(upgrades,list) or any(not isinstance(u,str) for u in upgrades):return out
        suffix=f' using loyalty number {loyalty}' if loyalty is not None else ''
        if upgrades:suffix+=f' with {len(upgrades)} upgrades'
        pat=(re.escape(f'Flight ticket {flight} (confirmation: ')+r'([A-F0-9]{6})'+
             re.escape(f') bought successfully for {name}'+suffix+'. Total cost: $')+
             r'([0-9]+\.[0-9]{2})'+re.escape('. Confirmation email sent.'))
        m=re.fullmatch(pat,result)
        if m:
            out.update(status='observed_success',confirmation_number=m[1],reported_total_cost=str(Decimal(m[2])))
        elif loyalty is not None and re.fullmatch(re.escape(f'Loyalty number {loyalty} not found for {name} on ')+r'.+',result):
            out['status']='observed_nonexecution'
        # Invalid upgrade messages and generic errors remain unknown unless a
        # future contract checks their exact validated argument list.
    elif tool=='cancel_flight_booking':
        out['effect']='ticket_cancelled_not_erasure_of_prior_booking'
        confirmation=args.get('confirmation_number')
        if not isinstance(confirmation,str):return out
        if result==f'Flight booking {flight} for {name} has been successfully cancelled. Confirmation email sent.':
            out['status']='observed_success'
        elif result in (f'No booking found with confirmation number {confirmation}',
                        'Ticket details do not match the provided confirmation number'):
            out['status']='observed_nonexecution'
    elif tool=='reserve_restaurant':
        out['effect']='reservation_written_not_service_consumed'
        restaurant=args.get('restaurant');start=args.get('start_time');party=args.get('party_size')
        if not isinstance(restaurant,str) or not isinstance(start,str) or type(party)!=int:return out
        if result==f'Restaurant {restaurant} not found':out['status']='observed_nonexecution';return out
        try:dt=datetime.fromisoformat(start)
        except ValueError:return out
        expected=f'Reservation for {restaurant} from {dt:%H:%M} to {dt+timedelta(hours=2):%H:%M} on {dt.date().isoformat()} has been made successfully.'
        if result==expected:out['status']='observed_success'
    return out


def bind_visible_with_airline(view):
    rows=deepcopy(bind_visible(view))
    for r in rows:
        if r.get('tool_name') in TOOLS and r.get('binding') in {'explicit_call_id','single_call_serial'}:
            r['execution']=decode_contract(r['tool_name'],r['arguments'],r['result_text'])
    return rows
