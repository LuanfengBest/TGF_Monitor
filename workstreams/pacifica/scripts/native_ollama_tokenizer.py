"""CPU-only counter for the observed Qwen3/Ollama native BPE implementation.

Prepared compatibility component, not retroactively installed in frozen v1/v2.
No inference, no +4 adjustment, and no tolerance for backend disagreement.
"""
import hashlib
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class NativeCounter:
    def __init__(self, binary=None):
        provenance = json.loads((ROOT / 'tools/ollama_tokenizer/provenance.json').read_text())
        self.vocabulary = ROOT / provenance['vocabulary']
        actual = hashlib.sha256(self.vocabulary.read_bytes()).hexdigest()
        if actual != provenance['vocabulary_sha256']:
            raise ValueError('Native tokenizer vocabulary hash changed')
        machine = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine(), platform.machine())
        self.binary = Path(binary) if binary else ROOT / f'tools/ollama_tokenizer/bin/tokenizer-{platform.system().lower()}-{machine}'
        if not self.binary.is_file():
            raise FileNotFoundError(f'Build the pinned CPU tokenizer helper first: {self.binary}')
        binary_sha = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        if binary_sha not in provenance['binary_sha256'].values():
            raise ValueError('Native tokenizer executable is not one of the audited builds')

    def encode(self, text, include_ids=False):
        result = subprocess.run([str(self.binary), str(self.vocabulary), '--stdin'],
            input=json.dumps({'prompt': text, 'include_ids': include_ids}) + '\n',
            text=True, capture_output=True, check=True, timeout=30)
        return json.loads(result.stdout)

    def count(self, text):
        return self.encode(text)['count']

    def check(self, text, output_tokens):
        n = self.count(text)
        if n + output_tokens + 128 > 32768:
            raise ValueError(f'Token capacity: {n}+{output_tokens}+128>32768; no truncation')
        return n
