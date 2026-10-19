"""Transport-only revision: reversible ASCII JSON avoids backend Unicode splitting discrepancies.

Protocol prompts, models, original evidence, ranking and budgets inherit frozen v1.
The failed v1 attempt remains separate; all v2 conditions are freshly paired.
"""
from paired_protocol import *

PLAN = ROOT / 'configs/paired_v2_plan.json'


def compact(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c')


def render_prompt(system, bundle):
    return ('<|im_start|>system\n' + system + '<|im_end|>\n'
            '<|im_start|>user\n' + compact(bundle) + ' /no_think<|im_end|>\n'
            '<|im_start|>assistant\n<think>\n\n</think>\n\n')
