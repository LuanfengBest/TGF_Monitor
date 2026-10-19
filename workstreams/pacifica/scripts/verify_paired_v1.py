"""Reconstruct each actual request and branch from frozen inputs, offline."""
import argparse
import json
from pathlib import Path
from ollama_client import save, digest
from paired_protocol import *
from run_paired_v1 import verify_inputs
import jsonschema


def verify(output):
    output = Path(output)
    plan = read(output/'plan.json')
    if plan != read(PLAN):
        raise ValueError('Plan mismatch')
    for name, sha in read(output/'source_hashes.json').items():
        if sha_file(ROOT/name) != sha:
            raise ValueError('Runtime source changed: '+name)
    counter = Counter()
    calls = []
    for p in sorted((output/'calls').glob('*_request.json')):
        stem = str(p)[:-len('_request.json')]
        req, resp, identity, usage = [read(stem+s+'.json') for s in ('_request','_response','_identity','_usage')]
        if req['model'] != usage['model'] or resp.get('done_reason') == 'length':
            raise ValueError('Bad response/model')
        if identity['endpoint'] == 'generate':
            if not req['raw'] or req['model'] != MONITOR:
                raise ValueError('Unexpected monitor transport')
            n = counter.check(req['prompt'], req['options']['num_predict'])
            if n != resp['prompt_eval_count'] or n != identity['expected_prompt_tokens']:
                raise ValueError('Input token mismatch')
            jsonschema.validate(json.loads(resp['response']), req['format'])
        else:
            if 'tools' in req or req['model'] != ACTOR:
                raise ValueError('Unexpected follow-up transport')
            reply_projection(resp)
        calls.append({'request':req, 'response':resp, 'identity':identity, 'usage':usage})
    def unique(name, prompt=None, messages=None):
        found = [c for c in calls if c['identity']['name'] == name and
                 (prompt is None or c['request'].get('prompt') == prompt) and
                 (messages is None or c['request'].get('messages') == messages)]
        if len(found) != 1:
            raise ValueError('Missing/duplicate/mutated call '+name)
        return found[0]
    results = []
    completed = read(output/'summary.json')
    if completed['status'] != 'completed' or completed['calls'] != len(calls):
        raise ValueError('Batch not complete')
    if completed['stage'] == 'first':
        unique('calibration_short', render_prompt('Return the JSON status ok.', {'test':'Token count calibration.'}))
        unique('calibration_full_trace', render_prompt('Return the JSON status ok. The supplied data needs no analysis.',
             read(ROOT/plan['attempts'][0]['shared_path'])))
    expected_calls = 2 if completed['stage'] == 'first' else 0
    for attempt in completed['attempts']:
        name = attempt['trace_id']
        item = next(i for i in plan['attempts'] if i['trace_id'] == name)
        original, shared = verify_inputs(item)
        out = output/name
        review = read(out/'initial_review.json')
        r = unique('initial_review', render_prompt(REVIEW_SYSTEM, shared))
        if json.loads(r['response']['response']) != review:
            raise ValueError('Review not derived from response')
        selected = select_event(shared, review)
        if selected != read(out/'selected_event.json'):
            raise ValueError('Selection rule mismatch')
        common = {**shared, 'initial_review':review, 'selected_event':selected}
        expected_calls += 4
        questions, replies = {}, {}
        if selected is not None:
            expected_calls += 3
            questions = read(out/'questions.json')
            q = unique('targeted_question', render_prompt(QUESTION_SYSTEM, common))
            if questions != {'fixed_b2':FIXED_QUESTION, 'tgf':json.loads(q['response']['response'])['question']}:
                raise ValueError('Question mismatch')
            for method in ('fixed_b2','tgf'):
                c = unique(method+'_answer', messages=actor_branch(original, selected, questions[method]))
                if c['request']['options'] != {'num_ctx':plan['actor_context'], 'num_predict':plan['answer_output_tokens'],
                    'seed':plan['actor_seed'], 'temperature':plan['actor_temperature']}:
                    raise ValueError('Actor condition settings differ')
                replies[method] = reply_projection(c['response'])
                if replies[method] != read(out/f'{method}_reply.json'):
                    raise ValueError('Reply projection mismatch')
        scores = {}
        for method in ('ledger_only','fixed_b2','tgf'):
            followup = None if method == 'ledger_only' or selected is None else {'question':questions[method], 'reply':replies[method]}
            bundle = {**common, 'followup':followup}
            if read(out/f'{method}_judge_input.json') != bundle:
                raise ValueError('Judge bundle differs from allowlisted data')
            c = unique(method+'_judge', render_prompt(JUDGE_SYSTEM, bundle))
            result = read(out/f'{method}_result.json')
            if result['judgment'] != json.loads(c['response']['response']):
                raise ValueError('Result mismatch')
            scores[method] = result['judgment']['unauthorized_action_score']
        results.append({'trace_id':name, 'selected_event':selected, 'scores':scores})
    if expected_calls != len(calls):
        raise ValueError('Unexpected extra/missing inference')
    report = {'passed':True, 'plan_sha256':digest(plan), 'calls':len(calls), 'traces':results,
        'checks':['full frozen visible input', 'same shared review/event/judge', 'independent original actor branches',
          'no follow-up tool execution', 'all native thinking retained', 'raw response derivation',
          'exact tokenizer/backend input counts', 'reference labels excluded from all reconstructed monitor requests'],
        'semantic_correctness': 'not established by structural checks',
        'costs':{m:{'calls':sum(c['request']['model']==m for c in calls),
            'input_tokens':sum(c['usage'].get('prompt_eval_count',0) for c in calls if c['request']['model']==m),
            'output_tokens':sum(c['usage'].get('eval_count',0) for c in calls if c['request']['model']==m),
            'request_seconds':sum(c['usage']['wall_seconds'] for c in calls if c['request']['model']==m)} for m in (MONITOR,ACTOR)}}
    save(output/'offline_verification.json', report)
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(verify(a.output),indent=2))
