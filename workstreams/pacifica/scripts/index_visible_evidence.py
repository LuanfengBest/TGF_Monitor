"""Index every visible text field with exact source spans, without model calls.

User requests and policy have their own source IDs. Long YAML record lists are
split at parser-reported source offsets; all characters are retained exactly.
The index supplies identifiers for future retrieval, not inferred authorization.
"""
import argparse
import hashlib
import json
from pathlib import Path
import yaml
from ollama_client import digest, save
from run_structured_review import validate_view


def split_offsets(text):
    if len(text)<2000:
        return [(0,len(text))]
    try:
        node=yaml.compose(text,Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        node=None
    if isinstance(node,yaml.SequenceNode) and len(node.value)>1:
        starts=[0]+[x.start_mark.index for x in node.value[1:]]
        ends=starts[1:]+[len(text)]
        return list(zip(starts,ends))
    return [(0,len(text))]


def build_index(view):
    validate_view(view)
    sources=[('user_request',view['user_request']),('policy',view['policy'])]
    for i,msg in enumerate(view['messages']):
        # Entire messages preserve fields beyond content/thinking, including calls.
        sources.append((f'message_{i:04d}.json',json.dumps(msg,ensure_ascii=False)))
        for field in ('content','thinking'):
            if isinstance(msg.get(field),str) and msg[field]:
                sources.append((f'message_{i:04d}.{field}',msg[field]))
    records=[]
    source_info=[]
    for source_id,text in sources:
        spans=split_offsets(text) if source_id.endswith('.content') else [(0,len(text))]
        assert ''.join(text[a:b] for a,b in spans)==text
        sha=hashlib.sha256(text.encode()).hexdigest()
        source_info.append({'source_id':source_id,'sha256':sha,'length_chars':len(text),
                            'record_count':len(spans)})
        for j,(a,b) in enumerate(spans):
            records.append({'record_id':f'{source_id}#{j:03d}','source_id':source_id,
                'start_char':a,'end_char':b,'source_sha256':sha,'text':text[a:b]})
    return {'view_sha256':digest(view),'model_calls':0,'scope':'Lossless visible-source index; no labels, inferred facts, relevance filtering or scoring',
            'duplication_note':'Complete serialized messages and their separately indexed content/thinking fields intentionally overlap. Do not send all representations twice to a model.',
            'sources':source_info,'records':records}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for path in sorted(a.root.glob('*/monitor_view.json')):
        index=build_index(json.loads(path.read_text()))
        save(a.output/f'{path.parent.name}.json',index)
        manifest.append({'trace_id':path.parent.name,'view_sha256':index['view_sha256'],
                         'source_count':len(index['sources']),'records':len(index['records'])})
    save(a.output/'manifest.json',{'status':'indexed_not_evaluated','model_calls':0,'traces':manifest})
    print(json.dumps(manifest,indent=2))
