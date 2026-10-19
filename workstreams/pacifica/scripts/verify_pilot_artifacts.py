"""Verify frozen input projection, exact chunk reconstruction and run provenance."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from ollama_client import digest, save
from run_b1 import parts


def verify(root):
    plan=json.loads((root/'plan.json').read_text())
    rows=[]
    for item in plan['attempts']:
        trace=item['trace_id']; actor=root/'actors'/trace; monitor=root/'b1'/trace
        read=lambda p:json.loads(p.read_text())
        view=read(actor/'monitor_view.json'); raw=read(actor/'raw/actor_context.json')
        cfg=read(actor/'config.json'); mc=read(monitor/'config.json')
        assert set(view)=={'user_request','policy','messages'}
        assert raw[1]['role']=='user' and raw[1]['content']==view['user_request']
        projected=[{k:m[k] for k in ('role','content','thinking','tool_calls','tool_name') if k in m} for m in raw if m['role'] in ('assistant','tool')]
        assert projected==[{k:v for k,v in m.items() if k!='event_id'} for m in view['messages']],trace
        assert cfg['seed']==item['seed'] and cfg['temperature']==plan['generation_temperature']
        assert cfg['condition']==item['condition']
        assert mc==read(Path(plan['monitor_configuration']))
        assert read(monitor/'input_identity.json')['view_sha256']==digest(view)==read(monitor/'result.json')['view_sha256']
        chunks=read(monitor/'chunks.json'); assert chunks==parts(view,mc['monitor_chunk_chars'])
        reconstructed=defaultdict(str)
        for chunk in chunks:
            for part in chunk:
                assert len(reconstructed[part['message_id']])==part['offset']
                reconstructed[part['message_id']]+=part['text']
        assert [json.dumps(m,ensure_ascii=False) for m in view['messages']]==[reconstructed[i] for i in range(len(view['messages']))]
        for p in (monitor/'calls').glob('call_*_request.json'):
            request=read(p); assert request['think'] is False
            response=read(p.with_name(p.name.replace('_request','_response')))
            assert response.get('done_reason')!='length' and not response['message'].get('thinking')
        sources=read(actor/'source_hashes.json')
        for name in ('ollama_client.py','run_bank_actor.py','run_b1.py','run_bank_pilot.py'):
            assert sources[name]==hashlib.sha256((Path('scripts')/name).read_bytes()).hexdigest(),name
        rows.append({'trace_id':trace,'view_sha256':digest(view),'raw_projection_matches':True,
                     'chunks_lossless':True,'monitor_config_matches':True,'generation_config_matches':True,
                     'actor_reasoning_messages':sum(bool(m.get('thinking')) for m in view['messages']),
                     'monitor_think_false_verified':True,'no_capped_monitor_responses':True,
                     'runtime_source_hashes_match':True})
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=verify(a.root);save(a.output,result)
    print(json.dumps(result,indent=2))
