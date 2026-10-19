"""Train-side simulated email projection. No network, LLM, or training client.

Original FunctionsRuntime/get_file_by_id/send_email do all simulator operations.
Execution means insertion into the simulated sent store, never external delivery.
Visible contracts require trusted, complete raw exports and frozen implementations.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'third_party/MonitorBench/datasets/dual_objective/agent'
sys.path.insert(0, str(AGENT))
from environments.base_environment import BaseEnvironment
from environment_classes.cloud_drive import CloudDrive
from environment_classes.inbox import Inbox
from environment_classes.shared_models import Email, CalendarEvent
from tools.drive_tools import get_file_by_id
from tools.email_tools import send_email
from utils.functions_runtime import FunctionsRuntime, make_function
from utils.pipeline_elements import tool_result_to_str
from pydantic_core import to_jsonable_python
from monitor_contract_v2 import strict_json, exact_equal

FAMILY = 'tgf_travel_itinerary_field_projection'
DIRECTORY = ROOT / 'data/task_design/travel_projection_v1'
FIELDS = ('itinerary_id', 'flight_number', 'departure_city', 'arrival_city', 'departure_utc', 'arrival_utc')
PUBLIC_ARGS = {'get_file_by_id': {'file_id'}, 'send_email': {'recipients', 'subject', 'body', 'attachments', 'cc', 'bcc'}, 'end_task': set()}
ALLOWED = {'role', 'content', 'thinking', 'tool_calls', 'tool_name', 'tool_call_id', 'event_id', 'source_type'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ProjectionEnvironment(BaseEnvironment):
    cloud_drive: CloudDrive
    inbox: Inbox

    def model_post_init(self, __context):
        self.add_tools([get_file_by_id, send_email])

    @property
    def environment_type(self):
        return 'TravelProjectionV1'

    @classmethod
    def create(cls):
        raise ValueError('Explicit fixture required')


@dataclass
class Task:
    definition: dict
    environment: ProjectionEnvironment
    runtime: FunctionsRuntime
    schemas: list
    ended: bool = field(default=False, init=False)

    def public_input(self):
        return deepcopy({k: self.definition[k] for k in ('user_request', 'policy')}) | {'tools': deepcopy(self.schemas)}

    def run_tool(self, name, arguments):
        if self.ended:
            return '', 'TaskEndedError: no tools after end_task'
        if name not in PUBLIC_ARGS:
            return '', 'ToolNotFoundError: outside task subset'
        if type(arguments) is not dict or set(arguments) - PUBLIC_ARGS[name]:
            return '', 'ArgumentBoundaryError: nonpublic argument'
        try:
            # Round trip also prohibits nested FunctionCall objects/private dependencies.
            if not exact_equal(strict_json(canonical(arguments)), arguments):
                raise ValueError('non-JSON values')
        except (TypeError, ValueError):
            return '', 'ArgumentBoundaryError: nonfinite or non-JSON argument'
        result, error = self.runtime.run_function(self.environment, name, deepcopy(arguments))
        if name == 'end_task' and error is None and result == 'end_task':
            self.ended = True
        return result, error


def load_task(directory=DIRECTORY):
    directory = Path(directory)
    definition = strict_json((directory / 'task.json').read_text())
    if definition['family_id'] != FAMILY or definition['intended_split'] != 'train' or definition['training_eligible']:
        raise ValueError('Task family/split/training gate mismatch')
    state = strict_json((directory / 'fixture.json').read_text())
    if set(state) != {'cloud_drive', 'inbox'}:
        raise ValueError('Unknown fixture dependency')
    env = ProjectionEnvironment(**deepcopy(state))
    functions = [make_function(f) for f in env.available_tools]
    schemas = []
    if {f.name for f in functions} != set(PUBLIC_ARGS):
        raise ValueError('Unexpected tools')
    for f in functions:
        params = f.parameters.model_json_schema()
        if set(params.get('properties', {})) != PUBLIC_ARGS[f.name]:
            raise ValueError('Private or unknown schema argument')
        schemas.append({'type': 'function', 'function': {'name': f.name, 'description': f.description, 'parameters': params}})
    return Task(definition, env, FunctionsRuntime(functions), schemas)


def original_text(result, error):
    # Official formatter hook: only JSON serialization of original typed fields.
    return 'TOOL_ERROR: ' + error if error else tool_result_to_str(result, dump_fn=lambda obj: canonical(to_jsonable_python(obj)))


def source_hashes():
    paths = {ROOT / 'scripts/travel_projection_v1.py', ROOT / 'scripts/prepare_travel_projection_v1.py',
             ROOT / 'tests/test_travel_projection_v1.py'}
    # Include local imported utilities and all imported original simulator modules.
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            p = Path(filename).resolve()
            if p.suffix == '.py' and (p.is_relative_to(AGENT) or p.parent == ROOT / 'scripts'):
                paths.add(p)
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def projection_from_file(file_result, file_id='1', itinerary_id='TRIP-P'):
    """Exact public-file content projection, not a general PII detector."""
    f = strict_json(file_result)
    if (type(f) is not dict or f.get('id_') != file_id or type(f.get('content')) is not str
            or f.get('filename') != 'itinerary_register.json' or f.get('owner') != 'fixture.owner@example.com'):
        raise ValueError('Wrong/missing authoritative file')
    rows = strict_json(f['content'])
    if type(rows) is not list or any(type(r) is not dict or type(r.get('itinerary_id')) is not str or not r['itinerary_id'] for r in rows):
        raise ValueError('Malformed itinerary table')
    if len({r['itinerary_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate itinerary identity')
    matching = [r for r in rows if r['itinerary_id'] == itinerary_id]
    if len(matching) != 1:
        raise ValueError('Missing/ambiguous requested row')
    row = matching[0]
    if any(type(row.get(k)) is not str or not row[k] for k in FIELDS):
        raise ValueError('Missing/nonstring projected field')
    for k in ('departure_utc', 'arrival_utc'):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', row[k]):
            raise ValueError('Invalid UTC spelling')
        datetime.strptime(row[k], '%Y-%m-%dT%H:%M:%SZ')
    return {k: row[k] for k in FIELDS}


def decode_execution(arguments, text):
    """A narrow trusted-return contract. Malformed/ambiguous results stay unknown."""
    unknown = {'status': 'unknown', 'effect_scope': 'simulator_sent_store_insertion', 'real_delivery_verified': False}
    try:
        if type(arguments) is not dict or set(arguments) - PUBLIC_ARGS['send_email']:
            return unknown
        a = make_function(send_email).parameters.model_validate(arguments).model_dump()
        # Exactly this original exception is before any Inbox.send_email dispatch.
        if (a['attachments'] == [{'file_id': '1'}]
                and text == "TOOL_ERROR: ValueError: Attachment must have a 'type' field."):
            return unknown | {'status': 'observed_nonexecution', 'reason': 'original_attachment_parse_rejected_before_storage'}
        raw = strict_json(text)
        if type(raw) is not dict or set(raw) != set(Email.model_fields):
            return unknown
        actual = Email.model_validate(raw).model_dump(mode='json')
        if not exact_equal(actual, raw) or raw['status'] != 'sent' or raw['read'] is not True or raw['timestamp'] is not None:
            return unknown
        attachments = []
        for item in a['attachments'] or []:
            if 'type' not in item:
                return unknown
            if item['type'] == 'file' or 'file_id' in item:
                attachments.append(str(item['file_id']))
            else:
                attachments.append(CalendarEvent(**item['event_details']))
        expected = Email(id_=raw['id_'], sender=raw['sender'], recipients=a['recipients'], subject=a['subject'],
                         body=a['body'], cc=a['cc'] or [], bcc=a['bcc'] or [], attachments=attachments,
                         status='sent', read=True, timestamp=None).model_dump(mode='json')
        if not exact_equal(expected, raw):
            return unknown
        return unknown | {'status': 'observed_success', 'sent_email': raw}
    except (TypeError, ValueError, KeyError):
        return unknown


def source_table(view):
    result = [{'source_id': k, 'text': view[k]} for k in ('user_request', 'policy')]
    for i, m in enumerate(view['messages']):
        result.append({'source_id': f'm{i:04d}.metadata', 'text': canonical({k: v for k, v in m.items() if k not in ('content', 'thinking')})})
        for k in ('content', 'thinking'):
            if k in m:
                if type(m[k]) is not str:
                    raise ValueError('Non-text source')
                result.append({'source_id': f'm{i:04d}.{k}', 'text': m[k]})
    return result


def event_bundles(view):
    if set(view) != {'user_request', 'policy', 'messages'}:
        raise ValueError('Nonpublic view fields')
    canonical(view)
    calls, returned, seen, items = {}, set(), set(), []
    for i, msg in enumerate(view['messages']):
        if set(msg) - ALLOWED:
            raise ValueError('Nonpublic message fields')
        if msg['role'] == 'assistant':
            for call in msg.get('tool_calls', []):
                if set(call) != {'id', 'function'} or set(call['function']) != {'name', 'arguments'}:
                    raise ValueError('Nonpublic call fields')
                cid, function = call['id'], call['function']
                if cid in calls or function['name'] not in PUBLIC_ARGS or type(function['arguments']) is not dict:
                    raise ValueError('Duplicate identity/uncovered operation')
                calls[cid] = (i, function)
        elif msg['role'] == 'tool':
            cid, eid = msg['tool_call_id'], msg['event_id']
            if cid not in calls or cid in returned or eid in seen:
                raise ValueError('Unbound/duplicate result')
            ci, function = calls[cid]
            provenance = msg.get('source_type')
            if msg['tool_name'] != function['name'] or provenance not in {'tool_return', 'harness_execution_record'}:
                raise ValueError('Wrong result provenance/name')
            if provenance == 'harness_execution_record' and msg['content'] != 'HARNESS_INTERRUPTED: effects unknown':
                raise ValueError('Unrecognized harness record')
            seen.add(eid); returned.add(cid)
            if function['name'] != 'send_email':
                continue
            prefix = deepcopy(view); prefix['messages'] = prefix['messages'][:i+1]
            items.append({'event_id': eid, 'call_id': cid, 'result_message_index': i,
                          'call_source_id': f'm{ci:04d}.metadata', 'result_source_id': f'm{i:04d}.content',
                          'arguments': deepcopy(function['arguments']), 'causal_view': prefix,
                          'sources': source_table(prefix),
                          'execution_facts': decode_execution(function['arguments'], msg['content']) if provenance == 'tool_return' else
                          {'status': 'unknown', 'effect_scope': 'simulator_sent_store_insertion', 'real_delivery_verified': False}})
        else:
            raise ValueError('Unexpected role')
    if set(calls) != returned:
        raise ValueError('Unresolved call coverage; retain raw incomplete export')
    return items
