"""Experimental sharp-corner U/Ue signature interface. Never returns approved resistance/local Mcr."""
import hashlib,json
from pathlib import Path
import numpy as np
if __package__:
 from .core import channel,stresses,solve,scalar
else:
 from core import channel,stresses,solve,scalar

def analyze(request):
 request=json.loads(json.dumps(request,allow_nan=False)) # immutable-by-caller snapshot
 required={'geometry','E_MPa','nu','axis','moment_sign','mesh_n','halfwaves_mm'}
 if set(request)!=required:raise ValueError('provide exactly '+', '.join(sorted(required)))
 g=request['geometry']
 if set(g)!={'h_mm','b_mm','lip_mm','t_mm'}:raise ValueError('geometry requires h_mm,b_mm,lip_mm,t_mm')
 E=scalar(request['E_MPa'],'E_MPa',True);nu=scalar(request['nu'],'nu')
 if not -1<nu<.5:raise ValueError('nu outside isotropic elastic domain')
 axis=request['axis'];sign=request['moment_sign']
 if axis not in ('x','y') or isinstance(sign,bool) or sign not in (-1,1):raise ValueError('explicit axis and sign required')
 raw=request['halfwaves_mm']
 if not isinstance(raw,list) or not 3<=len(raw)<=81:raise ValueError('operational budget: 3 to 81 halfwaves')
 lengths=[scalar(x,'halfwave',True) for x in raw]
 if any(b<=a for a,b in zip(lengths,lengths[1:])):raise ValueError('halfwaves must strictly increase')
 p=channel(g['h_mm'],g['b_mm'],g['lip_mm'],g['t_mm'],request['mesh_n'])
 if len(p)>97:raise ValueError('operational budget: maximum 97 nodes; not a physical limit')
 s,props=stresses(p,g['t_mm'],**{'Mx' if axis=='x' else 'My':sign*1e6})
 curve=[]
 for L in lengths:
  f,v,r=solve(p,g['t_mm'],L,s,E,nu,count=1);curve.append({'halfwave_mm':L,'first_positive_factor_kNm':float(f[0]),'relative_residual':float(r[0])})
 fingerprints={f:hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in ['core.py','custom_geometry_experimental.py']}
 return {'schema_version':1,'status':'experimental_signature_pending_mode_identification','design_approved':False,'local_Mcr_kNm':None,'distortional_Mcr_kNm':None,'input':request,'request_sha256':hashlib.sha256(json.dumps(request,sort_keys=True,allow_nan=False).encode()).hexdigest(),'implementation_sha256':fingerprints,'geometry_model':'external dimensions converted to sharp middleline; no corner radius, holes or stiffener restraints','longitudinal_boundary':'simply supported, one sinusoidal halfwave','nodes':p.tolist(),'middleline_properties':props,'curve':curve,'limitations':['No automatic mode classification; first eigenvalue is not automatically local.','No resistance calculation or production catalogue write.','A sampled signature does not establish a continuous minimum.','x is horizontal and y vertical in plotted section; inertia order is not assumed.','Different bending signs remain separate.']}
