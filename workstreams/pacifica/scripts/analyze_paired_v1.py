"""Offline paired case table and transparent cost accounting; no fitted threshold."""
import argparse
import json
from pathlib import Path
from paired_protocol import ROOT, read
from ollama_client import save


def analyze(outputs):
    labels = {r['trace_id']:r for r in read(ROOT/'data/paired_v1/reference_labels_private.json')['traces']}
    traces, calls = [], []
    for output in outputs:
        summary = read(output/'summary.json')
        verification = output/'offline_verification.json'
        verified = verification.exists() and read(verification)['passed']
        for p in sorted((output/'calls').glob('*_usage.json')):
            calls.append(read(p))
        for attempt in summary['attempts']:
            name = attempt['trace_id']; out = output/name
            row = {'trace_id':name, 'status':attempt['status'], 'structurally_verified':verified,
                   'reference':labels[name], 'methods':{}}
            if (out/'selected_event.json').exists():
                row['selected_event']=read(out/'selected_event.json')
            if (out/'questions.json').exists():
                row['questions']=read(out/'questions.json')
            for method in ('ledger_only','fixed_b2','tgf'):
                p=out/f'{method}_result.json'
                if p.exists():row['methods'][method]=read(p)
                p=out/f'{method}_reply.json'
                if p.exists():row[method+'_reply']=read(p)
            traces.append(row)
    by_stage={}
    for c in calls:
        n=c['name']; row=by_stage.setdefault(n,{'calls':0,'input_tokens':0,'output_tokens':0,'request_seconds':0})
        row['calls']+=1;row['input_tokens']+=c.get('prompt_eval_count',0)
        row['output_tokens']+=c.get('eval_count',0);row['request_seconds']+=c['wall_seconds']
    return {'scope':'Frozen single-family development cases, no calibrated detection metrics',
        'traces':traces,'costs_by_stage':by_stage,'actual_calls_with_usage':len(calls),
        'cost_interpretation':'Initial review is shared but belongs in every deployed method cost. Calibration is engineering overhead. TGF additionally pays targeted_question and tgf_answer; B2 pays fixed_b2_answer. No artificial calls added to equalize. GPU allocation tracked separately.',
        'limitations':['Tiny development set; label sample review pending; two labels unresolved.',
            'B3 budget control not yet run; historical B1 protocol differs.',
            'Reason/source correctness requires original-record review, not schema pass.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outputs',nargs='+',type=Path,required=True)
    p.add_argument('--save',type=Path,required=True)
    a=p.parse_args(); report=analyze(a.outputs);save(a.save,report)
    print(json.dumps({'cases':[{'trace_id':r['trace_id'],'reference_label':r['reference']['reference_label'],
      'scores':{m:v['judgment']['unauthorized_action_score'] for m,v in r['methods'].items()}} for r in report['traces']],
      'calls':report['actual_calls_with_usage']},indent=2))
