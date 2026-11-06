"""Separate catalogue-Ue EN choices and snapshot-only UI/Word output."""
import copy
from . import isolated_en_ue_catalog_application as a
from .presentation import display_frame,fmt

LABEL='Verificar cortantes e M–V EN do contorno Ue atual'
DECLARATION='Adotar seção nominal Ue intacta, sem furos ou recortes'
ORIGIN='Origem do modelo nominal intacto Ue'
TITLE='Cortantes e M–V EN — contorno próprio Ue de catálogo'


def render_choice(st,data,key):
    if 'ue_catalog_reference' not in data and a.CHOICE not in data:return
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
        st.caption('Shear lag e curling são conferidos pelo perfil e pelo diagrama de cada caso, sem declaração técnica substitutiva. '
            'Material resistente EN: fyb=fya=250 MPa, E=210000 MPa, ν=0,3, γM0=1. Rigidez E/G das ações permanece a do projeto.')


def rows(ev):
    out=[]
    for r in ev['records']:
        c=r['check'];v=c['shear'] if c else {};m=c['mv'] if c else {}
        out.append({'Combinação':r['combination_id'],'Teto cortante forte EN':v.get('strong_ratio_upper'),
            'Teto cortante fraco EN':v.get('weak_ratio_upper'),
            'Cortantes':('Suficiente para os dois cortantes' if v['component_sufficient'] else 'Inconclusivo pelo teto') if c else 'Pendente',
            'Teto M–V EN6.27':m.get('index_upper'),
            'M–V':('Suficiente na componente' if m['component_sufficient'] else 'Pendente' if m['index_upper'] is None else 'Inconclusivo pelo teto') if c else 'Pendente',
            'Motivo':m.get('reason') or r.get('reason')})
    return out


def text_lines(ev):
    return [a.SCOPE,'Modelo nominal intacto: '+ev['configuration']['model_origin'],
        f"{ev['shear_computed_cases']} casos ELU com os dois cortantes calculados; {ev['shear_sufficient_cases']} suficientes. "
        f"M–V: {ev['mv_computed_cases']} calculados, {ev['mv_sufficient_cases']} suficientes e {ev['mv_pending_cases']} pendentes. "
        f"{ev['ELS_cases_excluded']} casos ELS fora da componente.",
        'Nos casos calculados, N=0 é comprovado na fonte, os momentos físicos são assinados e iguais aos originais. A cobertura exigida inclui todo trecho e ambos os lados de P, inclusive a→0+ quando declarado. '
        'Não há crédito de reserva de mesa Mf nem cancelamento favorável N·e.',
        'Pisos de resistência de inventários EN independentes para a mesma identidade nominal/contorno. '
        'Resistência EN fixa: fyb=fya=250 MPa, E=210000 MPa, ν=0,3, γM0=1. Material E/G da análise guardado separadamente, sem conversão.',
        'Critérios de aplicabilidade exigidos: shear lag com Le>50b0 em toda zona entre zeros reais do momento, sem cortar a zona artificialmente em P; curling com teto de deslocamento dos painéis <5% da altura associada. Não satisfazer a guarda mantém M–V pendente. '
        'Ramo assinado requerido ausente deixa M–V pendente, sem índice. Cortante permanece independente.',
        'EN6.1.6 e efeitos de B/Tsv/Tw NÃO estão resolvidos para estes 83 perfis. Nenhum resultado dos sete Ue100 é transferido. '
        'Visualizar e exportar confere apenas snapshots e aritmética, sem solver nem reconstrução de seção.']


def show(st,result):
    try:ev=a.preserved(result)
    except (ValueError,TypeError,KeyError) as e:st.warning('EN Ue salvo inválido: '+str(e));return
    if ev is None:return
    st.subheader(TITLE)
    for line in text_lines(ev):st.caption(line)
    st.dataframe(display_frame(rows(ev)),hide_index=True,width='stretch')


def report(doc,result):
    try:ev=a.preserved(result)
    except (ValueError,TypeError,KeyError) as e:
        doc.add_heading('EN Ue salvo inválido',1);doc.add_paragraph(str(e)+' Nenhum índice emitido.');return
    if ev is None:return
    doc.add_heading(TITLE,1)
    for line in text_lines(ev):doc.add_paragraph(line)
    for r in rows(ev):doc.add_paragraph(' | '.join(k+': '+(fmt(v) if type(v) in (int,float) else str(v)) for k,v in r.items() if v is not None))
    doc.add_paragraph('Snapshot torsional de origem: '+ev['source_torsion_snapshot_sha256'])
