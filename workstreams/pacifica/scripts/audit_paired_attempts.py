"""Audit incomplete paired attempts without promoting them to accepted results."""
from collections import defaultdict
import difflib
import importlib
import json
from pathlib import Path
import hashlib
from tokenizers import Tokenizer
import jsonschema
from native_ollama_tokenizer import NativeCounter, ROOT
from summarize_costs import summarize


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def audit():
    native = NativeCounter()
    hf = Tokenizer.from_file(str(ROOT / 'data/tokenizers/qwen3_32b/tokenizer.json'))
    rows, tokenizer_rows = [], []
    jobs = [('paired_first_29362188', 'paired_protocol', 'run_paired_v1', 283),
            ('paired_ascii_first_29362895', 'paired_protocol_v2', 'run_paired_v2', 248)]
    for run, protocol, runner, gpu_seconds in jobs:
        directory = ROOT / 'results' / run
        p = importlib.import_module(protocol)
        plan = read(directory / 'plan.json')
        assert plan == read(p.PLAN)
        for name, expected in read(directory / 'source_hashes.json').items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
        original, shared = importlib.import_module(runner).verify_inputs(plan['attempts'][0])
        trace = directory / plan['attempts'][0]['trace_id']
        review = read(trace / 'initial_review.json')
        selected = p.select_event(shared, review)
        assert selected == read(trace / 'selected_event.json')
        common = {**shared, 'initial_review': review, 'selected_event': selected}
        questions = read(trace / 'questions.json')
        assert questions['fixed_b2'] == p.FIXED_QUESTION
        expected_prompts = {
            'calibration_short': p.render_prompt('Return the JSON status ok.', {'test': 'Token count calibration.'}),
            'calibration_full_trace': p.render_prompt('Return the JSON status ok. The supplied data needs no analysis.', shared),
            'initial_review': p.render_prompt(p.REVIEW_SYSTEM, shared),
            'targeted_question': p.render_prompt(p.QUESTION_SYSTEM, common),
        }
        for method in ('ledger_only', 'fixed_b2'):
            followup = None if method == 'ledger_only' else {'question': questions[method], 'reply': read(trace / f'{method}_reply.json')}
            bundle = {**common, 'followup': followup}
            assert bundle == read(trace / f'{method}_judge_input.json')
            expected_prompts[method + '_judge'] = p.render_prompt(p.JUDGE_SYSTEM, bundle)
        call_rows = []
        for path in sorted((directory / 'calls').glob('*_request.json')):
            stem = str(path)[:-len('_request.json')]
            request, response, identity = [read(stem + suffix + '.json') for suffix in ('_request', '_response', '_identity')]
            assert response['done_reason'] == 'stop'
            name = identity['name']
            if identity['endpoint'] == 'generate':
                assert request['prompt'] == expected_prompts[name]
                assert request['raw'] is True and request['model'] == p.MONITOR
                parsed = json.loads(response['response'])
                jsonschema.validate(parsed, request['format'])
                if name == 'initial_review':
                    assert parsed == review
                if name == 'targeted_question':
                    assert parsed['question'] == questions['tgf']
                encoded = native.encode(request['prompt'], include_ids=True)
                assert encoded['count'] == response['prompt_eval_count']
                assert native.check(request['prompt'], request['options']['num_predict']) == encoded['count']
                hf_ids = hf.encode(request['prompt'], add_special_tokens=False).ids
                differences = []
                for op, a, b, c, d in difflib.SequenceMatcher(a=hf_ids, b=encoded['ids'], autojunk=False).get_opcodes():
                    if op != 'equal':
                        differences.append({'operation': op, 'hf_ids': hf_ids[a:b], 'native_ids': encoded['ids'][c:d],
                            'hf_text': hf.decode(hf_ids[a:b]), 'native_text': hf.decode(encoded['ids'][c:d]),
                            'context': hf.decode(hf_ids[max(0, a-3):b+3])})
                tokenizer_rows.append({'path': str(path.relative_to(ROOT)), 'hf_count': len(hf_ids),
                    'native_count': encoded['count'], 'backend_count': response['prompt_eval_count'], 'differences': differences})
            else:
                method = name.removesuffix('_answer')
                assert method in ('fixed_b2', 'tgf')
                assert 'tools' not in request and request['model'] == p.ACTOR
                assert request['messages'] == p.actor_branch(original, selected, questions[method])
                assert p.reply_projection(response) == read(trace / f'{method}_reply.json')
                assert request['options']['num_predict'] == plan['answer_output_tokens']
            call_rows.append({'name': name, 'input_tokens': response['prompt_eval_count'],
                              'output_tokens': response['eval_count'], 'done_reason': response['done_reason']})
        assert len(call_rows) == 8
        rows.append({'run': run, 'status': read(directory / 'summary.json')['status'], 'gpu_seconds': gpu_seconds,
            'calls': call_rows, 'frozen_source_hashes_match': True, 'allowed_inputs_reconstructed': True,
            'independent_tool_disabled_actor_branches_verified': True, 'all_native_counts_match_backend': True,
            'complete_pair': False, 'accepted_results_changed': False,
            'missing_call': 'tgf_judge', 'selected_event': selected['event_id'],
            'ledger_only_score': read(trace / 'ledger_only_result.json')['judgment']['unauthorized_action_score'],
            'costs': summarize(directory)})
    report = {'inference_calls_by_this_audit': 0, 'complete_three_method_pairs': 0,
        'runs': rows, 'note': 'Offline reconstruction does not overwrite failure status or fill missing judgments.'}
    save(ROOT / 'analysis/paired_attempts_2026-10-12.json', report)
    save(ROOT / 'analysis/paired_native_go_tokenizer_audit.json', {'inference_calls': 0,
        'source': 'https://github.com/ollama/ollama/tree/v0.22.0/tokenizer',
        'vocabulary_origin': 'actual cached GGUF including special token types',
        'all_counts_match_backend': True, 'requests': tokenizer_rows})
    previous = read(ROOT / 'results/costs_total_through_contract_probe.json')
    combined = previous['by_model']
    for row in rows:
        for model, costs in row['costs']['by_model'].items():
            for key, value in costs.items():
                combined[model][key] = combined[model].get(key, 0) + value
    save(ROOT / 'results/costs_total_through_paired_attempts.json', {
        'previous_snapshot': 'results/costs_total_through_contract_probe.json',
        'added_snapshot': 'analysis/paired_attempts_2026-10-12.json', 'by_model': combined,
        'new_inference_requests': 16, 'total_inference_requests': sum(x['requests'] for x in combined.values()),
        'new_gpu_seconds': 531, 'major_gpu_allocations_through_this_run_seconds': 7737,
        'currency_cost_usd': None, 'new_jobs': [{'run': row['run'], 'status': 'FAILED', 'gpu_seconds': row['gpu_seconds']} for row in rows],
        'note': 'Both completed raw responses followed by failed input-count checks are charged. No retries or later GPU submissions. CPU tokenizer audit makes no inference calls.'})
    print(json.dumps({'audited_calls': 16, 'monitor_counts_matched': len(tokenizer_rows), 'complete_pairs': 0, 'new_gpu_seconds': 531}))


if __name__ == '__main__':
    audit()
