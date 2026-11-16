"""Reject cache misses before vLLM can cold-compile; no inference setting changes."""
import json
import os
from pathlib import Path
from .common import BUNDLE, CACHE_REL, ROOT, FACTOR_SHA, filehash


def install(manager_class):
    if getattr(manager_class,'_timing_warm_only',False):return
    original=manager_class.load
    def guarded(self,graph,example_inputs,graph_index,compile_range):
        expected=ROOT/'runtime_cache'/CACHE_REL
        if Path(self.cache_dir).resolve()!=expected.resolve():
            raise RuntimeError('Warm-cache key mismatch; cold compilation forbidden')
        if filehash(expected/'cache_key_factors.json')!=FACTOR_SHA:
            raise RuntimeError('Warm-cache factors changed; cold compilation forbidden')
        value=original(self,graph,example_inputs,graph_index,compile_range)
        if value is None:
            raise RuntimeError('Warm-cache miss; cold compilation forbidden')
        path=BUNDLE/'results'/('cache_hits_'+str(os.getpid())+'.jsonl')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a') as f:f.write(json.dumps({'graph_index':graph_index,'range_start':compile_range.start,'range_end':compile_range.end,'pid':os.getpid()})+'\n')
        return value
    manager_class.load=guarded
    manager_class._timing_warm_only=True
