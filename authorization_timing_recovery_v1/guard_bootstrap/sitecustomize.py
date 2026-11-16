"""Install a lazy, pinned vLLM cache-miss guard in every spawned interpreter."""
import importlib.abc
import importlib.machinery
import os
import sys

if os.environ.get('TIMING_REQUIRE_WARM_CACHE')=='1':
    class TimingLoader:
        def __init__(self,original):self.original=original
        def __getattr__(self,name):return getattr(self.original,name)
        def create_module(self,spec):return self.original.create_module(spec)
        def exec_module(self,module):
            self.original.exec_module(module)
            from authorization_timing_recovery_v1.cache_guard import install
            install(module.CompilerManager)
    class TimingFinder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname!='vllm.compilation.backends':return None
            spec=importlib.machinery.PathFinder.find_spec(fullname,path)
            if spec is None or spec.loader is None:raise ImportError('Pinned vLLM backend unavailable')
            spec.loader=TimingLoader(spec.loader)
            return spec
    sys.meta_path.insert(0,TimingFinder())
