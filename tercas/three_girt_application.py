"""Explicit opt-in adapter for the three-girt elastic diagnostic.

Never feeds N/M/V/T from this frame into the legacy N=0 resistance route.
No ELS, rod strength, warping or whole-member approval is issued here.
"""
import copy
import math
from .three_girt_frame import solve_three_girts,topology

SCHEMA='tercas_three_girt_results_v1'
GERDAU='https://gsn.gerdau.com/sites/gsn_gerdau/files/downloadable_files/Barras-e-Perfis-Tabela-de-bolso.pdf'
SOURCES=[
 {'title':'Gerdau — Barras e Perfis, tabela de bolso (03/19)','url':GERDAU,'use':'PDF p3: L3×3×3/16, A=7.03 cm², massa=5.52 kg/m; p8: redonda 3/8, 9.53 mm comercial, 0.56 kg/m. A redonda calculada com conversão nominal exata de 9.525 mm, não tabelada.'},
 {'title':'Gerdau — Barras e Perfis (02/14)','url':'https://gsn.gerdau.com/sites/gsn_gerdau/files/downloadable_files/catalogo-barras-e-perfis.pdf','use':'PDF p6: família de produtos ASTM A36; não certifica lote real ou ligação.'},
 {'title':'SCI P385 — Design of Steel Beams in Torsion','url':'https://www.steelconstruction.info/images/6/6f/Sci_p385.pdf','use':'§2.5–2.6 e §4: centro de cisalhamento, torção e empenamento. GJ não substitui ECw nem condições de empenamento.'},
 {'title':'OpenSees — Elastic Beam Column Element','url':'https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/elasticBeamColumn.html','use':'Referência de formulação elástica de barra 3D: A,E,G,J,Iy,Iz. Não certifica o modelo físico deste projeto.'},
 {'title':'OpenSees — Truss Element','url':'https://opensees.berkeley.edu/wiki/index.php/Truss_Element','use':'Elemento axial; sem rigidez geométrica nesta hipótese de primeira ordem.'},
]
LIMITATIONS=[
 'DIAGNÓSTICO ELÁSTICO CONDICIONAL: sem conclusão resistente, sem aprovação ELS e sem aprovação global.',
 'Saint-Venant/Euler–Bernoulli bruto: não inclui empenamento ECw, bimomento, tensões normais de empenamento, cisalhamento deformável, instabilidades ou segunda ordem.',
 'Fixar rotação de torção dos seis extremos não define restrição de empenamento.',
 'As barras azuis e cantoneiras verdes são idealizadas axiais bilaterais (tração e compressão), sem flexão local, folga ou pré-tensão. Não há verificação resistente dessas barras, das ligações ou da ancoragem.',
 'As travessas vermelhas são contínuas nas ligações internas: reações, N e momentos negativos são mantidos. Não se divide o vão em vigas simplesmente apoiadas nem se reduz FLT/Lz automaticamente.',
 'N/M/V/T são simultâneos por combinação, seção e lado. Máximos de componentes distintos não formam uma solicitação concomitante.',
 'A rota resistente existente pressupõe N=0 e não recebe os esforços deste sistema. Flexocompressão/tração, flexão fraca, torção/empenamento e Ief permanecem sem qualificação para este modelo.',
 'Flechas são absolutas do centroide com inércias brutas; não confronto ELS nem flecha relativa a uma corda de painel. Conferir sentido, referências e fechamento.',
 'Cargas distribuídas uniformes apenas nesta implementação. Ações concentradas ativas são recusadas, não ignoradas.',
 'Geometria, posições de carga, centro de cisalhamento e braços das ligações são declarações, não levantamentos ou comprovação física.',
]


def defaults():
 return dict(enabled=False,tie_count=2,position_mode='uniform',positions_mm=[],
  geometry_declared=False,axial_bars_declared=False,connections_declared=False,load_line_declared=False,origin='',
  sc_y_mm=None,sc_z_mm=0.,sc_origin='',load_y_from_CG_mm=0.,load_z_from_CG_mm=0.,
  connection_mode='concentric',connection_arm_mm=[0.,0.,0.],connection_offsets={},
  blue=dict(label='Barra redonda ASTM A36 Ø3/8 — Gerdau',A_mm2=math.pi*9.525**2/4,E_MPa=200000.,mass_kg_m=.56,
            origin='Gerdau tabela de bolso p8: massa nominal; A calculada com d=(3/8)×25.4=9.525 mm. E=200000 MPa declarado, não fornecido nessa tabela.'),
  green=dict(label='Cantoneira ASTM A36 L3×3×3/16 — Gerdau',A_mm2=703.,E_MPa=200000.,mass_kg_m=5.52,
             origin='Gerdau tabela de bolso p3: A=7.03 cm² e massa=5.52 kg/m nominais. E=200000 MPa declarado, não fornecido nessa tabela.'),
  brace_self_weight=True,direct_pp_uls_N_mm=None,direct_pp_sls_N_mm=None,
  direct_brace_factor_uls=None,direct_brace_factor_sls=None)


def enabled(data):
 raw=data.get('three_girt_model',{})
 if not isinstance(raw,dict):raise ValueError('Configuração do sistema de três travessas deve ser objeto.')
 active=raw.get('enabled',False)
 if not isinstance(active,bool):raise ValueError('Ativação do sistema 3D deve ser booleana.')
 return active and data.get('member_application','purlin')=='wall_girt'


def _number(v,name,positive=False,nonnegative=False):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (positive and v<=0) or (nonnegative and v<0):
  raise ValueError(name+': número finito '+('positivo' if positive else 'não negativo' if nonnegative else '')+' requerido.')
 return float(v)


def configuration(data):
 raw=data.get('three_girt_model',{});c=defaults()
 if not isinstance(raw,dict) or set(raw)-set(c):raise ValueError('Campos desconhecidos na configuração do sistema 3D.')
 c.update(copy.deepcopy(raw))
 for key in ('enabled','geometry_declared','axial_bars_declared','connections_declared','load_line_declared','brace_self_weight'):
  if not isinstance(c[key],bool):raise ValueError('Opção 3D deve ser booleana: '+key)
 if isinstance(c['tie_count'],bool) or not isinstance(c['tie_count'],int) or not 0<=c['tie_count']<=20:raise ValueError('Quantidade de linhas de tirantes deve ser inteira de 0 a 20 nesta implementação.')
 if c['position_mode'] not in ('uniform','custom'):raise ValueError('Modo de posições 3D inválido.')
 if c['connection_mode'] not in ('concentric','common_arm','individual'):raise ValueError('Modo de ligação 3D inválido.')
 for key in ('origin','sc_origin'):
  if not isinstance(c[key],str) or len(c[key])>2000:raise ValueError('Origem inválida/excessiva: '+key)
 L=_number(data.get('L_mm'),'Vão',positive=True)
 if L>100000:raise ValueError('Vão superior a 100000 mm fora desta implementação.')
 if c['position_mode']=='uniform':positions=[L*j/(c['tie_count']+1) for j in range(1,c['tie_count']+1)]
 else:
  positions=c['positions_mm']
  if not isinstance(positions,list) or len(positions)!=c['tie_count']:raise ValueError('Informe uma posição por linha de tirantes.')
  positions=[_number(v,'Posição do tirante') for v in positions]
 if any(b<=a for a,b in zip([0.]+positions,positions+[L])):raise ValueError('Posições devem crescer estritamente no interior do vão.')
 c['resolved_positions_mm']=positions
 for key in ('sc_y_mm','sc_z_mm','direct_pp_uls_N_mm','direct_pp_sls_N_mm','direct_brace_factor_uls','direct_brace_factor_sls'):
  if c[key] is not None:_number(c[key],key,nonnegative=key.startswith('direct_'))
 for key in ('load_y_from_CG_mm','load_z_from_CG_mm'):_number(c[key],key)
 for color in ('blue','green'):
  m=c[color]
  if not isinstance(m,dict) or set(m)!={'label','A_mm2','E_MPa','mass_kg_m','origin'}:raise ValueError('Perfil de barra inválido: '+color)
  for key in ('A_mm2','E_MPa'):_number(m[key],color+' '+key,positive=True)
  _number(m['mass_kg_m'],color+' massa',nonnegative=True)
  for key in ('label','origin'):
   if not isinstance(m[key],str) or not m[key].strip() or len(m[key])>2000:raise ValueError('Rótulo/origem do perfil de barra inválido.')
  nominal=defaults()[color]
  if any(m[key]!=nominal[key] for key in ('A_mm2','E_MPa','mass_kg_m')) and m['origin']==nominal['origin']:
   raise ValueError('Dados da barra '+color+' alterados: informe origem própria, sem atribuir o valor editado ao default Gerdau/E.')
 links=topology(c['tie_count']);arms=c['connection_arm_mm']
 if not isinstance(arms,list) or len(arms)!=3:raise ValueError('Braço comum deve conter três componentes.')
 arms=[_number(v,'Braço da ligação') for v in arms]
 if c['connection_mode']=='individual':
  offsets=c['connection_offsets']
  if not isinstance(offsets,dict) or set(offsets)!={x[0] for x in links}:raise ValueError('Informe os dois braços de cada barra do esquema ativo.')
  for key,value in offsets.items():
   if not isinstance(value,list) or len(value)!=2 or any(not isinstance(r,list) or len(r)!=3 for r in value):raise ValueError('Cada barra requer dois braços XYZ.')
   for r in value:
    for v in r:_number(v,'Braço individual')
 else:
  r=arms if c['connection_mode']=='common_arm' else [0.,0.,0.]
  offsets={key:[r[:],r[:]] for key,_,_,_ in links}
 c['resolved_offsets']=offsets
 return c


def readiness(data,c):
 missing=[]
 for key,label in [('geometry_declared','Declarar que distância entre travessas é também a distância entre eixos superior–central e central–inferior, com mesma seção/vão.'),
                   ('axial_bars_declared','Declarar idealização axial articulada T/C das barras redondas e cantoneiras.'),
                   ('connections_declared','Declarar posição/idealização das ligações e dos apoios.'),
                   ('load_line_declared','Declarar posição das cargas em relação ao centroide.')]:
  if not c[key]:missing.append(label)
 if not c['origin'].strip():missing.append('Informar origem/hipótese do modelo físico.')
 if c['sc_y_mm'] is None or c['sc_z_mm'] is None or not c['sc_origin'].strip():missing.append('Informar vetor CG→centro de cisalhamento e sua origem; x0 do catálogo não recebe sinal automático.')
 if data.get('load_mode')=='direct':
  for state in ('uls','sls'):
   if c['direct_pp_'+state+'_N_mm'] is None:missing.append('Declarar parcela de PP já combinada da travessa em '+state.upper()+' (zero somente se PP realmente ausente).')
   if c['brace_self_weight'] and c['direct_brace_factor_'+state] is None:missing.append('Declarar fator do PP das barras em '+state.upper()+'.')
 return missing


def load_cases(data,c):
 """Half EXTERNAL tributary actions; full PP of each equal girt and every bar."""
 def vectors(normal,parallel,pp):
  out=[];ey=c['load_y_from_CG_mm'];ez=c['load_z_from_CG_mm']
  for factor in (.5,1.,.5):
   ext_y=-factor*(parallel-pp);ext_z=-factor*normal;pp_y=-pp
   out.append(dict(q_y_N_mm=ext_y+pp_y,q_z_N_mm=ext_z,load_y_from_CG_mm=0.,load_z_from_CG_mm=0.,
                   distributed_torque_CG_N=ey*ext_z-ez*ext_y,
                   components=[dict(id='external',q_y_N_mm=ext_y,q_z_N_mm=ext_z,y_from_CG_mm=ey,z_from_CG_mm=ez),
                               dict(id='girt_PP',q_y_N_mm=pp_y,q_z_N_mm=0.,y_from_CG_mm=0.,z_from_CG_mm=0.)]))
  return out
 if data.get('load_mode')=='area':
  from .batch import area_bundle
  bundle=area_bundle(data);rows=[]
  for combo in bundle['combinations']:
   coef=combo['coefficients'];pp=coef.get('PP',0.)*bundle['case_vectors_N_mm']['PP']['parallel']
   normal=combo['q_vector']['normal'];parallel=combo['q_vector']['parallel']
   loads=vectors(normal,parallel,pp)
   rows.append(dict(combination=copy.deepcopy(combo),loads=loads,combined_girt_PP_N_mm=pp,brace_weight_factor=coef.get('PP',0.)))
  return rows,bundle
 if data.get('load_mode')!='direct':raise ValueError('Modo de cargas desconhecido.')
 rows=[]
 for state,label in [('uls','ELU'),('sls','ELS')]:
  for key in ('P_'+state,'P_parallel_'+state):
   if _number(data.get(key,0.),key)!=0:raise ValueError('Sistema 3D: ação concentrada ativa ('+key+') não implementada; não foi descartada.')
  normal=_number(data.get('q_'+state),'q '+label);parallel=_number(data.get('q_parallel_'+state,0.),'q vertical '+label)
  pp=_number(c['direct_pp_'+state+'_N_mm'],'PP combinado '+label,nonnegative=True)
  factor=c['direct_brace_factor_'+state] if c['brace_self_weight'] else 0.
  if c['brace_self_weight']:_number(factor,'Fator PP barras '+label,nonnegative=True)
  loads=vectors(normal,parallel,pp)
  rows.append(dict(combination=dict(id='DIRETO_'+label,type='Ações já combinadas',limit_state=label,expression=data.get('actions_origin',''),
                                   q_vector={'normal':normal,'parallel':parallel},coefficients=None),loads=loads,combined_girt_PP_N_mm=pp,brace_weight_factor=factor))
 return rows,None


def calculate(data):
 from .ue_reference import claims_reference
 from .ue_family_reference import claims_reference as family_claims
 if claims_reference(data) or family_claims(data):raise ValueError('Referência própria Ue restrita à terça de flexão: remova o vínculo por uma nova seleção explícita antes do diagnóstico 3D; entradas preservadas, sem migração automática.')
 from .application import fingerprint,VERSION,build_spec
 from .batch import area_bundle,case_inputs
 if not enabled(data):raise ValueError('O sistema 3D requer seleção explícita em Travessa lateral.')
 c=configuration(data)
 # Structural input contract is checked without evaluating the legacy response.
 if data.get('load_mode')=='area':
  b=area_bundle(data);build_spec(case_inputs(data,b['combinations'][0]))
 else:build_spec(data)
 result=dict(schema=SCHEMA,version=VERSION+' / three-girt-diagnostic-20261103',project=data.get('project',''),synthetic=data.get('synthetic',False),
             input_data=copy.deepcopy(data),input_fingerprint=fingerprint(data),configuration=c,status='not_solved',cases=[],
             physical_conditions_verified=False,resistance_qualified=False,ELS_qualified=False,whole_member_approved=False,
             limitations=LIMITATIONS[:],sources=copy.deepcopy(SOURCES),
             axis_convention='X: A→B; Y: vertical para cima; Z: horizontal para a direita na vista A→B; rotações pela mão direita. qY=−q paralelo e qZ=−q normal da interface. My é forte, Mz é fraco. N positivo tração.',
             support_convention='Seis extremos: ux=uy=uz=rx=0; ry e rz livres. Rotação de torção impedida não especifica empenamento.',
             topology_note='Verticais em cada linha; diagonais azuis dos extremos superiores à primeira/última linha central. Para n≠2 é extensão declarada do croqui; n=0 sem barras.',
             load_distribution='CP por área inclui o peso da telha/revestimento e demais permanentes informados, sem PP do perfil. Fatores de CP e vento superior/central/inferior = 0.5/1/0.5; PP de cada travessa integral aplicado no CG; ações externas na linha declarada. PP das barras, se ativo, integral e ponderado pelo coeficiente PP; metade em cada extremidade da barra. Nenhuma parcela é duplicada.',
             legacy_route_used=False)
 from .model_domain import evidence as domain_evidence
 result['model_domain_evidence']=domain_evidence(data)
 if result['model_domain_evidence']['conflict']:result['limitations'].append(result['model_domain_evidence']['conflict'])
 missing=readiness(data,c)
 if missing:result.update(reason='Premissas explícitas pendentes; não calculado.',missing=missing);return result
 p=data['properties'];spacing=_number(data['area_inputs']['spacing_m'],'Distância entre travessas',positive=True)*1000
 s=dict(A_mm2=_number(p['A_cm2'],'A',positive=True)*100,I_strong_mm4=_number(p['Ix_cm4'],'Ix',positive=True)*1e4,
        I_weak_mm4=_number(p['Iy_cm4'],'Iy',positive=True)*1e4,J_mm4=_number(p['J_mm4'],'J',positive=True),
        E_MPa=_number(p['E_MPa'],'E',positive=True),G_MPa=_number(p['G_MPa'],'G',positive=True),
        sc_y_mm=c['sc_y_mm'],sc_z_mm=c['sc_z_mm'],origin=data['property_origin']+'; SC: '+c['sc_origin'])
 lc,bundle=load_cases(data,c)
 for row in lc:
  model=solve_three_girts(L_mm=data['L_mm'],upper_gap_mm=spacing,lower_gap_mm=spacing,attachment_x_mm=c['resolved_positions_mm'],
                         section=s,blue=c['blue'],green=c['green'],loads=row['loads'],axial_restraint='both_ends',
                         connection_offsets=c['resolved_offsets'],include_green=True,brace_self_weight=c['brace_self_weight'],brace_weight_factor=row['brace_weight_factor'])
  result['cases'].append(dict(row,model=model))
 result['status']='conditional_elastic_diagnostic' if all(x['model']['status']=='conditional_elastic_diagnostic' for x in result['cases']) else 'not_solved'
 if result['status']=='not_solved':result['reason']='Ao menos uma combinação não passou o gate numérico; consultar cada caso. Não existe fallback para vão livre.'
 result['load_bundle']=bundle
 result['inactive_legacy_fields']=['segments','weak_axis','weak_catalog','route_domain','Ml_Nmm','Mdist_Nmm','wall_tie_study','wall_els']
 return result
