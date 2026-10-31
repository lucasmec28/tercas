"""Boundary adapter, traceable inputs and partial results. No UI state in the core."""
import copy, hashlib, json, math, warnings
from scipy.integrate import IntegrationWarning
from .core.selecao import select, edit
from .core.especificacao_unica import evaluate
from .core.travamentos_nbr import segment_moments
from .catalogs import catalog_labels, critical_defaults, apply_material, entries, STEEL_NAMES
from .core.local_table12 import local_critical
from .load_combinations import COMBINATION_TYPES

VERSION='0.4.3-estudo'

def defaults(index=0):
 s=select(index)
 d={'schema':'tercas_input_v2','catalog_index':index,'synthetic':False,'project':'Estudo de terça',
 'properties':{k:v['value'] for k,v in s['fields'].items()},'property_origin':'Informação do usuário; conferir documento do perfil e material',
 'L_mm':3000.,'q_uls':0.,'P_uls':0.,'x_uls':1500.,'q_sls':0.,'P_sls':0.,'x_sls':1500.,
 'actions_origin':'Ações de uma combinação informada pelo usuário; fatores já aplicados quando ELU',
 'Ml_Nmm':None,'Mdist_Nmm':None,'critical_origin':'','ELS_limit_mm':None,'ELS_origin':'',
 'route_domain':False,'segments':[{'start_mm':0.,'end_mm':3000.,'Ly_effective_mm':None,'Lz_effective_mm':None,'Cb_mode':'one','restraint_provenance':''}],
 'left_web':False,'right_web':False,'support_origin':'','patch_mm':None,'patch_origin':'',
 'steel_name':'ASTM A36','load_mode':'direct','selected_types':['ELU normal','ELS rara','ELS frequente'],
 'area_inputs':{'spacing_m':1.5,'permanent_kgf_m2':0.,'live_kgf_m2':0.,'wind_up_kgf_m2':0.,'wind_down_kgf_m2':0.},
 'ELS_down_denominator':180.,'ELS_up_denominator':120.}
 d.update(critical_defaults(index));d=apply_material(d,'ASTM A36')
 if d['Ml_Nmm'] is None:
  f=d['properties']
  try:
   c=local_critical(s['family'],f['h'],f['bf'],f['t'],f['Wx_cm3']*1000,f['E_MPa'],D_mm=f['lip']);d['Ml_Nmm']=c['Ml_Nmm'];d['critical_origin']+='; Ml calculado: '+c['origin']
  except (ValueError,TypeError):pass
 return d

def example():
 idx=next(i for i,e in enumerate(entries()) if e['family']=='U' and e['dimensions_mm']=={'h':100,'bf':50,'lip':0,'t':2})
 d=defaults(idx);d['synthetic']=True;d['project']='EXEMPLO DIDÁTICO — não é projeto'
 d['properties'].update(E_MPa=200000.,G_MPa=200000/2.6,fy_MPa=250.,fu_MPa=400.,ri_mm=2.,J_mm4=520.,Cw_mm6=164780000.)
 d.update(property_origin='Dados sintéticos do teste de interface; não certificados pelo fabricante',q_uls=.30726527,P_uls=1500.,q_sls=.229812216,P_sls=1000.,Ml_Nmm=3195774.181964692,critical_origin='Crítico sintético para regressão de interface; não validado para o perfil do fabricante',ELS_limit_mm=3000/180,ELS_origin='L/180 selecionado no exemplo didático',route_domain=True,left_web=True,right_web=True,support_origin='Apoios por alma ligada assumidos no exemplo didático',patch_mm=40.,patch_origin='Contato central sintético')
 d['segments']=[dict(start_mm=0.,end_mm=3000.,Ly_effective_mm=3000.,Lz_effective_mm=3000.,Cb_mode='one',restraint_provenance='Comprimentos efetivos sintéticos de teste')]
 return d

def fingerprint(data):return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest()

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def build_spec(data):
 if not isinstance(data,dict):raise ValueError('O arquivo deve conter um objeto de entradas JSON.')
 from .inclination_adapter import configuration,number
 configuration(data)
 from .weak_axis import validate
 validate(data)
 for key in ('q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls'):number(data.get(key,0.),key)
 if not isinstance(data,dict):raise ValueError('O arquivo deve conter um objeto de entradas JSON.')
 if data.get('schema')!='tercas_input_v2':raise ValueError('Formato anterior não reconhecido nesta atualização de catálogo. Selecione novamente o perfil para evitar troca de seção por índice.')
 if data.get('steel_name') not in STEEL_NAMES:raise ValueError('Tipo de aço inválido.')
 if data.get('load_mode') not in ('direct','area'):raise ValueError('Modo de carregamento inválido.')
 types=data.get('selected_types')
 if not isinstance(types,list) or any(x not in COMBINATION_TYPES for x in types) or len(set(types))!=len(types):raise ValueError('Tipos de combinação inválidos.')
 area=data.get('area_inputs')
 area_keys={'spacing_m','permanent_kgf_m2','live_kgf_m2','wind_up_kgf_m2','wind_down_kgf_m2'}
 if not isinstance(area,dict) or set(area)!=area_keys:raise ValueError('Entradas de área incompletas.')
 if any(not finite(v) or v<0 for v in area.values()) or area['spacing_m']<=0:raise ValueError('Entradas de área inválidas.')
 for key in ['ELS_down_denominator','ELS_up_denominator']:
  if not finite(data.get(key)) or data[key]<=0:raise ValueError('Denominador ELS inválido: '+key)
 if not isinstance(data.get('catalog_index'),int) or isinstance(data['catalog_index'],bool) or not 0<=data['catalog_index']<len(catalog_labels()):raise ValueError('Perfil de catálogo inválido.')
 required=set(defaults(data['catalog_index']))
 missing=required-set(data)
 if missing:raise ValueError('Arquivo incompleto. Campos ausentes: '+', '.join(sorted(missing)))
 for key in ['project','property_origin','actions_origin','critical_origin','ELS_origin','support_origin','patch_origin']:
  if not isinstance(data.get(key),str) or len(data[key])>2000:raise ValueError('Texto inválido ou excessivo: '+key)
 for key in ['synthetic','route_domain','left_web','right_web']:
  if not isinstance(data.get(key),bool):raise ValueError('Opção inválida: '+key)
 if not isinstance(data.get('properties'),dict) or set(data['properties'])!=set(defaults(data['catalog_index'])['properties']):raise ValueError('Conjunto de propriedades incompleto ou não reconhecido.')
 for key in ['Ml_Nmm','Mdist_Nmm','ELS_limit_mm','patch_mm']:
  val=data.get(key)
  if val is not None and not finite(val):raise ValueError('Número inválido: '+key)
 fy=data['properties'].get('fy_MPa');fu=data['properties'].get('fu_MPa')
 if finite(fy) and finite(fu) and fu<fy:raise ValueError('fu não pode ser menor que fy.')
 d=copy.deepcopy(data);L=d['L_mm']
 if not finite(L) or not 0<L<=100000:raise ValueError('Informe um vão positivo, até 100.000 mm nesta versão.')
 for key in ['q_uls','P_uls','q_sls','P_sls','x_uls','x_sls']:
  if not finite(d.get(key)):raise ValueError('Ação ou posição inválida: '+key)
 for key in ['x_uls','x_sls']:
  if not 0<d[key]<L:raise ValueError('A posição da carga concentrada deve estar dentro do vão, não no apoio.')
 s=select(d['catalog_index']);incoming=d.get('properties',{})
 # Geometry is catalog-controlled in this first emission, no silent property mixing.
 for key in ['h','bf','t','lip']:
  if incoming.get(key)!=s['fields'][key]['value']:raise ValueError('Geometria alterada: selecione um perfil disponível. Seção manual não implementada nesta emissão.')
 for key,val in incoming.items():
  if key not in s['fields']:raise ValueError('Propriedade desconhecida: '+key)
  if val is None:s['fields'][key]={'value':None,'origin':'Não informada','edited':True}
  elif val!=s['fields'][key]['value']:edit(s,key,val,d.get('property_origin',''))
 # Radius initially absent may be provided without invalidating published properties;
 # convention uncertainty remains visible in every report.
 def critical(key):return {'value':d.get(key),'origin':d.get('critical_origin','')}
 segs=d.get('segments',[])
 if not isinstance(segs,list) or len(segs)>20:raise ValueError('Use até 20 trechos por caso.')
 for seg in segs:
  if not isinstance(seg,dict):raise ValueError('Trecho inválido.')
  required_segment={'start_mm','end_mm','Lz_effective_mm','Cb_mode','restraint_provenance'}
  if not ('Ly_effective_mm' in seg or {'Ly_top_effective_mm','Ly_bottom_effective_mm'}.issubset(seg)):raise ValueError('Informe os comprimentos efetivos das mesas superior e inferior.')
  if not required_segment.issubset(seg):raise ValueError('Trecho incompleto: informe início, fim, Ly, Lz, Cb e origem.')
  if seg.get('Cb_mode') not in ('one','quarter_formula'):raise ValueError('Opção de Cb inválida no trecho.')
  for k in ('start_mm','end_mm','Ly_effective_mm','Ly_top_effective_mm','Ly_bottom_effective_mm','Lz_effective_mm'):
   if k in seg and seg[k] is not None and not finite(seg[k]):raise ValueError('Comprimento ou coordenada inválida no trecho: '+k)
  if seg.get('restraint_provenance') is not None and not isinstance(seg['restraint_provenance'],str):raise ValueError('Origem dos vínculos deve ser texto.')
 spec={'selected_section':s,'L_mm':L,'route_domain':'strong_symmetry_CT_no_primary_torsion' if d.get('route_domain') is True else None,
 'Ml':critical('Ml_Nmm'),'Mdist':critical('Mdist_Nmm'),
 'ULS':{'q_Nmm':d['q_uls'],'P_N':d['P_uls'],'x_mm':d['x_uls'],'origin':d.get('actions_origin','')},
 'SLS':{'q_Nmm':d['q_sls'],'P_N':d['P_sls'],'x_mm':d['x_sls'],'origin':d.get('actions_origin','')},
 'segments':copy.deepcopy(segs),'ELS_limit_mm':{'value':d.get('ELS_limit_mm'),'origin':d.get('ELS_origin','')},
 'introduction':{'left':{'route':'web_connection' if d.get('left_web') is True else None,'origin':d.get('support_origin','')},'right':{'route':'web_connection' if d.get('right_web') is True else None,'origin':d.get('support_origin','')},'point':{'c_mm':d.get('patch_mm'),'origin':d.get('patch_origin','')}}}
 return spec

def calculate(data):
 from .inclination_adapter import direct_evidence
 spec=build_spec(data)
 inclination_evidence=direct_evidence(data)
 with warnings.catch_warnings(record=True) as captured:
  warnings.simplefilter('always',IntegrationWarning)
  result=evaluate(spec)
 result['numerical_warnings']=[str(w.message) for w in captured if issubclass(w.category,IntegrationWarning)]
 if result['numerical_warnings']:
  result['ELS']['criterion_status']='not_evaluated_numerical_warning'
  result['ELS'].pop('index',None)
  result['ELS']['reason']='Integração emitiu aviso numérico. Flecha apenas diagnóstica; limite não concluído.'
 result.update(version=VERSION,project=data.get('project',''),synthetic=data.get('synthetic') is True,input_fingerprint=fingerprint(data),input_data=copy.deepcopy(data))
 b=result['NBR_branches']
 # No concentrated compressive action means this particular check is inapplicable,
 # not a missing field. Negative force is outside this compression-only adapter.
 if data['P_uls']==0:b['point']={'status':'not_applicable','reason':'Sem força concentrada de compressão no caso informado.'}
 result['inclination_evidence']=inclination_evidence
 result['whole_member_approved']=False
 result['coverage_warnings']=[]
 intervals=[]
 for seg in data['segments']:
  a,b=seg.get('start_mm'),seg.get('end_mm')
  if finite(a) and finite(b) and 0<=a<b<=data['L_mm']:intervals.append((a,b))
 end=0.
 for a,b in sorted(intervals):
  if a>end+1e-8:result['coverage_warnings'].append('Há parte do vão sem trecho de FLT informado.')
  if a<end-1e-8:result['coverage_warnings'].append('Há trechos de FLT sobrepostos; conferir comprimentos efetivos.')
  end=max(end,b)
 if end<data['L_mm']-1e-8:result['coverage_warnings'].append('Há parte do vão sem trecho de FLT informado.')
 result['coverage_warnings']=list(dict.fromkeys(result['coverage_warnings']))
 from .weak_axis import integrate
 integrate(result)
 return result

STATUS={'not_evaluated':'Não avaliado','invalid_inputs':'Entrada inválida','FLT_not_evaluated':'Não avaliado','route_domain_not_declared':'Domínio não informado','computed':'Calculado','computed_bending_component':'Componente de flexão calculada','computed_from_supplied_inputs':'Calculado com dados informados','computed_fixed_load_position':'Calculado na posição informada','computed_from_supplied_effective_lengths':'Calculado com comprimentos informados','not_applicable':'Não aplicável','exempt_Table14':'Dispensado pela Tabela 14','stiffener_exception_9_5_1':'Exceção de enrijecedor §9.5.1','outside_implemented_family':'Fora da versão','invalid_or_outside_implemented_domain':'Entrada inválida ou fora do domínio'}

def rows(result):
 out=[]
 def add(name,r,source,index=None):
  idx=r.get('index') if index is None else index
  status=STATUS.get(r.get('status'),r.get('status','Não avaliado'))
  if idx is not None and finite(idx):status='Não atende' if idx>1 else 'Atende ao critério calculado'
  detail=translate(r.get('reason',r.get('missing','')))
  if r.get('compressed_flange'):detail=f"Mesa comprimida governante: {r['compressed_flange']}; comprimento lateral efetivo: {r.get('Ly_used_mm')} mm; Lz torsional: {r.get('Lz_used_mm')} mm. "+str(detail)
  if isinstance(detail,list):detail=', '.join(map(str,detail))
  out.append({'Verificação':name,'Situação':status,'Índice':idx,'Demanda / valor':'—','Resistência / limite':'—','Referência':source,'Observação':str(detail)})
 b=result['NBR_branches'];add('Flexão local',b['local'],'NBR 14762 §9.8.2.1');add('Distorcional',b['distortional'],'§9.3 / §9.8.2.3 / Tabela 14')
 for i,r in enumerate(result['FLT_segments'],1):add(f'FLT — trecho {i}',r,'§9.8.2.2')
 shear=result['section_checks'].get('shear',{});d=result['input_data'];L=d['L_mm'];q=d['q_uls'];P=d['P_uls'];a=d['x_uls'];R=q*L/2+P*(L-a)/L;V=max(abs(R),abs(R-q*a),abs(R-q*a-P),abs(R-q*L-P))
 add('Cortante',shear,'§9.8.3',V/shear['VRd_N'] if shear.get('VRd_N') else None)
 mv=b['MV'];add('Flexão e cortante concomitantes',mv,'§9.8.4',mv.get('result',{}).get('index_squared'))
 add('Flecha — flexão',result['ELS'],'§9.8.5; critério informado')
 for row in out:
  name=row['Verificação']
  if name=='Flexão local':r=b['local'];cap=r.get('MRd_Nmm');dem=r.get('Msd_Nmm')
  elif name=='Distorcional':r=b['distortional'];cap=r.get('MRd_Nmm');dem=r.get('Msd_Nmm')
  elif name.startswith('FLT —'):
   r=result['FLT_segments'][int(name.split()[-1])-1];cap=r.get('FLT',{}).get('MRd_flt_Nmm');dem=r.get('moments',{}).get('Mmax_Nmm')
  else:continue
  if dem is not None:row['Demanda / valor']=f'{dem/1e6:.6f} kN·m'
  if cap is not None:row['Resistência / limite']=f'{cap/1e6:.6f} kN·m'
 for row in out:
  name=row['Verificação']
  if name=='Cortante':
   row['Demanda / valor']=f'{V/1000:.6f} kN'
   if shear.get('VRd_N'):row['Resistência / limite']=f"{shear['VRd_N']/1000:.6f} kN"
  elif name=='Carga concentrada' and b['point'].get('FRd_N'):
   row['Demanda / valor']=f"{b['point']['force_N']/1000:.6f} kN";row['Resistência / limite']=f"{b['point']['FRd_N']/1000:.6f} kN"
  elif name=='Flecha — flexão':
   els=result['ELS']
   if els.get('deflection_mm') is not None:row['Demanda / valor']=f"{els['deflection_mm']:.6f} mm em x={els['x_mm']:.3f} mm"
   if els.get('limit_mm') is not None:row['Resistência / limite']=f"{els['limit_mm']:.6f} mm"
  elif name=='Flexão e cortante concomitantes':row['Resistência / limite']='Σ índices² ≤ 1'
 from .inclination_adapter import pending_rows
 for state,ev in result.get('inclination_evidence',{}).items():
  out+=pending_rows(ev,state)
 return out


TRANSLATIONS={
'web connected to another beam/column':'Alma ligada a outra viga ou pilar; a ligação não é dimensionada nesta verificação.',
'W,fy,Ml and critical origin':'Faltam Wx, fy, Ml ou a origem do crítico.',
'local MRd,VRd,ULS origin and actions':'Faltam resistência local, cortante, ações ELU ou sua origem.',
'select actual web connection, transverse stiffener or flange-contact geometry; no new normative check invented':'Informe o detalhe real do apoio: alma ligada, enrijecedor ou contato pela mesa. Esta versão oferece a primeira alternativa.',
'point patch geometry and origin missing':'Faltam comprimento e origem do contato da carga concentrada.',
'outside isolated internal positive patch subset':'Contato fora do subconjunto interno de compressão isolada desta versão.',
'current patch subset needs declared end-web connections; flange contacts need separate geometry':'Introdução localizada não concluída: o detalhe necessário ao adaptador do Anexo D não foi informado. Ligações e apoios estão fora do escopo do app.',
'ULS action provenance missing':'Falta a origem das ações ELU.',
'positive effective lengths required':'Ly e Lz efetivos devem ser positivos e finitos.',
'subroutine requires declared NBR strong-axis expression domain; not generic any-profile stability':'Informe o domínio da expressão de Me. A rotina não representa qualquer situação de estabilidade.',
'W,fy and Mdist with origin':'Faltam Wx, fy ou Mdist com origem para este ramo distorcional.',
'Protocolo de máximo único limitado a ações de mesmo sentido':'A flecha desta versão cobre q e P de mesmo sentido. Este caso continua disponível nas demais verificações.',
'invalid segment/action geometry':'Geometria do trecho ou posição da ação inválida.',
'Ml with positive value and origin':'Ml positivo e origem', 'Ml with origin':'Ml e origem', 'SLS actions with origin':'ações ELS e origem',
'applicable ELS limit with source':'limite ELS aplicável com origem', 'Ly_top_effective_mm':'Comprimento efetivo da mesa superior','Ly_bottom_effective_mm':'Comprimento efetivo da mesa inferior','Ly_effective_mm':'Comprimento lateral efetivo da mesa comprimida', 'Lz_effective_mm':'Lz efetivo', 'restraint_provenance':'origem do vínculo',
}
def translate(value):
 if isinstance(value,list):return ', '.join(TRANSLATIONS.get(str(v),str(v)) for v in value)
 return TRANSLATIONS.get(str(value),str(value))

