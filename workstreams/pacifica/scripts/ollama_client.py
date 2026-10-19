"""Native Ollama transport with durable requests, raw thinking and usage records."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Ollama:
    def __init__(self, output):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        host = os.environ.get('TGF_OLLAMA_URL') or subprocess.check_output(['ollama', 'host'], text=True).strip()
        self.host = host if host.startswith('http') else 'http://' + host
        if not self.host.startswith(('http://127.0.0.1:', 'http://localhost:')):
            raise ValueError('This runner requires the local job-scoped model server')
        self.count = 0

    def api(self, endpoint, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(self.host + '/api/' + endpoint, data=data,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=600) as response:
            return json.load(response)

    def metadata(self, model):
        return {'version': self.api('version'), 'tags': self.api('tags'),
                'show': self.api('show', {'model': model}),
                'job_id': os.environ.get('SLURM_JOB_ID'),
                'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv'], text=True)}

    def chat(self, model, messages, *, tools=None, think=True, ctx=32768,
             predict=2048, seed=42, temperature=0, format=None):
        # Byte count is a deliberately conservative input bound for these byte-level
        # tokenizers. Reserve extra space for chat/template/schema expansion. Reject
        # before sending rather than silently dropping older messages.
        size = len(json.dumps({'messages': messages, 'tools': tools or []}, ensure_ascii=False).encode())
        overhead = 4096 + 128 * len(messages) + 256 * len(tools or [])
        if size + overhead + predict > ctx:
            raise ValueError(f'Context guard: {size}+{overhead}+{predict}>{ctx}; no messages discarded')
        payload = {'model': model, 'messages': messages, 'stream': False, 'think': think,
                   'keep_alive': '15m', 'options': {'num_ctx': ctx, 'num_predict': predict,
                   'seed': seed, 'temperature': temperature}}
        if tools:
            payload['tools'] = tools
        if format is not None:
            payload['format'] = format
        self.count += 1
        stem = self.output / f'call_{self.count:04d}'
        save(str(stem) + '_request.json', payload)
        start = time.monotonic()
        try:
            result = self.api('chat', payload)
        except Exception as exc:
            save(str(stem) + '_error.json', {'error': repr(exc), 'wall_seconds': time.monotonic()-start})
            raise
        save(str(stem) + '_response.json', result)
        save(str(stem) + '_usage.json', {'model': model, 'wall_seconds': time.monotonic()-start,
             'api_charge_usd': None, **{k: v for k, v in result.items() if k.endswith(('_count','_duration'))}})
        return result

    def unload(self, model):
        return self.api('generate', {'model': model, 'keep_alive': 0})
