"""Account for every saved model request, including capped and failed attempts."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from ollama_client import save


def summarize(root):
    groups = defaultdict(lambda: dict(requests=0, responses=0, capped_responses=0,
        transport_errors=0, post_response_errors=0, requests_without_response=0, prompt_tokens=0,
        output_tokens=0, measured_request_wall_seconds=0.0,
        server_total_seconds=0.0))
    for path in sorted(root.rglob('call_*_request.json')):
        request = json.loads(path.read_text())
        directory = str(path.parent.relative_to(root))
        key = (directory, request['model'])
        row = groups[key]
        row['requests'] += 1
        stem = str(path)[:-len('_request.json')]
        response = Path(stem + '_response.json')
        usage = Path(stem + '_usage.json')
        error = Path(stem + '_error.json')
        if response.exists():
            raw = json.loads(response.read_text())
            row['responses'] += 1
            row['capped_responses'] += raw.get('done_reason') == 'length'
        else:
            row['requests_without_response'] += 1
        if usage.exists():
            raw = json.loads(usage.read_text())
            row['prompt_tokens'] += raw.get('prompt_eval_count', 0)
            row['output_tokens'] += raw.get('eval_count', 0)
            row['measured_request_wall_seconds'] += raw.get('wall_seconds', 0)
            row['server_total_seconds'] += raw.get('total_duration', 0) / 1e9
        if error.exists():
            raw = json.loads(error.read_text())
            # A saved, completed response followed by a local integrity failure
            # is still a billable response, not a transport failure.
            row['post_response_errors' if response.exists() else 'transport_errors'] += 1
            if not usage.exists():
                row['measured_request_wall_seconds'] += raw.get('wall_seconds', 0)
    rows = [dict(directory=d, model=m, **values) for (d,m),values in groups.items()]
    totals = defaultdict(lambda: defaultdict(int))
    for row in rows:
        for key,value in row.items():
            if isinstance(value, (int,float)):
                totals[row['model']][key] += value
    return dict(by_attempt=rows, by_model=dict(totals), currency_cost_usd=None,
        notes=[
            'Local job-scoped Ollama only; no paid inference API was invoked.',
            'HPC accounting price was not provided; currency cost is unknown, not zero.',
            'Output tokens include native thinking as reported by the runtime.',
            'Includes probes, failed token-capped calls and retries; metadata/unload requests are not inference calls.',
            'Request wall time is not allocated GPU time; Slurm allocation accounting is recorded separately.',
        ])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('results'))
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = summarize(a.root)
    save(a.output, result)
    print(json.dumps(result['by_model'], indent=2))
