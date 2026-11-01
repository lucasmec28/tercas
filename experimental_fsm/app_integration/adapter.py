"""Isolated bridge. Intentionally has no import/write path to production catalogue or resistance engine."""
import sys,json,hashlib
from pathlib import Path
import importlib,importlib.util
import numpy as np
if __package__ and '.' in __package__:
 from ..custom_geometry_experimental import analyze
 from ..core import channel,stresses,solve,NotEvaluated
else:
 # Standalone/app_integration import: load a private package, never global core.
 root=Path(__file__).resolve().parents[1];name='_lro_fsm_experimental_engine'
 if name in sys.modules:
  if Path(sys.modules[name].__file__).resolve()!=root/'__init__.py':raise ImportError('FSM package namespace already belongs to another path')
 else:
  spec=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
  module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
 engine=importlib.import_module(name+'.core');entry=importlib.import_module(name+'.custom_geometry_experimental')
 analyze=entry.analyze;channel=engine.channel;stresses=engine.stresses;solve=engine.solve;NotEvaluated=engine.NotEvaluated

def fingerprint(request):return hashlib.sha256(json.dumps(request,sort_keys=True,allow_nan=False).encode()).hexdigest()
def run(request):
 result=analyze(request)
 result['sampled_valleys']=[i for i in range(1,len(result['curve'])-1) if result['curve'][i]['first_positive_factor_kNm']<min(result['curve'][i-1]['first_positive_factor_kNm'],result['curve'][i+1]['first_positive_factor_kNm'])]
 result['mode_classification']='não identificada automaticamente; mínimo de assinatura não implica modo local'
 return result

def ensure_current(request,result):
 for filename,digest in result.get('implementation_sha256',{}).items():
  if filename not in ('core.py','custom_geometry_experimental.py'):raise ValueError('Origem de implementação desconhecida.')
  actual=hashlib.sha256(Path(__file__).resolve().parents[1].joinpath(filename).read_bytes()).hexdigest()
  if actual!=digest:raise ValueError('Implementação alterada: recalcule o estudo.')
 if set(result.get('implementation_sha256',{}))!={'core.py','custom_geometry_experimental.py'}:raise ValueError('Rastreabilidade da implementação ausente.')
 if result.get('request_sha256')!=fingerprint(request):raise ValueError('Entradas alteradas: recalcule antes de usar ou exportar o resultado.')
 if result.get('design_approved') is not False or result.get('local_Mcr_kNm') is not None or result.get('distortional_Mcr_kNm') is not None:raise ValueError('Resultado incompatível com escopo experimental.')

def export_json(request,result):
 ensure_current(request,result)
 return json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)

def mode_at(request,result,index):
 ensure_current(request,result)
 if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(result['curve']):raise ValueError('Selecione um ponto calculado da assinatura.')
 r=json.loads(json.dumps(request));g=r['geometry'];p=channel(g['h_mm'],g['b_mm'],g['lip_mm'],g['t_mm'],r['mesh_n']);s,_=stresses(p,g['t_mm'],**{'Mx' if r['axis']=='x' else 'My':r['moment_sign']*1e6});L=result['curve'][index]['halfwave_mm'];f,v,res=solve(p,g['t_mm'],L,s,r['E_MPa'],r['nu'],count=1)
 if not np.isclose(f[0],result['curve'][index]['first_positive_factor_kNm'],rtol=1e-8,atol=0):raise ValueError('Resultado não corresponde ao cálculo atual.')
 # Dimensionless visualization normalization only, not displacement response.
 q=v[:,0].reshape(-1,4);amp=float(max(np.linalg.norm(q[:,:2],axis=1)))
 if amp<=0:raise ValueError('Modo transversal não disponível para desenho.')
 return {'half_wave_mm':L,'eigenfactor_kNm':float(f[0]),'residual':float(res[0]),'nodes_mm':p.tolist(),'transverse_shape_normalized':(q[:,:2]/amp).tolist(),'rotation_shape_per_normalization':(q[:,3]/amp).tolist(),'classification':'pending_review','warning':'Forma modal normalizada e arbitrariamente amplificada; não é deslocamento de serviço.'}

def section_svg(mode):
 p=np.asarray(mode['nodes_mm']);q=np.asarray(mode['transverse_shape_normalized']);span=max(float(np.ptp(p[:,0])),float(np.ptp(p[:,1])),1);d=p+.10*span*q;allp=np.vstack([p,d]);lo=allp.min(axis=0)-.15*span;hi=allp.max(axis=0)+.15*span
 def points(a):return ' '.join(f'{(x-lo[0])/span*300:.3f},{(hi[1]-y)/span*300:.3f}' for x,y in a)
 w=(hi[0]-lo[0])/span*300;h=(hi[1]-lo[1])/span*300
 return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.3f} {h:.3f}" role="img" aria-label="Seção e forma modal normalizada"><polyline points="{points(p)}" fill="none" stroke="#25334a" stroke-dasharray="4 3" stroke-width="2"/><polyline points="{points(d)}" fill="none" stroke="#d96516" stroke-width="2"/></svg>'
