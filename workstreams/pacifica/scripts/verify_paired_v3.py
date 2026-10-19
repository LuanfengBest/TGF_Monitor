"""Independently reconstruct immutable reused and newly generated paired calls."""
import argparse
import json
from pathlib import Path
import jsonschema
from paired_protocol_v3 import *
from run_paired_v2 import verify_inputs
from ollama_client import save, digest


def frozen_prefix(plan):
    for name, expected in plan['recovery']['prefix_files_sha256'].items():
        if sha_file(ROOT/name) != expected:
            raise ValueError('Reused artifact changed: '+name)
    source = ROOT/plan['recovery']['prefix_directory']
    if read(source/'plan.json') != read(ROOT/plan['recovery']['source_protocol']):
        raise ValueError('Original v2 plan changed')
    if sha_file(ROOT/'tools/ollama_tokenizer/provenance.json') != plan['native_tokenizer_provenance_sha256']:
        raise ValueError('Native tokenizer provenance changed')
    return source


def verify(output=None, prefix_only=False):
    plan = read(PLAN)
    prefix = frozen_prefix(plan)
    output = prefix if prefix_only else Path(output).resolve()
    summary = read(output/'summary.json')
    stage = 'recover' if prefix_only else summary['stage']
    if not prefix_only and (read(output/'plan.json') != plan or summary['status'] != 'completed'):
        raise ValueError('Incomplete run or plan mismatch')
    roots = [prefix] if prefix_only else ([prefix, output] if stage == 'recover' else [output])
    counter, calls = Counter(), []
    for directory in roots:
        for name, expected in read(directory/'source_hashes.json').items():
            if sha_file(ROOT/name) != expected:
                raise ValueError('Runtime source changed: '+name)
        for path in sorted((directory/'calls').glob('*_request.json')):
            stem = str(path)[:-len('_request.json')]
            req, resp, identity, usage = [read(stem+s+'.json') for s in ('_request','_response','_identity','_usage')]
            if resp.get('done_reason') != 'stop' or req['model'] != usage['model']:
                raise ValueError('Incomplete response or model mismatch')
            if identity['endpoint'] == 'generate':
                n = counter.check(req['prompt'], req['options']['num_predict'])
                if n != resp['prompt_eval_count']:
                    raise ValueError('Native tokenizer/backend mismatch')
                if directory != prefix and n != identity['expected_prompt_tokens']:
                    raise ValueError('Recorded native count mismatch')
                jsonschema.validate(json.loads(resp['response']), req['format'])
            else:
                reply_projection(resp)
            calls.append({'request':req,'response':resp,'identity':identity,'usage':usage,'path':str(path.relative_to(ROOT))})

    def monitor(name, system, bundle, schema, cap):
        payload = {'model':MONITOR,'prompt':render_prompt(system,bundle),'raw':True,'stream':False,
            'keep_alive':'15m','options':{'num_ctx':CONTEXT,'num_predict':cap,'seed':42,'temperature':0},'format':schema}
        found = [c for c in calls if c['identity']['name'] == name and c['request'] == payload and c['identity']['endpoint']=='generate']
        if len(found) != 1:
            raise ValueError('Missing, duplicate or altered monitor request: '+name)
        return json.loads(found[0]['response']['response'])

    if stage == 'recover':
        schema = obj_schema({'status':{'type':'string','enum':['ok']}})
        monitor('calibration_short','Return the JSON status ok.',{'test':'Token count calibration.'},schema,32)
        monitor('calibration_full_trace','Return the JSON status ok. The supplied data needs no analysis.',
            read(ROOT/plan['attempts'][0]['shared_path']),schema,32)
    items = plan['attempts'][:1] if stage == 'recover' else plan['attempts'][1:]
    expected_count = 2 if stage == 'recover' else 0
    traces = []
    for item in items:
        original, shared = verify_inputs(item)
        out = output/item['trace_id']
        if read(out/'shared.json') != shared:
            raise ValueError('Shared data changed')
        review = monitor('initial_review',REVIEW_SYSTEM,shared,review_schema(shared),plan['review_output_tokens'])
        if review != read(out/'initial_review.json'):
            raise ValueError('Review changed')
        selected = select_event(shared,review)
        if selected != read(out/'selected_event.json'):
            raise ValueError('Selection changed')
        common = {**shared,'initial_review':review,'selected_event':selected}
        if read(out/'common_judge_evidence.json') != common:
            raise ValueError('Common judge evidence changed')
        expected_count += 4
        questions, replies = {}, {}
        if selected is not None:
            expected_count += 3
            question = monitor('targeted_question',QUESTION_SYSTEM,common,obj_schema({'question':text_schema(600)}),plan['question_output_tokens'])['question']
            questions = {'fixed_b2':FIXED_QUESTION,'tgf':question}
            if questions != read(out/'questions.json'):
                raise ValueError('Question changed')
            for method in ('fixed_b2','tgf'):
                payload = {'model':ACTOR,'messages':actor_branch(original,selected,questions[method]),
                    'think':plan['actor_think'],'stream':False,'keep_alive':'15m','options':{
                    'num_ctx':plan['actor_context'],'num_predict':plan['answer_output_tokens'],
                    'seed':plan['actor_seed'],'temperature':plan['actor_temperature']}}
                found = [c for c in calls if c['identity']['name']==method+'_answer' and c['request']==payload and c['identity']['endpoint']=='chat']
                if len(found)!=1:
                    raise ValueError('Actor branch changed')
                replies[method] = reply_projection(found[0]['response'])
                if replies[method] != read(out/f'{method}_reply.json'):
                    raise ValueError('Actor reply projection changed')
        scores = {}
        for method in ('ledger_only','fixed_b2','tgf'):
            if prefix_only and method=='tgf':
                if any(c['identity']['name']=='tgf_judge' for c in calls):
                    raise ValueError('Recovery would repeat an existing judge')
                expected_count -= 1
                continue
            followup = None if method=='ledger_only' or selected is None else {'question':questions[method],'reply':replies[method]}
            bundle = {**common,'followup':followup}
            if read(out/f'{method}_judge_input.json') != bundle:
                raise ValueError('Judge evidence changed')
            judgment = monitor(method+'_judge',JUDGE_SYSTEM,bundle,judge_schema(shared),plan['judge_output_tokens'])
            result_path = out/f'{method}_result.json'
            if (not prefix_only or result_path.exists()) and read(result_path)['judgment'] != judgment:
                raise ValueError('Saved judgment differs from raw response')
            scores[method] = judgment['unauthorized_action_score']
        traces.append({'trace_id':item['trace_id'],'selected_event':selected,'scores':scores})
    if len(calls) != expected_count:
        raise ValueError('Missing or extra inference calls')
    if not prefix_only:
        expected_new = len(calls) - (8 if stage=='recover' else 0)
        if summary['calls'] != expected_new or [a['trace_id'] for a in summary['attempts']] != [i['trace_id'] for i in items]:
            raise ValueError('Summary does not account for actual calls/attempts')
        if any(a['status']!='completed' for a in summary['attempts']):
            raise ValueError('Trace incomplete')
    report = {'passed':True,'prefix_only':prefix_only,'plan_sha256':digest(plan),'stage':stage,
        'calls_including_reused':len(calls),'new_calls':0 if prefix_only else summary['calls'],
        'call_request_paths':[c['path'] for c in calls],'traces':traces,
        'checks':['frozen source/trace hashes','exact reconstructed payloads and schemas','independent tool-disabled actor branches',
            'raw response derivation','native tokenizer/backend counts and capacity','no reference labels in monitor payload'],
        'semantic_correctness':'not established by structural verification'}
    if not prefix_only:
        save(output/'offline_verification.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--prefix-only',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.output,a.prefix_only),indent=2))
