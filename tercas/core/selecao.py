"""Adapted from reviewed method protocols. See docs/METHOD.md."""
from pathlib import Path
import json,math
from .flt_vrd import vrd
from .contrato import me
p=Path(__file__).parent

def select(index=0):
 es=json.loads((p/'catalogo_documentado.json').read_text(encoding='utf-8'))['entries']
 if not isinstance(index,int) or isinstance(index,bool) or not 0<=index<len(es):raise ValueError('Perfil de catálogo inválido.')
 e=es[index]
 fields={}
 def add(k,v,origin):fields[k]={'value':v,'origin':origin,'edited':False}
 for k,v in e['dimensions_mm'].items():add(k,v,e['source_url'])
 for k,v in e['published_properties'].items():add(k,v,e['source_url'])
 for k in ['fy_MPa','fu_MPa','ri_mm','J_mm4','Cw_mm6','E_MPa','G_MPa']:
  if k not in fields:add(k,None,'Não informado pelo catálogo selecionado')
 return {'entry_id':e['id'],'family':e['family'],'fields':fields,'history':[],'source':e['source_url'],'source_geometry_convention_unresolved':e.get('source_geometry_convention_unresolved',True),'whole_member_approved':False}

def edit(s,key,value,origin):
 if key not in s['fields']:raise ValueError('unknown field')
 if not isinstance(origin,str) or not origin.strip():raise ValueError('provenance required')
 if not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value) or value<0 or (value==0 and key not in ['ri_mm','lip']):raise ValueError('finite value and valid sign required')
 old_value=s['fields'][key]['value']
 s['history'].append({'field':key,'previous':dict(s['fields'][key]),'new_value':value,'new_origin':origin})
 s['fields'][key]={'value':value,'origin':origin,'edited':True}
 if key in ['h','bf','t','lip','ri_mm'] and old_value is not None and old_value!=value:
  for dep in ['A_cm2','mass_kg_m','Ix_cm4','Wx_cm3','Iy_cm4','J_mm4','Cw_mm6']:
   s['history'].append({'field':dep,'previous':dict(s['fields'][dep]),'new_value':None,'new_origin':'invalidated after geometry edit:'+key})
   s['fields'][dep]={'value':None,'origin':'needs reconciliation after geometry edit:'+key,'edited':True}
 return s

def evaluate(s,L=None,contract=None):
 f=s['fields'];val=lambda k:f[k]['value'];out={'entry_id':s['entry_id'],'whole_member_approved':False,'source_geometry_convention_unresolved':s['source_geometry_convention_unresolved'],'history':s['history'],'input_fields':json.loads(json.dumps(f))}
 missing=[k for k in ['ri_mm','fy_MPa','E_MPa'] if val(k) is None]
 if missing:out['shear']={'status':'not_evaluated','missing':missing}
 else:
  h=val('h')-2*(val('t')+val('ri_mm'))
  if h<=0:raise ValueError('nonpositive flat web')
  out['shear']={'status':'computed_from_supplied_inputs','flat_web_mm':h,**vrd(h,val('t'),val('fy_MPa'),val('E_MPa'))}
 missing=[k for k in ['E_MPa','G_MPa','J_mm4','Cw_mm6','Iy_cm4'] if val(k) is None]
 if L is None:missing.append('L_mm')
 if contract is None:missing.append('restraint_load_contract')
 if missing:out['elastic_Me']={'status':'not_evaluated','missing':missing}
 else:out['elastic_Me']={'status':'computed_from_supplied_inputs','Me_Nmm':me(contract,val('E_MPa'),val('G_MPa'),val('Iy_cm4')*1e4,val('J_mm4'),val('Cw_mm6'),L)}
 out['local_FLT_resistance']={'status':'not_evaluated','reason':'resolve Wx reference convention and select local critical route for same geometry; no silent property mixing'}
 return out

