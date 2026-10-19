"""Audit the frozen 44-event extension using the unchanged public-only checker."""
import argparse,json
from datetime import datetime
from pathlib import Path
import tgf_sft_qualification_audit_v1 as q
import tgf_sft_train_extension_v1 as ext
ROOT=q.ROOT;DATA=ext.OUT;OUT=ROOT/'data/training/tgf_sft_train_extension_v1';PLAN=ROOT/'configs/tgf_sft_train_extension_audit_v1.json'
def run(mode):
 if mode=='freeze':
  ext.verify();paths=set(q.sources())|set(ext.verify()['source_hashes'])|{'scripts/tgf_sft_train_extension_audit_v1.py',str(ext.PLAN.relative_to(ROOT)),str(q.PLAN.relative_to(ROOT))}
  paths|={str(p.relative_to(ROOT)) for p in DATA.glob('*.json')}
  q.pairs.write_new(PLAN,{'source_hashes':{p:q.src.sha(ROOT/p) for p in sorted(paths)},'max_events':44,'model_calls':0,'training_runs':0,'gpu_jobs':0,'frozen_at':datetime.now().astimezone().isoformat()});print('extension audit frozen');return
 plan=q.src.read(PLAN)
 for p,h in plan['source_hashes'].items():
  if q.src.sha(ROOT/p)!=h:raise ValueError('Source changed: '+p)
 rows=[];details=[];encoder=q.pairs.Encoder();lengths={a:[] for a in q.pairs.ARMS}
 for e in q.src.read(DATA/'manifest.json')['events']:
  if e['split']!='train' or e['training_eligible'] is not False or q.src.sha(DATA/e['input_file'])!=e['input_sha256']:raise ValueError('input mismatch')
  p=q.src.read(DATA/e['input_file']);t,d=q.audit(p,e['domain']);raw=q.src.read(DATA/(e['case_id']+'_raw.json'))
  end=next(i for i,m in enumerate(raw['messages']) if m.get('event_id')==e['event_id'])
  causal={k:raw[k] for k in ('user_request','policy')};causal['messages']=raw['messages'][:end+1]
  if not q.src.exact_equal(p,q.src.make_input(causal,e['event_id'])):raise ValueError('causal mismatch')
  row={'input':p,'target':t,'metadata':e|{'label_method':'unchanged_programmatic_public_causal_checks','reviewer_is_human':False,'blind_review':False,'source_manifest_sha256':q.src.sha(DATA/'manifest.json')}}
  aa,bb=q.pairs.paired_rows(row)
  for arm,item in zip(q.pairs.ARMS,(aa,bb)):lengths[arm].append(encoder.encode(item))
  rows.append(row);details.append({'example_id':e['example_id'],**d})
 if len(rows)!=44:raise ValueError('population mismatch')
 old=[json.loads(s) for s in (q.OUT/'candidates.jsonl').read_text().splitlines()]
 if len({q.src.obj_sha(r['input']) for r in old+rows})!=64:raise ValueError('Duplicate canonical input')
 result={'events':44,'total_train_events':64,'input_unique_hashes':64,'training_eligible':False,'semantic_review_pending':True,
         'label_counts':{str(v):sum(r['target']['executed_unauthorized'] is v for r in rows) for v in (True,False,None)},
         'total_train_label_counts':{str(v):sum(r['target']['executed_unauthorized'] is v for r in old+rows) for v in (True,False,None)},
         'plan_sha256':q.src.sha(PLAN),'token_summary':{a:{'answer_total':sum(r['answer_tokens'] for r in ls),'sequence_total':sum(r['sequence_tokens'] for r in ls),'max_sequence':max(r['sequence_tokens'] for r in ls)} for a,ls in lengths.items()}}
 if mode=='export':
  OUT.mkdir(parents=True,exist_ok=False)
  q.pairs.write_new(OUT/'manifest.json',result);q.pairs.write_new(OUT/'public_audit_details.json',details)
  with (OUT/'candidates.jsonl').open('x') as f:
   for r in rows:f.write(q.src.canonical(r)+'\n')
 else:
  if not q.src.exact_equal(rows,[q.src.strict_json(s) for s in (OUT/'candidates.jsonl').read_text().splitlines()]):raise ValueError('export mismatch')
  if not q.src.exact_equal(result,q.src.read(OUT/'manifest.json')):raise ValueError('manifest mismatch')
 print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','export','verify']);run(p.parse_args().mode)
