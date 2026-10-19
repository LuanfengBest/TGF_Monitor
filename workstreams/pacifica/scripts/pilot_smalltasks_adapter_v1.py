"""Versioned public task decomposition; all original state/tools/model remain fixed."""
from prospective_actor_v6 import ROOT,load_original,require_original_ready,canonical_state,read,digest,sha_text
TASKS=ROOT/'data/pilot_smalltasks_v1/public_tasks.json'

def load_small(attempt):
    if attempt['condition']!='ordinary':raise ValueError('Focused feasibility is ordinary only')
    task=next((t for t in read(TASKS)['instances'] if t['task_id']==attempt.get('task_id')),None)
    if task is None or task['candidate_id']!=attempt['candidate_id']:raise ValueError('Unregistered focused task')
    if task['request_sha256']!=sha_text(task['user_request']):raise ValueError('Focused request digest')
    c=load_original(attempt['candidate_id'])
    parent=read(ROOT/'configs/pilot_collection_v1.json')
    require_original_ready(c,parent['registry']['candidates'])
    if attempt.get('secondary_objective')!=c.secondary_objective:raise ValueError('Hidden asset changed')
    expected={'schemas':digest(c.schemas),'initial_state':digest(canonical_state(c.environment.model_dump(mode='json'))),'policy':digest(c.policy),'original_request':digest(c.user_request)}
    if task['parent_asset_digests']!=expected:raise ValueError('Focused task changed environment, tools or original authority')
    c.original_request=c.user_request;c.user_request=task['user_request'];c.task_id=task['task_id']
    return c

def require_small_ready(candidate,registry):
    task=next(t for t in read(TASKS)['instances'] if t['task_id']==candidate.task_id)
    if candidate.user_request!=task['user_request']:raise ValueError('Focused public request changed')
    focused=candidate.user_request
    try:
        candidate.user_request=candidate.original_request
        return require_original_ready(candidate,registry['candidates'])
    finally:candidate.user_request=focused
