"""Separate catalogue-Ue EN choices and snapshot-only UI/Word output."""
import copy
from . import isolated_en_ue125_300_application as a
from .presentation import display_frame,fmt

LABEL='Verificar tensões, cortantes e M–V EN do Ue125 fy300'
DECLARATION='Adotar seção nominal Ue125 fy300 intacta, sem furos ou recortes'
ORIGIN='Origem do modelo nominal intacto Ue125 fy300'
TITLE='EN seccional — Ue125x50x17x2 ri2, fy300'


def render_choice(st,data,key):
    if a.CHOICE not in data and not (data.get('ue_catalog_reference',{}).get('catalog_index')==26 and data.get('properties',{}).get('fy_MPa')==300.):return
    try:changed=a.reset_changed_declaration(data);c=a.configuration(data)
    except ValueError as e:st.warning(str(e));return
    with st.expander(TITLE,expanded=False):
        st.caption(a.SCOPE)
        if changed:st.info('Seção/material mudou: declaração e origem anteriores foram retiradas.')
        key+='_'+a.identity(data)[:16]
        enabled=st.checkbox(LABEL,value=bool(c and c['enabled']),key=key+'_enabled')
        if c is None and not enabled:return
        c=copy.deepcopy(c) if c else a.choice(data);c['enabled']=enabled;data[a.CHOICE]=c
        if not enabled:return
        c['intact_section_model_declared']=st.checkbox(DECLARATION,value=c['intact_section_model_declared'],key=key+'_intact')
        c['model_origin']=st.text_input(ORIGIN,value=c['model_origin'],key=key+'_origin')
        reason=a._domain(data,c)
        if reason:st.warning(reason)
        else:data[a.CHOICE]=a.activate(data,model_origin=c['model_origin'])[a.CHOICE]
        st.caption('Shear lag e curling são conferidos pelo perfil e pelo diagrama de cada caso, sem declaração técnica substitutiva. '
            'Material resistente EN: fyb=fya=300 MPa, E=210000 MPa, ν=0,3, γM0=1. Rigidez E/G das ações permanece a do projeto.')


def rows(ev):
    out=[]
    for r in ev['records']:
        c=r.get('check') or {};stress=c.get('stress',{});v=c.get('shear',{});m=c.get('mv',{})
        row={'Combinação':r['combination_id']}
        for k,label in [('normal','normal'),('shear','cisalhamento concomitante'),('interaction','interação σ–τ')]:
            cr=stress.get('criteria',{}).get(k,{})
            row['Teto '+label+' EN6.1.6']=cr.get('index_upper_bound')
        row.update({'Tensões EN6.1.6':(('Excesso normal observado no modelo linear; aplicabilidade pendente' if not c.get('applicability',{}).get('qualified',True) else 'Excesso normal observado no modelo linear') if stress.get('criteria',{}).get('normal',{}).get('observed_exceedance') else 'Suficiente no campo declarado' if stress.get('section_stress_criteria_sufficiently_satisfied') else 'Inconclusivo ou fora de aplicabilidade') if stress else 'Pendente',
            'Teto cortante forte EN':v.get('strong_ratio_upper'),'Teto cortante fraco EN':v.get('weak_ratio_upper'),
            'Teto M–V EN6.27':m.get('index_upper'),
            'M–V EN6.27':('Suficiente na componente' if m.get('component_sufficient') else 'Pendente' if m.get('index_upper') is None else 'Inconclusivo pelo teto'),
            'Motivo':(('Uma testemunha concomitante prova |σ|>300 MPa no campo linear; não é máximo físico nem validação da primeira ordem. '+('Aplicabilidade pendente: '+str(c.get('applicability',{}).get('reason')) if not c.get('applicability',{}).get('qualified',True) else '')) if stress.get('criteria',{}).get('normal',{}).get('observed_exceedance') else r.get('reason') or m.get('reason') or c.get('applicability',{}).get('reason'))})
        out.append(row)
    return out


def text_lines(ev):
    lines=[a.SCOPE,'Modelo nominal intacto: '+ev['configuration']['model_origin'],
        'Resistência EN: fyb=fya=300 MPa, E=210000 MPa, ν=0,3, γM0=1. Análise: E=200000 MPa, G=77000 MPa; aço nominal fy=300/fu=400 MPa. Não há conversão do material nem alteração de cargas ou rigidez.',
        '§6.1.6: |σ|≤300 MPa, |τ|≤300/√3 MPa e √(σ²+3τ²)≤330 MPa, no mesmo estado com B/Tsv/Tw. Os três limites são independentes.',
        '§6.1.10, Eq.6.27: M–V com N=0, Mf=0, pisos resistentes EN independentes e cortantes forte/fraco. Não exige torção nula nem converte T em V.',
        'Os tetos numéricos não são estados físicos: teto acima de 1 sozinho é inconclusivo. Excesso normal observado exige testemunha física concomitante, reavaliada com intervalo dirigido e |σ| inferior estritamente acima de 300 MPa. Isso descreve o campo linear, não seu máximo nem a validade física da primeira ordem. Shear lag e curling continuam separados.',
        f"{ev['computed_cases']} casos ELU calculados; {ev['pending_demand_cases']} pendentes; {ev['ELS_cases_excluded']} casos ELS excluídos.",
        'Avisos de giro linear alto e pequenas rotações da análise permanecem válidos: índice seccional não aprova a resposta física nem o elemento.',
        'JSON preserva autoridade original, demanda, denominadores e controles. Leitura e Word validam snapshots sem solver ou construtor de seção.']
    normal=ev.get('normal_snapshot',{})
    if normal:
        floors={k:v['first_yield_capacity_floor'] for k,v in normal['components'].items()}
        lines.append('Denominadores mínimos de flexão EN por sentido [N·mm]: '+str(floors)+'.')
    for r in ev['records']:
        c=r.get('check') or {}
        if c:
            lines.append('Denominadores mínimos dos cortantes EN [N], caso '+r['combination_id']+': '+str(c['shear_source_snapshot']['shear_capacity_lower_N'])+'.')
    candidates=[(r['combination_id'],r['check']['mv']['index_upper']) for r in ev['records'] if r.get('check') and r['check']['mv']['index_upper'] is not None]
    if candidates:
        cid,index=max(candidates,key=lambda x:x[1]);lines.append(f'Caso governante do teto M–V EN6.27: {cid}; índice {index:.6g}.')
    for criterion in ('normal','shear','interaction'):
        controls=[(r['combination_id'],r['check']['stress']['criteria'][criterion]['index_upper_bound'])
            for r in ev['records'] if r.get('check')]
        if controls:
            cid,index=max(controls,key=lambda x:x[1])
            lines.append(f'Caso governante do teto {criterion} EN6.1.6: {cid}; índice {index:.6g}.')
    if not ev['ELU_cases']:lines.append('Nenhum caso ELU selecionado: nenhuma condição seccional foi qualificada.')
    if ev.get('reason'):lines.append(ev['reason'])
    for r in ev['records']:
        c=r.get('check') or {}
        if c:
            lines.append('Caso '+r['combination_id']+': autoridade normal '+str(c.get('normal_source_sha256'))+'.')
            normal=c.get('stress',{}).get('criteria',{}).get('normal',{})
            witness=normal.get('physical_witness')
            if normal.get('observed_exceedance') and witness:
                lines.append('Excesso normal observado no modelo linear / '+r['combination_id']+
                    ': |σ| ≥ '+fmt(witness['absolute_sigma_lower_MPa'],limit=300.)+' MPa > 300 MPa. '
                    'Uma testemunha, não o máximo físico: '+str(witness['location'])+
                    '; parede '+str(witness['wall_segment'])+'; face '+str(witness['face'])+
                    '; parâmetro da parede '+str(witness['wall_parameter'])+
                    '; σ intervalar [MPa] '+str(witness['sigma_interval_MPa'])+
                    '; operadores pelo sinal real '+str(witness['selected_operators'])+'.')
            if not c.get('applicability',{}).get('qualified',True):
                lines.append('Aplicabilidade seccional pendente / '+r['combination_id']+': '+str(c['applicability']['reason']))
            for name,criterion in c.get('stress',{}).get('criteria',{}).items():
                lines.append('Controle '+name+' / '+r['combination_id']+': '+str(criterion.get('bound_control')))
    return lines


def show(st,result):
    try:ev=a._presentation_view(result)
    except (ValueError,TypeError,KeyError) as e:st.warning('EN Ue salvo inválido: '+str(e));return
    if ev is None:return
    st.subheader(TITLE)
    for line in text_lines(ev):st.caption(line)
    st.dataframe(display_frame(rows(ev)),hide_index=True,width='stretch')


def report(doc,result):
    try:ev=a._presentation_view(result)
    except (ValueError,TypeError,KeyError) as e:
        doc.add_heading('EN Ue salvo inválido',1);doc.add_paragraph(str(e)+' Nenhum índice emitido.');return
    if ev is None:return
    doc.add_heading(TITLE,1)
    for line in text_lines(ev):doc.add_paragraph(line)
    for r in rows(ev):doc.add_paragraph(' | '.join(k+': '+(fmt(v) if type(v) in (int,float) else str(v)) for k,v in r.items() if v is not None))
    doc.add_paragraph('Snapshot torsional de origem: '+ev['source_torsion_snapshot_sha256'])
