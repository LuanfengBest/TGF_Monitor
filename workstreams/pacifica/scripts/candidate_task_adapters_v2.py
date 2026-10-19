"""Explicit v2 fixture loader. No model transport or automatic generation approval."""
import hashlib
import json
from candidate_task_adapters_v1 import (
    ROOT, AGENT, Candidate, InvoiceEnvironment, RebookingEnvironment,
    FunctionsRuntime, make_function, require_generation_ready,
)

DIRECTORIES = {'bank_invoice_release': 'bank_invoice_release_v2',
               'airline_single_passenger_rebooking': 'airline_rebooking_v2'}


def load_candidate(candidate_id):
    directory = ROOT / 'data/task_design' / DIRECTORIES[candidate_id]
    revision = json.loads((directory / 'revision.json').read_text())
    for name, expected in revision['source_hashes'].items():
        if hashlib.sha256((AGENT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Original simulator changed: {name}')
    hashes = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
              for name in ['task.json', 'simulator_initial_state.json']}
    if hashes != revision['current_assets']:
        raise ValueError('Revised fixture hashes changed')
    task = json.loads((directory / 'task.json').read_text())
    state = json.loads((directory / 'simulator_initial_state.json').read_text())
    cls = InvoiceEnvironment if candidate_id == 'bank_invoice_release' else RebookingEnvironment
    # Do not use inherited create(), which intentionally continues loading v1.
    env = cls(**state)
    functions = [make_function(tool) for tool in env.available_tools]
    schemas = [{'type': 'function', 'function': {
        'name': f.name, 'description': f.description,
        'parameters': f.parameters.model_json_schema()}} for f in functions]
    if {s['function']['name'] for s in schemas} != set(task['tool_subset']) | {'end_task'}:
        raise ValueError('Unexpected exposed tool set')
    for schema in schemas:
        if set(schema['function']['parameters'].get('properties', {})) & set(type(env).model_fields):
            raise ValueError('Private dependency exposed in tool schema')
    return Candidate(candidate_id, task['user_request'], task['policy'], env,
                     FunctionsRuntime(functions), schemas, hashes)
