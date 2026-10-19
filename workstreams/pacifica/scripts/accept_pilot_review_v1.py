"""Accept an actually completed AI event review; never fill labels or human signatures."""
import argparse
import json
from pathlib import Path
from pilot_collection_v1 import ROOT, PLAN, actor, batch_path, create, now
from pilot_review_packet_v1 import validate_case, select_balanced


def accept(batch, packet, review_path):
    packet=Path(packet).resolve(); review_path=Path(review_path).resolve()
    manifest=actor.read(packet/'manifest.json'); review=actor.read(review_path)
    if manifest['calibration_only'] or manifest['batch']!=batch or manifest['planned_attempts']!=30:
        raise ValueError('Only the exact new collection batch can be accepted')
    if manifest['technical_complete']!=30 or manifest['stage_status']!='completed':
        raise ValueError('Incomplete batch; preserve failure and stop before next submission')
    if review['reviewer_type']!='AI' or review['human_gold'] is not False or review['independent_review'] is not False:
        raise ValueError('Honest AI reviewer provenance required')
    if review['source_hashes']!=manifest['source_hashes']:
        raise ValueError('Review sources differ from packet')
    for name,h in manifest['source_hashes'].items():
        if actor.sha(ROOT/name)!=h: raise ValueError('Original source changed: '+name)
    packet_hashes=actor.read(packet/'PACKET_SHA256.json')
    for name,h in packet_hashes.items():
        if actor.sha(packet/name)!=h: raise ValueError('Frozen packet changed: '+name)
    if [r['case_id'] for r in review['cases']]!=[c['case_id'] for c in manifest['cases']]:
        raise ValueError('Every planned case must be reviewed exactly once')
    identities=actor.read(packet/'private_reference/identity_mapping.json')
    rows=[]
    for case,assessment,identity in zip(manifest['cases'],review['cases'],identities):
        if case['case_id']!=identity['case_id']: raise ValueError('Identity mapping changed')
        facts=actor.read(packet/'private_reference'/case['case_id']/'event_facts.json')
        view=actor.read(packet/case['public_path'])
        if actor.sha(packet/case['public_path'])!=case['trace_sha256'] or actor.sha(packet/'private_reference'/case['case_id']/'event_facts.json')!=case['facts_sha256']:
            raise ValueError('Evidence binding changed')
        row=validate_case(case,assessment,facts,view)
        row.update(attempt_id=identity['attempt_id'],condition_not_label=identity['condition_not_label'],
                   packet=str(packet.relative_to(ROOT)),review_path=str(review_path.relative_to(ROOT)))
        rows.append(row)
    expected=[a['attempt_id'] for a in actor.read(PLAN)['attempts'] if a['batch']==batch]
    if [r['attempt_id'] for r in rows]!=expected: raise ValueError('Batch sampling order changed')
    archive_path=batch_path(batch,'archive_receipt'); archive=actor.read(archive_path)
    archived=ROOT/archive['archive']
    if actor.sha(archived)!=archive['sha256']: raise ValueError('Archive must be recovered and hash-verified')
    job=archive['job_id']; sacct=next(x.split('|') for x in archive['sacct'].splitlines() if x.startswith(job+'|'))
    if sacct[1]!='COMPLETED' or sacct[2]!='0:0': raise ValueError('Non-successful job cannot advance')
    all_rows=[]; source_paths=[packet/'manifest.json',packet/'PACKET_SHA256.json',review_path,archive_path,
        ROOT/'scripts/accept_pilot_review_v1.py',ROOT/'scripts/pilot_review_packet_v1.py',PLAN]
    if batch>1:
        previous_path=batch_path(batch-1,'review_acceptance'); previous=actor.read(previous_path)
        if not previous['full_review_complete'] or previous['target_reached']:
            raise ValueError('Invalid previous campaign state')
        all_rows.extend(previous['all_reviewed_rows']);source_paths.append(previous_path)
    all_rows.extend(rows)
    coverage=select_balanced(all_rows)
    sample=[]
    if coverage['target_reached']:
        # Six positives and six negatives per domain, with at least three hard negatives.
        for family in ['bank_transfer_2','american_airlines_2']:
            group=sorted([r for r in coverage['selected'] if r['family']==family],key=lambda r:(r['trace_sha256'],r['attempt_id']))
            positives=[r for r in group if r['label']==1][:6]
            negatives=[r for r in group if r['label']==0]
            hard=[r for r in negatives if r['hard_negative']][:3]
            selected_ids={r['attempt_id'] for r in hard}
            sample.extend(positives+hard+[r for r in negatives if r['attempt_id'] not in selected_ids][:3])
    receipt={'accepted_at':now(),'plan_sha256':actor.sha(PLAN),'batch':batch,
        'full_review_complete':True,'technical_batch_complete':True,'target_reached':coverage['target_reached'],
        'reviewer_type':'AI','human_gold':False,'independent_review':False,'human_review_status':'not_performed',
        'all_reviewed_rows':all_rows,'coverage':coverage,'team_sample':sample,
        'remaining_batch_slots':8-batch,'new_model_calls':0,
        'source_hashes':{str(p.relative_to(ROOT)):actor.sha(p) for p in source_paths}}
    create(batch_path(batch,'review_acceptance'),receipt)
    print(json.dumps({k:receipt[k] for k in ['batch','full_review_complete','target_reached','remaining_batch_slots']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',type=int,required=True);p.add_argument('--packet',type=Path,required=True);p.add_argument('--review',type=Path,required=True)
    a=p.parse_args();accept(a.batch,a.packet,a.review)
