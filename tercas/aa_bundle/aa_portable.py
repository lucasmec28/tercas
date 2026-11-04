"""Explicit, separate research entries. No method selection or mathematical changes."""
from pathlib import Path
import hashlib,json,types,uuid

class IntegrityError(RuntimeError):
    pass

class Bundle:
    """Caller must supply an independently trusted BUNDLE_MANIFEST.json SHA-256."""
    def __init__(self, expected_manifest_sha256):
        self.root=Path(__file__).resolve().parent
        self.expected_manifest_sha256=expected_manifest_sha256
        self.verify()
    def verify(self):
        try:
            raw=(self.root/'BUNDLE_MANIFEST.json').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=self.expected_manifest_sha256:
                raise IntegrityError('External bundle manifest pin mismatch')
            manifest=json.loads(raw)
            for rel,expected in manifest['files'].items():
                p=(self.root/rel).resolve()
                if not p.is_relative_to(self.root):raise IntegrityError('Path escapes bundle: '+rel)
                if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
                    raise IntegrityError('Bundle source mismatch: '+rel)
            return manifest
        except (OSError,ValueError,KeyError) as exc:
            raise IntegrityError('Bundle integrity failure: '+str(exc)) from exc
    def _call(self,entry,operation,*args,**kwargs):
        manifest=self.verify()
        path=self.root/manifest['entries'][entry]
        module=types.ModuleType('_aa_portable_'+uuid.uuid4().hex)
        module.__file__=str(path)
        exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
        return getattr(module,operation)(*args,**kwargs)
    def family_assess(self,request):return self._call('family','assess',request)
    def family_assess_json(self,raw):return self._call('family','assess_json',raw)
    def family_compare_component(self,request,component,limit_mm):return self._call('family','compare_component',request,component,limit_mm)
    def local_partition_assess(self,request,refinement_budget=64):return self._call('local_partition','assess',request,refinement_budget=refinement_budget)
    def local_partition_assess_json(self,raw,refinement_budget=64):return self._call('local_partition','assess_json',raw,refinement_budget=refinement_budget)
    def local_partition_compare_component(self,request,component,criterion_mm,refinement_budget=64):return self._call('local_partition','compare_component',request,component,criterion_mm,refinement_budget=refinement_budget)
    def positive_ratio_assess(self,request):return self._call('positive_ratio','assess',request)
    def positive_ratio_assess_json(self,raw):return self._call('positive_ratio','assess_json',raw)
    def positive_ratio_compare_component(self,request,component,limit_mm):return self._call('positive_ratio','compare_component',request,component,limit_mm)
