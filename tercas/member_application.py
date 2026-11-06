"""Explicit purlin/girt orientation and bounded, non-design vertical studies.

Legacy inputs without member_application remain purlins. No table resistance,
sheeting restraint or unqualified weak critical is introduced here.
"""
import copy,math

KINDS=('purlin','wall_girt')
ELS_DEFAULTS={'normal_denominator':120.,'vertical_denominator':180.,
              'normal_reference_mm':None,'vertical_reference_mm':None,
              'origin':'Critérios declarados no estudo; conferir aplicação. Referência histórica CBCA/Gerdau, não nova prescrição normativa.'}

def member_kind(data):
 value=data.get('member_application','purlin')
 if not isinstance(value,str) or value not in KINDS:
  raise ValueError('Aplicação inválida: selecione Terça ou Travessa lateral.')
 return value

def is_girt(data):return member_kind(data)=='wall_girt'

def _positive(value,name):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
  raise ValueError(name+': informe número positivo e finito.')
 return float(value)

def wall_els_config(data):
 supplied=data.get('wall_els',{})
 if not isinstance(supplied,dict) or set(supplied)-set(ELS_DEFAULTS):
  raise ValueError('Configuração ELS da travessa inválida.')
 cfg=dict(ELS_DEFAULTS,**supplied)
 for key in ('normal_denominator','vertical_denominator'):_positive(cfg[key],key)
 for key in ('normal_reference_mm','vertical_reference_mm'):
  cfg[key]=data['L_mm'] if cfg[key] is None else cfg[key];_positive(cfg[key],key)
 if not isinstance(cfg['origin'],str) or not cfg['origin'].strip():raise ValueError('Informe a origem/aplicação dos limites ELS da travessa.')
 return cfg

def tie_config(data):
 cfg=data.get('wall_tie_study',{})
 allowed={'enabled','anchorage_confirmed','origin','springs'}
 if not isinstance(cfg,dict) or set(cfg)-allowed:raise ValueError('Configuração do estudo de tirantes inválida.')
 out=dict(enabled=False,anchorage_confirmed=False,origin='',springs=[]);out.update(copy.deepcopy(cfg))
 if any(not isinstance(out[k],bool) for k in ('enabled','anchorage_confirmed')):raise ValueError('Opções de tirantes devem ser booleanas.')
 if not isinstance(out['origin'],str):raise ValueError('Origem do estudo de tirantes deve ser texto.')
 if not isinstance(out['springs'],list) or len(out['springs'])>20:raise ValueError('Use até 20 molas neste estudo elástico da implementação.')
 for spring in out['springs']:
  if not isinstance(spring,dict) or set(spring)!={'x_mm','k_N_mm','origin'}:raise ValueError('Cada tirante requer x_mm, k_N_mm e origem.')
  _positive(spring['x_mm'],'Posição do tirante');_positive(spring['k_N_mm'],'Rigidez do tirante')
  if spring['x_mm']>=data['L_mm']:raise ValueError('O tirante deve estar no interior do vão.')
  if not isinstance(spring['origin'],str) or not spring['origin'].strip():raise ValueError('Informe a origem/hipótese de cada rigidez.')
 return out

def validate(data):
 from .deflection_scope import enabled as uniaxial_component_enabled
 uniaxial_component_enabled(data)
 kind=member_kind(data)
 if kind=='wall_girt':
  _positive(data.get('L_mm'),'Vão do modelo');wall_els_config(data);tie_config(data)
 return kind

def normal_els_limit(data):
 cfg=wall_els_config(data)
 return {'value':cfg['normal_reference_mm']/cfg['normal_denominator'],
         'origin':cfg['origin']+'; perpendicular ao fechamento, Lref='+str(cfg['normal_reference_mm'])+' mm / '+str(cfg['normal_denominator'])+'. Lref não altera o vão do modelo ou FLT.'}

def wall_angle():return {'radians':math.pi/2,'degrees':90.,'percent':None}

def wall_convention():
 return ('Travessa lateral, vista A→B: U/Ue com boca para baixo e alma horizontal acima. '
         '+paralelo é vertical para baixo (flexão fraca, My positivo/alma comprimida no vão livre); '
         '+normal é horizontal para a esquerda nesta vista (flexão forte). '
         'Vento± normal ao fechamento; PP/permanentes verticais. Sem crédito de travamento do fechamento. '
         'Orientação não comprova carga no CT nem ausência de torção primária.')

def adapt_wall_bundle(data,bundle):
 from .inclination import simply_supported_state
 from .load_combinations import uniform_effects
 a=data['area_inputs'];g=9.80665/1000.;width=a['spacing_m']
 cases={'PP':{'normal':0.,'parallel':data['properties']['mass_kg_m']*g},
        'CP':{'normal':0.,'parallel':a['permanent_kgf_m2']*width*g},
        'SC':{'normal':0.,'parallel':0.},
        'V_Cima':{'normal':-a['wind_up_kgf_m2']*width*g,'parallel':0.},
        'V_Baixo':{'normal':a['wind_down_kgf_m2']*width*g,'parallel':0.}}
 bundle.update(member_application='wall_girt',inclination={'configuration':{'orientation':'mouth_down','area_basis':'wall_plane'},'angle':wall_angle()},case_vectors_N_mm=cases,
               case_q_N_mm={k:v['normal'] for k,v in cases.items()},
               case_effects_at_midspan={k:uniform_effects(v['normal'],data['L_mm']) for k,v in cases.items()})
 bundle['inactive_roof_inputs']={'live_kgf_m2':a['live_kgf_m2'],'inclination':copy.deepcopy(data.get('inclination',{})),'automatic_maintenance_P':False}
 for c in bundle['combinations']:
  if 'SC' in c['coefficients'] or 'P' in c['coefficients']:raise ValueError('Travessa por área: combinação de cobertura não aplicável neste cenário.')
  q={axis:math.fsum(c['coefficients'].get(k,0.)*v[axis] for k,v in cases.items()) for axis in ('normal','parallel')}
  p={'normal':0.,'parallel':0.};L=data['L_mm'];mid=simply_supported_state(L,L/2,q,p,L/2)['normal']
  c.update(q_N_mm=q['normal'],q_kN_m=q['normal'],P_N=0.,q_vector=q,P_vector=p,
           sign='normal positiva' if q['normal']>0 else 'normal negativa' if q['normal']<0 else 'normal nula',
           origin=c['origin']+'; subconjunto sem SC/P de cobertura para a travessa declarada; coeficientes da matriz do usuário, não gerador normativo universal',
           effects_at_midspan={'left_reaction_N':mid['Rleft_N'],'right_reaction_N':mid['Rright_N'],'V_N':mid['V_N'],'M_Nmm':mid['M_Nmm'],'midspan_moment_Nmm':mid['M_Nmm'],'max_abs_shear_N':max(abs(mid['Rleft_N']),abs(mid['Rright_N']))})
 bundle['notes']=[wall_convention(),
  'Cenário declarado sem SC usual e P de manutenção de cobertura: somente linhas da matriz original sem SC; P automática não adicionada. Ações especiais devem ser avaliadas e, quando aplicável, informadas em componentes já combinadas no modo direto.',
  'Valores de SC/inclinação da Terça ficam armazenados, porém inativos na Travessa. Área e distância referem-se ao plano do fechamento; CP não repete PP.',
  'L do modelo, Lref dos limites ELS e comprimentos efetivos de estabilidade são independentes. Tirantes não reduzem nenhum deles automaticamente.']
 return bundle

def add_vertical_studies(result):
 """Gross elastic diagnostic only; never infer Ief or replace strength demands."""
 from .direct_self_weight import calculation_inputs
 d=calculation_inputs(result['input_data']);cfg=wall_els_config(d);ties=tie_config(d)
 q=d.get('q_parallel_sls',0.);P=d.get('P_parallel_sls',0.);fields=result['input_snapshot']['selected_section']['fields']
 scope='Componente vertical elástica com Iy bruto, não Ief qualificado nem aprovação ELS. Não altera esforços resistentes, FLT ou Lref.'
 common={'scope':scope,'uses_effective_inertia':False,'usable_for_design_approval':False,
         'L_model_mm':d['L_mm'],'L_reference_mm':cfg['vertical_reference_mm'],
         'declared_limit_mm':cfg['vertical_reference_mm']/cfg['vertical_denominator'],
         'limit_origin':cfg['origin'],'index':None}
 if q==0 and P==0:
  base=dict(common,status='not_applicable',reason='Sem ação vertical na combinação ELS.');result['elastic_vertical']=base
 else:
  try:
   from .weak_vertical_elastic import study_weak_vertical
   Iy=fields['Iy_cm4']['value'];E=fields['E_MPa']['value']
   if Iy is None or E is None:raise ValueError('E ou Iy bruto ausente.')
   model=study_weak_vertical(L=d['L_mm'],E=E,Iy=Iy*1e4,q=q,P=P,a=d['x_sls'])
   base=dict(common,status='gross_elastic_diagnostic',model=model);result['elastic_vertical']=base
  except (ValueError,TypeError,ArithmeticError,OverflowError) as exc:
   result['elastic_vertical']=dict(common,status='not_evaluated',reason=str(exc))
 if not ties['enabled']:return
 study=dict(common,status='not_evaluated',hypothesis=copy.deepcopy(ties),strength_model_unchanged=True)
 if not ties['anchorage_confirmed'] or not ties['origin'].strip():
  study['reason']='Estudo não executado: declarar hipótese de ancoragem fixa e origem/caminho das rigidezes. Existência de linha de tirantes não comprova esse apoio.'
 elif not ties['springs']:study['reason']='Estudo ativado, mas nenhuma rigidez/posição de tirante foi informada.'
 else:
  try:
   from .weak_vertical_elastic import study_weak_vertical
   Iy=fields['Iy_cm4']['value'];E=fields['E_MPa']['value']
   if Iy is None or E is None:raise ValueError('E ou Iy bruto ausente.')
   model=study_weak_vertical(L=d['L_mm'],E=E,Iy=Iy*1e4,q=q,P=P,a=d['x_sls'],
             springs=[dict(x=s['x_mm'],k=s['k_N_mm'],origin=s['origin']) for s in ties['springs']])
   study.update(status='conditional_elastic_tie_study',model=model)
   study['warning']='Hipótese de molas verticais em estrutura fixa, tração apenas, sem folga/pré-tensão. Menor flecha não valida tirantes. Momentos podem inverter; a redistribuição NÃO foi incorporada às verificações resistentes do vão livre.'
  except (ValueError,TypeError,ArithmeticError,OverflowError) as exc:study['reason']=str(exc)
 result['elastic_tie_study']=study

def vertical_row(result):
 r=result['elastic_vertical'];model=r.get('model',{});maximum=model.get('deflection_max_abs',{})
 status='Não aplicável' if r['status']=='not_applicable' else 'Parcial — diagnóstico bruto; Ief vertical não qualificado'
 return {'Verificação':'Flecha vertical — eixo fraco','Situação':status,'Índice':None,
         'Demanda / valor':('—' if not maximum else f"Bruta: {maximum['value_mm']:.6f} mm em x={maximum['x_mm']:.3f} mm"),
         'Resistência / limite':f"Critério declarado {r['declared_limit_mm']:.6f} mm; não confrontado com flecha efetiva",
         'Referência':'Modelo elástico Euler–Bernoulli; critério informado, sem conclusão ELS',
         'Observação':r.get('reason','')+' '+r['scope']+' '+r['limit_origin']}
