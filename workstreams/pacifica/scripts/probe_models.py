"""Check real generation, thinking and tool-call transport; no benchmark claims."""
import argparse
from pathlib import Path
from ollama_client import Ollama, save

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    client = Ollama(a.output / 'calls')
    save(a.output / 'metadata.json', client.metadata(a.model))
    think = 'low' if a.model.startswith('gpt-oss') else True
    r = client.chat(a.model, [{'role':'user','content':'What is 17 + 25? Answer with the number.'}], think=think, predict=1024)
    m = r['message']
    result = {'model': a.model, 'content': m.get('content'),
              'raw_thinking_nonempty': bool(m.get('thinking')),
              'done_reason': r.get('done_reason'), 'benchmark_result': False}
    if a.model.startswith('gpt-oss'):
        tool = {'type':'function','function':{'name':'lookup_balance','description':'Look up a simulated account balance.',
                'parameters':{'type':'object','properties':{},'required':[]}}}
        messages = [{'role':'user','content':'Call lookup_balance to check my simulated account balance; do not guess.'}]
        r = client.chat(a.model, messages, tools=[tool], think=think, predict=1024)
        calls = r['message'].get('tool_calls', [])
        result['tool_call_names'] = [c['function']['name'] for c in calls]
        if result['tool_call_names'] != ['lookup_balance']:
            raise RuntimeError('Expected one lookup_balance call')
        messages += [r['message'], {'role':'tool','tool_name':'lookup_balance','content':'123.45 USD'}]
        r = client.chat(a.model, messages, tools=[tool], think=think, predict=1024)
        result['tool_reply_content'] = r['message'].get('content')
    save(a.output / 'summary.json', result)
    print(result, flush=True)
    print(client.api('ps'), flush=True)
    client.unload(a.model)

if __name__ == '__main__':
    main()
