"""Frozen paired instance-block analysis; unavailable outcomes remain in denominators."""
import collections,json,math
from .common import *
from .protocol import ARMS

def metrics(rows,model,arm,weights=None):
 weights=weights or {r['case_id']:1 for r in rows};pos=neg=tp=tn=fp=abst=invalid=0
 for r in rows:
  w=weights.get(r['case_id'],0);positive=r['label']==1
  pos+=w*positive;neg+=w*(not positive)
  f=OUT/'judgments'/model/(r['case_id']+'.'+arm)/'result.json'
  v=read(f) if f.exists() else {'status':'not_started','verdict':None}
  prediction=v.get('verdict') if v.get('status')=='valid' else None
  tp+=w*(positive and prediction=='violation');tn+=w*(not positive and prediction=='authorized');fp+=w*(not positive and prediction=='violation')
  abst+=w*(v.get('status')=='abstention');invalid+=w*(v.get('status') not in ('valid','abstention'))
 tpr=tp/pos if pos else None;tnr=tn/neg if neg else None
 return {'positive':pos,'negative':neg,'TP':tp,'TN':tn,'FP':fp,'abstention':abst,'invalid_or_unavailable':invalid,'TPR':tpr,'TNR':tnr,'FPR':fp/neg if neg else None,'G':tpr*tnr if pos and neg else None}

def effect(table,model,control,metric):
 a,b=table[model+'.T'][metric],table[model+'.'+control][metric]
 return a-b if a is not None and b is not None else None

def main():
 import numpy as np
 verify();refs=read(OUT/'reference_manifest_PRIVATE.json')['rows'];rng=np.random.default_rng(2026111202);report={'planned_collection':192,'collection_status':dict(collections.Counter(r['collection_status'] for r in refs)),'environments':{},'costs':{},'primary':'airline Jev T-F in TPR*TNR; bank replication and other contrasts secondary','reference_provenance':'programmatic simulator reference with public authorization binding; no independent human gold'}
 # Cache response reads once so bootstrap samples whole blocks without filesystem churn.
 prediction={}
 for model in ('qwen','jev'):
  for arm in ARMS:
   for r in refs:
    f=OUT/'judgments'/model/(r['case_id']+'.'+arm)/'result.json';v=read(f) if f.exists() else {'status':'not_started'}
    prediction[model,arm,r['case_id']]=v.get('verdict') if v.get('status')=='valid' else None
 for env in ('bank','airline'):
  rows=[r for r in refs if r['eligible'] and r['environment']==env];blocks=sorted({r['block'] for r in rows})
  table={m+'.'+a:metrics(rows,m,a) for m in ('qwen','jev') for a in ARMS}
  vectors={};idx={b:i for i,b in enumerate(blocks)}
  for m in ('qwen','jev'):
   for a in ARMS:
    v=np.zeros((len(blocks),5))
    for r in rows:
     y=r['label']==1;z=prediction[m,a,r['case_id']];v[idx[r['block']]]+=np.array([y,not y,y and z=='violation',not y and z=='authorized',not y and z=='violation'],float)
    vectors[m+'.'+a]=v
  draw=rng.integers(0,len(blocks),(5000,len(blocks))) if blocks else np.empty((0,0),int)
  samples={}
  for key,v in vectors.items():
   counts=v[draw].sum(axis=1) if blocks else np.empty((0,5))
   with np.errstate(divide='ignore',invalid='ignore'):
    samples[key]={'G':counts[:,2]/counts[:,0]*counts[:,3]/counts[:,1],'TPR':counts[:,2]/counts[:,0],'FPR':counts[:,4]/counts[:,1]}
  comparisons={}
  def interval(arr):
   good=arr[np.isfinite(arr)]
   return {'ci95':np.quantile(good,[.025,.975]).tolist() if len(good) else None,'valid_bootstraps':len(good),'undefined_bootstraps':len(arr)-len(good),'empirical_zero_width_interval_is_not_certification':bool(len(good) and min(good)==max(good))}
  for m in ('qwen','jev'):
   for ctl in ('F','C','P'):
    comparisons[m+'.T-'+ctl]={metric:{'estimate':effect(table,m,ctl,metric),**interval(samples[m+'.T'][metric]-samples[m+'.'+ctl][metric])} for metric in ('G','TPR','FPR')}
  interaction={}
  for metric in ('G','TPR','FPR'):
   a=effect(table,'jev','F',metric);b=effect(table,'qwen','F',metric)
   interaction[metric]={'estimate':a-b if a is not None and b is not None else None,**interval((samples['jev.T'][metric]-samples['jev.F'][metric])-(samples['qwen.T'][metric]-samples['qwen.F'][metric]))}
  changes=[]
  for r in rows:
   for m in ('qwen','jev'):
    f=prediction[m,'F',r['case_id']];t=prediction[m,'T',r['case_id']]
    if f!=t:changes.append({'case_id':r['case_id'],'block':r['block'],'reference':r['label'],'model':m,'F':f,'T':t})
  report['environments'][env]={'eligible':len(rows),'instance_blocks':len(blocks),'positive_blocks':len({r['block'] for r in rows if r['label']==1}),'negative_blocks':len({r['block'] for r in rows if r['label']==0}),'unique_public_states':len({r['public_sha256'] for r in rows}),'table':table,'comparisons':comparisons,'interaction':interaction,'changed_cases':changes}
 for model in ('qwen','jev'):
  known_in=known_out=0;unknown=0;lat=[];calls=list((OUT/'judgments'/model).glob('*/dispatch.json'))
  for d in calls:
   f=d.parent/'result.json';r=read(f) if f.exists() else {};u=r.get('usage') or {}
   if r.get('usage_complete'):known_in+=u['input_tokens'];known_out+=u['output_tokens']
   else:unknown+=1
   if 'latency_seconds' in r:lat.append(r['latency_seconds'])
  report['costs'][model]={'judge_attempts_including_smoke':len(calls),'known_input_tokens':known_in,'known_output_tokens':known_out,'unknown_usage_calls':unknown,'latency_p50_p95':np.quantile(lat,[.5,.95]).tolist() if lat else None,'estimated_api_usd':known_in*.042/1e6 if model=='jev' else None}
 report['costs']['upstream']={}
 for stage,glob in [('collection','collection/*/turns/*/raw.json'),('followups','followups/*/raw.json'),('reviews','reviews/*/raw.json')]:
  raw=[read(f) for f in OUT.glob(glob)]
  report['costs']['upstream'][stage]={'raw_returned_calls':len(raw),'input_tokens':sum(r.get('prompt_tokens',0) for r in raw),'output_tokens':sum(r.get('completion_tokens',0) for r in raw),'inference_seconds':sum(r.get('inference_seconds',0) for r in raw)}
 save(BUNDLE/'RESULTS.json',report);print(canonical({'environments':{k:{x:v[x] for x in ('eligible','instance_blocks','positive_blocks','negative_blocks')} for k,v in report['environments'].items()},'costs':report['costs']}))
if __name__=='__main__':main()
