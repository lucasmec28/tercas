"""Whole-span length extension of the closed homogeneous reference contract.

The section/local FSM vector is immutable. Effective lengths are declared inputs,
not inferred supports. Only explicit application writes derived input values.
"""
import copy
import math

FIELD = 'homogeneous_lengths'
VERSION = 'homogeneous_whole_span_lengths_20261103_r1'
REPORTING_VERSION = 'homogeneous_length_derivation_20261103_r1'
SPAN_ORIGIN = ('Sem travamento intermediário nesta idealização: comprimentos iguais ao vão, '
               'Kx=Ky=Kz=1, garfos matemáticos e empenamento livre. Não qualifica ligações reais.')
LIMIT = ('Esforços e flechas continuam os de uma viga biapoiada inteira, sem novos apoios. '
         'Lx/Ly/Lz de estabilidade não criam tirantes, molas, rigidez ou vínculos no modelo de ações. '
         'Comprimentos distintos são aplicação algébrica normativa a valores declarados, '
         'não solução modal de um arranjo de vínculos fisicamente comprovado. '
         'Ly é comum aos dois sentidos fortes nesta extensão. Kx=Ky=Kz=1, Cb=Cm=1; '
         'empenamento livre, cargas no CT ou hipótese aplicável sem efeito desestabilizante. '
         'Sem crédito da telha e sem verificação de torção primária ou resistência 3D; sem aprovação global.')
FROZEN_SCOPE = ('Geometria, propriedades próprias de seção, aço e críticos locais FSM por sentido '
                'permanecem congelados. Nex/Ney/Nez e Mcr são derivados dos comprimentos atuais; '
                'não se reutilizam os Ne de 3 m após mudar comprimentos. Um único trecho [0,L]; '
                'não há segmentação nem inferência de contraventamento.')
SOURCES = ('NBR 14762:2010 §9.7.2.1, p41–42/PDF47–48; §9.8.2.2, p48/PDF54; '
           'Anexo E.2, p82/PDF88. Kz=1 na ausência de impedimento garantido ao empenamento. '
           'Esta extensão adota K=1 sobre as distâncias destravadas declaradas; não reduz K×L abaixo delas. '
           'A ressalva normativa sobre redução do comprimento efetivo abaixo da distância destravada '
           'não é uma exigência nova para toda distância menor que o vão. O registro da origem das '
           'distâncias não comprova o arranjo, rigidez ou compatibilidade física dos vínculos.')


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' deve ser positivo e finito.')
    return float(value)


def configuration(L, config):
    L=positive(L, 'Vão L')
    if not isinstance(config, dict):raise ValueError('Contrato de comprimentos inválido.')
    mode=config.get('mode')
    keys={'schema','mode','origin'} | ({'Lx_effective_mm','Ly_effective_mm','Lz_effective_mm'} if mode=='declared' else set())
    if config.get('schema')!=VERSION or mode not in ('span','declared') or set(config)!=keys:
        raise ValueError('Contrato de comprimentos desconhecido/incompleto; sem fatores K reduzidos ou segmentação.')
    origin=config.get('origin')
    if not isinstance(origin,str) or not origin.strip() or len(origin)>2000:
        raise ValueError('Informe a origem/justificativa dos comprimentos declarados (até 2000 caracteres).')
    lengths={axis:L if mode=='span' else positive(config[axis+'_effective_mm'],axis+' efetivo') for axis in ('Lx','Ly','Lz')}
    return {'L_mm':L,'mode':mode,'origin':origin,'lengths':lengths}


def global_criticals(data, config=None):
    """Ne from fixed section data; existing Annex E implementation for both signs."""
    cfg=configuration(data['L_mm'],data[FIELD] if config is None else config)
    p=data['properties'];weak=data['weak_axis'];r0=weak['positive']['r0_mm']
    E,G,Ix,Iy,J,Cw=(p['E_MPa'],p['G_MPa'],p['Ix_cm4']*1e4,p['Iy_cm4']*1e4,p['J_mm4'],p['Cw_mm6'])
    lx,ly,lz=(cfg['lengths'][k] for k in ('Lx','Ly','Lz'))
    nx=math.pi**2*E*Ix/lx**2
    ny=math.pi**2*E*Iy/ly**2
    torsion=G*J+math.pi**2*E*Cw/lz**2
    nz=torsion/r0**2
    # Same evaluation order as the existing strong FLT routine, Cb=1.
    strong=math.pi/ly*math.sqrt(E*Iy*torsion)
    from .inclination import annex_e_critical
    values={'Nex_N':nx,'Ney_N':ny,'Nez_N':nz,'torsion_modal_stiffness_Nmm2':torsion,'Me_strong_Nmm':strong}
    for sign in ('positive','negative'):
        s=weak[sign]
        values['Me_weak_'+sign+'_Nmm']=annex_e_critical(Nex_N=nx,Nez_N=nz,r0_mm=r0,j_mm=s['j_mm'],Cs=s['Cs'],Cm=1.,provenance=cfg['origin'])['Me_Nmm']
    if any(not math.isfinite(v) or v<=0 for v in values.values()):raise ValueError('Comprimentos fora da faixa numérica do cálculo; nenhum valor derivado foi aplicado.')
    return values


def _number_text(value):return format(float(value),'.15g')


def expected_inputs(canonical, L, config, *, current=None):
    """Construct exact expected derivatives, without modifying the supplied object.

    Used for validation and for explicit user application. Never call it as an
    import repair; imported values must already equal all expected derivatives.
    """
    cfg=configuration(L,config)
    out=copy.deepcopy(canonical if current is None else current)
    out['L_mm']=cfg['L_mm'];out[FIELD]=copy.deepcopy(config)
    # Compute from the immutable section/local vector, never from old Ne.
    model=copy.deepcopy(canonical);model['L_mm']=cfg['L_mm'];model[FIELD]=copy.deepcopy(config)
    values=global_criticals(model)
    lx,ly,lz=(cfg['lengths'][k] for k in ('Lx','Ly','Lz'))
    description=('Vão biapoiado inteiro L='+_number_text(L)+' mm; Kx=Ky=Kz=1; '
                 'Lx='+_number_text(lx)+', Ly comum='+_number_text(ly)+', Lz='+_number_text(lz)+' mm. '
                 'Cb=Cm=1; empenamento livre. Distâncias de estabilidade não criam apoios ou tirantes. Origem: '+cfg['origin'])
    out['segments']=[{'start_mm':0.,'end_mm':cfg['L_mm'],'Ly_top_effective_mm':ly,
                      'Ly_bottom_effective_mm':ly,'Lz_effective_mm':lz,'Cb_mode':'one',
                      'restraint_provenance':description}]
    out['support_origin']=canonical['support_origin']+' Vão inteiro atual; sem apoios intermediários no cálculo de esforços/flechas.'
    out['weak_axis']=copy.deepcopy(canonical['weak_axis'])
    for item in out['weak_axis'].values():
        item.update(Nex_N=values['Nex_N'],Nez_N=values['Nez_N'])
        item['provenance']+=' Ne recalculados de E/Ix/G/J/Cw/r0 próprios pelos comprimentos atuais. '+description
    # Chosen benchmark criterion, not a universal normative requirement.
    denominator=canonical['ELS_down_denominator']
    out['ELS_limit_mm']=cfg['L_mm']/denominator
    out['ELS_origin']='L/'+_number_text(denominator)+' escolhido para teste no modo direto, atualizado com o vão; não prescrição universal.'
    return out


def apply_lengths(data, *, L_mm, mode='span', origin=None, Lx_mm=None, Ly_mm=None, Lz_mm=None):
    """Explicit UI/API action. Absolute P coordinates and all actions are kept."""
    from .homogeneous_reference import assess, source
    state=assess(data)
    if not state['active']:raise ValueError('Ative uma referência própria íntegra antes de editar comprimentos.')
    config={'schema':VERSION,'mode':mode,'origin':SPAN_ORIGIN if mode=='span' and origin is None else origin}
    if mode=='declared':config.update(Lx_effective_mm=Lx_mm,Ly_effective_mm=Ly_mm,Lz_effective_mm=Lz_mm)
    return expected_inputs(source(state['reference_id']),L_mm,config,current=data)


def scope_text(base_scope):
    return base_scope.replace('L e comprimentos efetivos=3000 mm, Cb=Cm=1, N=0.',
                              'vão e comprimentos de estabilidade registrados na derivação atual, Cb=Cm=1, N=0.')


def evidence(data, canonical):
    cfg=configuration(data['L_mm'],data[FIELD]);same=all(v==cfg['L_mm'] for v in cfg['lengths'].values())
    return {'schema':VERSION,'mode':cfg['mode'],'L_mm':cfg['L_mm'],'effective_lengths_mm':cfg['lengths'],
            'origin':cfg['origin'],'Kx':1.,'Ky':1.,'Kz':1.,'Cb':1.,'Cm':1.,
            'global_criticals':global_criticals(data),'sources':SOURCES,'scope':LIMIT,
            'interpretation':('Comprimentos iguais ao vão: formulação da barra inteira com garfos ideais e empenamento livre, sob hipóteses declaradas.' if same else
                              'Comprimentos distintos do vão: somente aplicação algébrica normativa a valores declarados; não valida uma solução modal física do arranjo de vínculos.'),
            'all_effective_lengths_equal_span':same,'physical_restraints_verified':False,
            'primary_torsion_checked':False,'whole_member_approved':False,
            'section_data_unchanged':True,'new_supports_created_in_demand_model':False,
            'P_direct_policy':'Coordenadas absolutas preservadas. Fora de [0,L], corrigir explicitamente antes de calcular modo direto.',
            'ELS_criteria':{'direct_denominator':canonical['ELS_down_denominator'],'direct_limit_mm':data['ELS_limit_mm'],
                            'area_down_denominator':data['ELS_down_denominator'],'area_up_denominator':data['ELS_up_denominator'],
                            'area_down_limit_mm':data['L_mm']/data['ELS_down_denominator'],
                            'area_up_limit_mm':data['L_mm']/data['ELS_up_denominator'],
                            'scope':'Razões escolhidas para teste, não prescrição universal. Ief combinado/flecha fraca e ELS completo não qualificados.'},
            'baseline_reference_span_mm':canonical['L_mm'],
            'baseline_restraint_provenance':canonical['segments'][0]['restraint_provenance']}


def report(doc, record):
    """Historical output uses recorded derivation, not current recomputation."""
    item=record.get('global_length_derivation')
    if not item:return
    from .presentation import fmt
    doc.add_heading('Vão e comprimentos de estabilidade — derivação registrada',2)
    doc.add_paragraph('Vão biapoiado inteiro: '+fmt(item['L_mm'])+' mm. Comprimentos de estabilidade: '+
                      '; '.join(k+'='+fmt(v)+' mm' for k,v in item['effective_lengths_mm'].items())+'. Kx=Ky=Kz=1; Cb=Cm=1.')
    for key in ('origin','interpretation','scope','sources','P_direct_policy'):doc.add_paragraph(item[key])
    for key,value in item['global_criticals'].items():doc.add_paragraph(key+': '+fmt(value))
    els=item['ELS_criteria'];doc.add_paragraph('Limite ELS direto registrado: '+fmt(els['direct_limit_mm'])+' mm; L/'+fmt(els['direct_denominator'])+'. '+els['scope'])
    doc.add_paragraph('As propriedades e críticos locais da referência própria permanecem os mesmos; os Ne e Mcr acima são derivados do contrato atual, não novas propriedades de seção. A origem dos vínculos da referência original de 3 m não é transferida como comprovação física dos comprimentos declarados.')
