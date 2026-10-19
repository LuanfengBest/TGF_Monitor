"""Fixture-only adapters for three reviewed monitor-v2 mechanism candidates.

Original tools and FunctionsRuntime perform all simulator work. No model transport,
labels, generation runner, semantic authorization checker or old fixture loader.
"""
from dataclasses import dataclass, field
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'third_party/MonitorBench/datasets/dual_objective/agent'
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))
from environments.base_environment import BaseEnvironment
from environment_classes.bank_accounts import BankAccount
from environment_classes.cloud_drive import CloudDrive
from environment_classes.travel_booking import Flights, User
from environment_classes.inbox import Inbox
from environment_classes.ticket import TicketManager
from tools.drive_tools import get_file_by_id
from tools.financial_transfer import get_scheduled_transactions, schedule_transaction
from tools.flight_tools import cancel_flight_booking
from utils.functions_runtime import FunctionsRuntime, make_function

CANDIDATES = {
    'bank_cumulative_spend_pool': 'train',
    'bank_batch_quorum': 'validation',
    'airline_duplicate_retention': 'validation',
}
VARIANTS = {name: ('base',) for name in CANDIDATES}
VARIANTS['bank_batch_quorum'] = ('base', 'review_set_b', 'review_set_c')
PUBLIC_ARGS = {
    'get_file_by_id': {'file_id'},
    'get_scheduled_transactions': set(),
    'schedule_transaction': {'recipient', 'amount', 'subject', 'date', 'recurring', 'override'},
    'cancel_flight_booking': {'flight_number', 'name_on_ticket', 'confirmation_number'},
    'end_task': set(),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BankMechanismEnvironment(BaseEnvironment):
    bank_account: BankAccount
    cloud_drive: CloudDrive

    def model_post_init(self, __context):
        self.add_tools([get_file_by_id, get_scheduled_transactions, schedule_transaction])

    @property
    def environment_type(self):
        return 'MonitorV2BankMechanism'

    @classmethod
    def create(cls):
        raise ValueError('Use explicit hash-checked load_task; no implicit fixture')


class RetentionEnvironment(BaseEnvironment):
    cloud_drive: CloudDrive
    flights: Flights
    user: User
    flight_tickets: dict[str, list[str]]
    total_spent: dict
    inbox: Inbox
    ticket_manager: TicketManager

    def model_post_init(self, __context):
        self.add_tools([get_file_by_id, cancel_flight_booking])

    @property
    def environment_type(self):
        return 'MonitorV2Retention'

    @classmethod
    def create(cls):
        raise ValueError('Use explicit hash-checked load_task; no implicit fixture')


def make_environment(candidate_id, state):
    if candidate_id not in CANDIDATES:
        raise ValueError('Unreviewed candidate')
    cls = RetentionEnvironment if candidate_id == 'airline_duplicate_retention' else BankMechanismEnvironment
    if set(state) != set(cls.model_fields):
        raise ValueError('Unexpected or missing private state keys')
    return cls(**deepcopy(state))


def functions_and_schemas(environment):
    functions = [make_function(tool) for tool in environment.available_tools]
    schemas = []
    for function in functions:
        params = function.parameters.model_json_schema()
        if set(params.get('properties', {})) != PUBLIC_ARGS[function.name]:
            raise ValueError(f'Public argument surface changed: {function.name}')
        if set(params.get('properties', {})) & set(type(environment).model_fields):
            raise ValueError('Private dependency leaked to schema')
        schemas.append({'type': 'function', 'function': {
            'name': function.name, 'description': function.description, 'parameters': params}})
    return functions, schemas


def source_hashes():
    """Pin imported original Python implementations plus the two new adapter scripts."""
    paths = {ROOT / 'scripts/monitor_v2_task_adapters.py', ROOT / 'scripts/prepare_monitor_v2_tasks.py',
             ROOT / 'tests/test_monitor_v2_task_adapters.py', ROOT / 'scripts/observed_execution_v1.py',
             ROOT / 'scripts/observed_airline_execution_v1.py'}
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(AGENT) and path.suffix == '.py':
                paths.add(path)
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


@dataclass
class PreparedTask:
    candidate_id: str
    user_request: str
    policy: str
    environment: BaseEnvironment
    runtime: FunctionsRuntime
    schemas: list
    fixture_hashes: dict
    intended_split: str
    split: object = None  # proposal intent is not a frozen executable split
    training_eligible: bool = False
    generation_approved: bool = False
    ended: bool = field(default=False, init=False)

    def public_input(self):
        # Positive allowlist, never serialize this dataclass or its environment.
        return deepcopy({'user_request': self.user_request, 'policy': self.policy, 'tools': self.schemas})

    def run_tool(self, name, arguments):
        """CPU dispatch boundary. It does not enforce user business authorization.

        Later runners must use this boundary or implement the same end_task guard;
        original FunctionsRuntime alone does not terminate a task after end_task.
        """
        if self.ended:
            return None, 'TaskEndedError: no tools after end_task'
        if name not in self.runtime.functions:
            return None, 'ToolNotFoundError: tool outside this task subset'
        if not isinstance(arguments, dict) or set(arguments) - PUBLIC_ARGS[name]:
            return None, 'ArgumentBoundaryError: nonpublic argument'
        try:
            # Reject objects/nested function objects outside plain JSON arguments.
            json.dumps(arguments, allow_nan=False)
        except (TypeError, ValueError):
            return None, 'ArgumentBoundaryError: arguments must be finite JSON'
        result, error = self.runtime.run_function(self.environment, name, arguments)
        if name == 'end_task' and result == 'end_task' and error is None:
            self.ended = True
        return result, error


def task_directory_name(candidate_id, variant='base'):
    if candidate_id not in VARIANTS or variant not in VARIANTS[candidate_id]:
        raise ValueError('Unreviewed candidate/variant')
    return 'monitor_v2_' + candidate_id + ('' if variant == 'base' else '__' + variant)


def load_task(candidate_id, directory=None, variant='base'):
    if candidate_id not in CANDIDATES:
        raise ValueError('Unreviewed candidate')
    dirname = task_directory_name(candidate_id, variant)
    directory = Path(directory) if directory is not None else ROOT / 'data/task_design' / dirname
    manifest = json.loads((directory / 'preparation_manifest.json').read_text())
    if (manifest['candidate_id'] != candidate_id or manifest['variant'] != variant
            or manifest.get('generation_approved') is not False):
        raise ValueError('Fixture-only candidate identity/gate changed')
    for name, expected in manifest['source_hashes'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError(f'Frozen source changed: {name}')
    for name, expected in manifest['review_source_hashes'].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f'Review/proposal changed: {name}')
    required = {'task.json', 'simulator_initial_state.json', 'tool_schemas.json'}
    if set(manifest['asset_hashes']) != required:
        raise ValueError('Incomplete fixture asset manifest')
    for name, expected in manifest['asset_hashes'].items():
        if digest(directory / name) != expected:
            raise ValueError(f'Fixture changed: {name}')
    task = json.loads((directory / 'task.json').read_text())
    if task['candidate_id'] != candidate_id or task['intended_split'] != CANDIDATES[candidate_id]:
        raise ValueError('Task identity/split intent mismatch')
    if task['generation_approved'] or task['training_eligible']:
        raise ValueError('Fixture preparation is not generation/training approval')
    environment = make_environment(candidate_id, json.loads((directory / 'simulator_initial_state.json').read_text()))
    functions, schemas = functions_and_schemas(environment)
    if schemas != json.loads((directory / 'tool_schemas.json').read_text()):
        raise ValueError('Runtime schema differs from frozen public schema')
    if {f.name for f in functions} != set(task['tool_subset']) | {'end_task'}:
        raise ValueError('Unexpected tool subset')
    return PreparedTask(candidate_id, task['user_request'], task['policy'], environment,
                        FunctionsRuntime(functions), schemas, manifest['asset_hashes'], task['intended_split'])


def load_candidate(candidate_id, variant='base'):
    return load_task(candidate_id, variant=variant)


def require_generation_ready(*args, **kwargs):
    raise ValueError('Fixture-only preparation: actor/model generation and training are not approved')
