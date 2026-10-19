"""Prepare deterministic event views for primary AI review; never derive trace labels."""
from pathlib import Path
import json,re,hashlib
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1]
IN=ROOT/'analysis/tgf_full_handoff_20261018'
OUT=ROOT/'analysis/tgf_full48_authorization_20261018'
def load(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def execution(e):
    t=e['tool'];s=str(e.get('result') or '');err=e.get('error')
    if t=='end_task':return 'terminal'
    if err:return 'failed'
    if s.startswith(('Error','Failed','Invalid tool','ValidationError','Row ')):return 'failed'
    if not e['candidate_state_change']:return 'read'
    if t in ('send_money_venmo','send_money_zelle'):return 'executed' if s.startswith('Successfully sent ') else 'failed' if ('not found' in s or 'Verification' in s) else 'unresolved'
    if t in ('add_venmo_contact','add_zelle_contact'):return 'executed' if s.startswith('Successfully added ') else 'unresolved'
    if t.startswith('transfer_bank_to_'):return 'executed' if s.startswith('Successfully transferred ') else 'unresolved'
    if t=='schedule_transaction':return 'executed' if 'has been scheduled successfully' in s else 'failed' if 'not scheduled' in s else 'unresolved'
    if t=='buy_flight_ticket':return 'executed' if s.startswith('Flight ticket ') and 'bought successfully for' in s else 'failed' if 'not found' in s or 'Invalid upgrade' in s else 'unresolved'
    if t=='reserve_restaurant':return 'executed' if s.startswith('Reservation for ') and 'made successfully.' in s else 'failed' if 'not found' in s else 'unresolved'
    if t=='send_email':return 'executed' if re.search(r'^status: sent\s*$',s,re.M) else 'unresolved'
    if t in ('append_to_file','create_file'):return 'executed' if 'id_:' in s and 'content:' in s else 'unresolved'
    prefixes={'create_sheet':'Sheet ','add_multiple_columns':'Added columns:','add_multiple_rows':'Added rows ','set_cell_value':'Set value '}
    if t in prefixes:return 'executed' if s.startswith(prefixes[t]) else 'unresolved'
    return 'unresolved'
def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'case_views').mkdir()
    index=load(IN/'raw_record_index.jsonl');events=load(IN/'tool_event_index_PRIVATE_REVIEW_ONLY.jsonl');by=defaultdict(list)
    for e in events:by[e['trace_id']].append(e)
    summaries=[];expanded=[];refs={}
    for r in index:
        if r['tool_calls']==0:continue
        tid=r['id'];env=tid.split('/')[0];raw=json.loads((ROOT/r['source_file']).read_text());initial=raw['extra_args']['environment_states'][0];final=raw['environment'];conv=raw['conversation']
        refs.setdefault(env,initial)
        emails=defaultdict(list);files=defaultdict(list)
        for e in by[tid]:
            if not e['candidate_state_change'] and e['tool']!='end_task' and not e.get('error'):
                txt=e.get('result','')
                for id in re.findall(r"(?:^|\n)\s*id_:\s*['\"]?([0-9]+)['\"]?(?:\s|$)",txt):
                    (emails if 'email' in e['tool'] else files)[id].append(e['step'])
        es=[]
        for e in by[tid]:
            x=dict(e,execution_checked=execution(e),event_key=f"{tid}:s{e['step']}:c{e['call_index']}")
            es.append(x);expanded.append(x)
        lines=[f'CASE {tid}',f'RAW {r["source_file"]}',f'PUBLIC EMAIL IDS {dict(emails)}',f'PUBLIC FILE IDS {dict(files)}']
        success=[e for e in es if e['execution_checked']=='executed']
        summary={'id':tid,'all_events':len(es),'execution_counts':dict(Counter(e['execution_checked'] for e in es)),
                 'email_source_steps':dict(emails),'file_source_steps':dict(files),'source_sha256':r['source_sha256'],
                 'state_top_keys_changed':[k for k in initial if initial[k]!=final[k]],'all_events_semantically_reviewed':False}
        if env=='american_airlines_2':
            catalog={f['flight_number']:f for f in initial['flights']['flight_list']};book=[e for e in success if e['tool']=='buy_flight_ticket']
            booked=defaultdict(list)
            for e in book:booked[e['args']['name_on_ticket']].append(e['args']['flight_number'])
            summary['flight_state_matches_successful_call_sequence']=dict(booked)==final['flight_tickets']
            assert summary['flight_state_matches_successful_call_sequence'],tid
            summary['tickets']=len(book);summary['final_reservation']=final['reservation']
            lines.append('BOOKINGS (each entry is a separate successful tool receipt; all sequences agree with final flight_tickets)')
            for name in sorted(booked):
                seq=[e for e in book if e['args']['name_on_ticket']==name]
                lines.append(name+': '+' | '.join(f"s{e['step']} {e['args']['flight_number']} [{catalog[e['args']['flight_number']]['departure_city']}->{catalog[e['args']['flight_number']]['arrival_city']}] loyalty={e['args'].get('loyalty_number')} up={e['args'].get('upgrades')}" for e in seq))
            lines.append('NON-BOOKING MUTATION EVENTS (failed attempts retained)')
            for e in es:
                if e['candidate_state_change'] and e['tool']!='buy_flight_ticket':lines.append(f"s{e['step']} {e['execution_checked']} {e['tool']} {json.dumps(e['args'],ensure_ascii=False)} -> {str(e.get('error') or e.get('result'))[:140]}")
            failed=[e for e in es if e['tool']=='buy_flight_ticket' and e['execution_checked']!='executed']
            lines.append('FAILED BOOKINGS: '+' | '.join(f"s{e['step']} {json.dumps(e['args'],ensure_ascii=False)} -> {e.get('error') or e.get('result')}" for e in failed))
            lines.append('FINAL RESERVATION '+json.dumps(final['reservation'],ensure_ascii=False))
        else:
            lines.append('ALL STATE-CHANGING EVENTS; email args contain full body, other results compact')
            for e in es:
                if e['candidate_state_change']:lines.append(f"s{e['step']} {e['execution_checked']} {e['tool']} {json.dumps(e['args'],ensure_ascii=False)} -> {str(e.get('error') or e.get('result'))[:140]}")
            changes={}
            for service,key in [('bank_account','scheduled_transactions'),('bank_account','transactions'),('venmo','transaction_history'),('zelle','transaction_history')]:
                a,b=initial[service][key],final[service][key];assert b[:len(a)]==a
                changes[service+'.'+key]=b[len(a):]
            contact_changes={svc:{k:v for k,v in final[svc]['contacts'].items() if initial[svc]['contacts'].get(k)!=v} for svc in ['venmo','zelle']}
            summary.update(financial_state_additions=changes,contact_state_changes=contact_changes)
            lines.append('CONTACT CHANGES '+json.dumps(contact_changes,ensure_ascii=False))
        # Initial/final key changes expose mutations outside the extracted action classes.
        lines.append('CHANGED STATE MODULES '+str(summary['state_top_keys_changed']))
        summary['view_file']=str((OUT/'case_views'/f"{tid.replace('/','__')}.txt").relative_to(ROOT))
        (ROOT/summary['view_file']).write_text('\n'.join(lines)+'\n')
        summaries.append(summary)
    for filename,data in [('reference_initial_states_PRIVATE.json',refs),('case_summaries.json',summaries)]:
        (OUT/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'events_with_execution_status.jsonl').open('x') as f:
        for e in expanded:f.write(json.dumps(e,ensure_ascii=False)+'\n')
    print(json.dumps({'cases':len(summaries),'events':len(expanded),'execution':Counter(e['execution_checked'] for e in expanded),'unresolved':[(e['event_key'],e['tool'],str(e.get('error') or e.get('result'))[:100]) for e in expanded if e['execution_checked']=='unresolved']},ensure_ascii=False))
if __name__=='__main__':main()
