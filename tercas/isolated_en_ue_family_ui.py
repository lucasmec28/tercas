"""Explicit family selection and validated, parameterized UI/Word views."""
import copy
from . import isolated_en_ue_family_application as a
from .presentation import display_frame,fmt
TITLE='EN seccional — família Ue Pierin completa'
LABEL='Usar a nova rota EN da família Ue'
DECLARATION='Adotar seção nominal intacta, sem furos/recortes'
ORIGIN='Origem do modelo nominal intacto'


def render_choice(st,data,key):
    if 'ue_catalog_reference' not in data and a.CHOICE not in data:return
    try:changed=a.reset_changed_declaration(data);c=a.configuration(data)
    except ValueError as e:st.warning(str(e));return
    with st.expander(TITLE,expanded=False):
        st.caption(a.SCOPE)
        if changed:st.info('Seção/material mudou: declare novamente o modelo nominal intacto.')
        key+='_'+a.identity(data)[:16]
        enabled=st.checkbox(LABEL,value=bool(c and c['enabled']),key=key+'_enabled')
        if c is None and not enabled:return
        c=copy.deepcopy(c) if c else a.choice(data);c['enabled']=enabled;data[a.CHOICE]=c
        if not enabled:return
        st.caption('γM0=1,0: escolha própria desta versão EN, independente de γ NBR. Outro γ permanece pendente até extensão da normalização do método.')
        c['intact_section_model_declared']=st.checkbox(DECLARATION,value=c['intact_section_model_declared'],key=key+'_intact')
        c['model_origin']=st.text_input(ORIGIN,value=c['model_origin'],key=key+'_origin')
        reason=a._domain(data,c)
        if reason:st.warning(reason)
        else:
            updated=a.activate(data,model_origin=c['model_origin'],gamma_M0=c['gamma_M0'])
            for k in ('isolated_en_ue125_300_model','isolated_en_ue_catalog_model','isolated_en_stress_model'):data.pop(k,None)
            data[a.CHOICE]=updated[a.CHOICE]
        st.caption('fyb=fya nominal declarado, sem encruamento; E resistente=210000 MPa e ν=0,3. E/G da demanda não são alterados. Ramos sem operador ficam pendentes apenas quando necessários ao caso.')


def rows(ev):
    out=[]
    for r in ev['records']:
        c=r.get('check') or {};s=c.get('stress',{});v=c.get('shear',{});m=c.get('mv',{})
        row={'Combinação':r['combination_id'],'Estado':('Parcial: '+str(c['component_status']) if c and 'pending' in c['component_status'].values() else r['status'])}
        for k,label in [('normal','normal'),('shear','cisalhamento concomitante'),('interaction','σ–τ')]:
            row['Teto EN6.1.6 '+label]=s.get('criteria',{}).get(k,{}).get('index_upper_bound')
        row.update({'Tensões suficientes':s.get('section_stress_criteria_sufficiently_satisfied',False),
            'Teto cortante forte':v.get('strong_ratio_upper'),'Teto cortante fraco':v.get('weak_ratio_upper'),
            'Teto M–V EN6.27':m.get('index_upper'),'M–V suficiente':m.get('component_sufficient',False),
            'Motivo':r.get('reason') or m.get('reason')})
        out.append(row)
    return out


def text_lines(ev):
    mat=ev['material'];limit=mat['fya_MPa']/mat['gamma_M0']
    lines=[a.SCOPE,'Modelo nominal intacto: '+ev['configuration']['model_origin'],
        f"Resistência EN: fyb=fya={mat['fyb_MPa']:g} MPa; γM0={mat['gamma_M0']:g}; E=210000 MPa; ν=0,3. Rigidez E/G e cargas da análise original preservadas.",
        f'EN6.1.6: |σ|≤{limit:g} MPa; |τ|≤{limit:g}/√3 MPa; √(σ²+3τ²)≤{1.1*limit:g} MPa. Limites independentes, no mesmo campo B/Tsv/Tw.',
        'EN6.1.10/6.27: quatro momentos independentes por sentido, N=0, Mf=0; cortantes forte/fraco. Torção não é convertida em V.',
        'Teto acima de 1 é inconclusivo. Testemunha física concomitante pode provar excesso no campo linear, não seu máximo nem validade da primeira ordem. Shear lag/curling são verificados separadamente.',
        f"Cortante calculado: {ev['shear_computed_cases']}; tensões calculadas: {ev['stress_computed_cases']}; M–V calculado: {ev['mv_computed_cases']}. Casos parciais: {ev['partial_cases']}; demanda pendente: {ev['pending_demand_cases']}; ELS excluídos: {ev['ELS_cases_excluded']}.",
        'Giro alto, estabilidade global e ELS combinado permanecem separados. Nenhuma aprovação de barra ou adequação física da primeira ordem.',
        'Leitura autentica fórmulas/dados atuais e repete a aritmética vinculada à demanda original; não resolve novo modelo de membro.']
    normal=ev.get('normal_snapshot',{})
    if normal:lines.append('Aço declarado: '+str(normal.get('material_declaration'))+'. Conformidade de produto/ductilidade não verificada por um valor numérico de fy.')
    for name,component in normal.get('components',{}).items():
        lines.append(f"{name}: piso [N·mm] {component.get('first_yield_capacity_floor')}; elegível={component['eligible']}; motivos={component.get('blocking_reasons',[])}.")
    for row in ev['records']:
        c=row.get('check')
        if not c:lines.append(row['combination_id']+': '+str(row.get('reason')));continue
        lines.append(row['combination_id']+': cortantes mínimos [N] '+str(c['shear_source_snapshot']['shear_capacity_lower_N'])+'.')
        for name,criterion in c['stress']['criteria'].items():
            lines.append(row['combination_id']+' / '+name+': '+criterion['criterion']+'; controle '+str(criterion.get('bound_control')))
            witness=criterion.get('physical_witness')
            if witness:lines.append('Testemunha concomitante: |σ|≥'+str(witness['absolute_sigma_lower_MPa'])+' MPa; limite '+str(witness['normal_limit_MPa'])+' MPa; localização '+str(witness['location'])+'.')
        if not c['applicability']['qualified']:lines.append('Aplicabilidade pendente: '+c['applicability']['reason'])
    return lines


def show(st,result):
    try:ev=a._presentation_view(result)
    except (ValueError,TypeError,KeyError) as e:st.warning('EN família salvo inválido: '+str(e));return
    if ev is None:return
    st.subheader(TITLE)
    for line in text_lines(ev):st.caption(line)
    st.dataframe(display_frame(rows(ev)),hide_index=True,width='stretch')


def report(doc,result):
    try:ev=a._presentation_view(result)
    except (ValueError,TypeError,KeyError) as e:
        doc.add_heading('EN família salvo inválido',1);doc.add_paragraph(str(e)+' Nenhum índice emitido.');return
    if ev is None:return
    doc.add_heading(TITLE,1)
    for line in text_lines(ev):doc.add_paragraph(line)
    for row in rows(ev):doc.add_paragraph(' | '.join(k+': '+(fmt(v) if type(v) in (int,float) else str(v)) for k,v in row.items() if v is not None))
