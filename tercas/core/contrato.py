"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math

def qualify(c):
 problems=[]
 if not isinstance(c,dict):return {"model_contract_satisfied":False,"issues":["contract must be mapping"],"physical_design_approved":False}
 if not isinstance(c.get("actions"),list) or any(not isinstance(a,dict) for a in c.get("actions",[])):return {"model_contract_satisfied":False,"issues":["actions must be list of mappings"],"physical_design_approved":False}
 if c.get('sheet_restraint_credit') is not False:problems.append('sheet_restraint_credit must be false')
 if c.get('topology')!='single_span_no_overhang':problems.append('unsupported topology')
 if c.get('intermediate_braces')!=[]:problems.append('intermediate brace modes require separate qualified route')
 for end in ['left','right']:
  r=c.get(end,{})
  if not isinstance(r,dict):
   problems.append(end+':restraint must be mapping');continue
  for key,value in [('lateral_displacement','fixed'),('twist','fixed'),('warping','free'),('weak_bending_rotation','free')]:
   if r.get(key)!=value:problems.append(end+':'+key+' not qualified by this route')
  if not isinstance(r.get('evidence'),str) or not r['evidence'].strip():problems.append(end+':missing restraint provenance')
 if c.get('load_height_relative_CT_mm')!=0:problems.append('load height outside selected Me model')
 if c.get('bending_axis')!='strong_symmetry_axis' or c.get('axial_force_N')!=0 or c.get('weak_bending_Nmm')!=0:problems.append('strong-axis-only zero-axial domain required')
 if c.get('strong_axis_symmetry') is not True:problems.append('section symmetry not qualified')
 for action in c.get('actions',[]):
  if not isinstance(action.get('name'),str):problems.append('action identity missing')
  if action.get('torque_demonstrated_zero') is not True:problems.append(str(action.get('name'))+':torsion requires applicable route')
  if not isinstance(action.get('evidence'),str) or not action['evidence'].strip():problems.append('action provenance missing')
 if not c.get('actions'):problems.append('actions missing including self-weight disposition')
 if not any(a.get('name')=='self_weight' for a in c.get('actions',[])):problems.append('self-weight disposition missing')
 return {'model_contract_satisfied':not problems,'issues':problems,'physical_design_approved':False}

def me(c,E,G,Iy,J,Cw,L):
 q=qualify(c)
 if not q['model_contract_satisfied']:raise ValueError('; '.join(q['issues']))
 if not all(math.isfinite(v) and v>0 for v in (E,G,Iy,J,Cw,L)):raise ValueError('positive finite properties required')
 # NBR9.8.2.2 specialized Cb1, fork ends, free warping; Ly=Lz=L.
 return math.pi/L*math.sqrt(E*Iy*(G*J+math.pi**2*E*Cw/L**2))
