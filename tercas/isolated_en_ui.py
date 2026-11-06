"""Explicit section model choice and snapshot-only EN display/Word."""
import copy
from . import isolated_en_application as a
from .presentation import display_frame,fmt

LABEL='Verificar tensões combinadas e cisalhamento torsional (EN)'
DECLARATION='Adotar seção nominal intacta, sem furos ou recortes, neste complemento EN'
ORIGIN='Origem/hipótese do modelo de seção intacta EN'
TITLE='Tensões combinadas e cisalhamento torsional — complemento EN'


def render_choice(st,data,key):
    own=isinstance(data.get('ue_family_reference'),dict) or isinstance(data.get('ue_reference'),dict)
    if not own and a.CHOICE not in data:return
    if data.get('member_application','purlin')!='purlin':
        if a.CHOICE in data:st.caption('Complemento EN isolado inativo nesta aplicação; a rede tem sua verificação própria.')
        return
    try:
        changed=a.reset_changed_declaration(data);c=a.configuration(data)
    except ValueError as exc:
        st.warning(str(exc));return
    with st.expander('Complemento EN — torção e interação de tensões',expanded=False):
        st.caption(a.SCOPE)
        if changed:st.info('Seção/material mudou: opção preservada, declaração e origem retiradas. Declare novamente para a seção atual.')
        # Identity belongs to widget keys too, so a previous checkbox cannot re-adopt another profile.
        key+='_'+a.identity(data)[:16]
        enabled=st.checkbox(LABEL,value=bool(c and c['enabled']),key=key+'_enabled')
        if c is None and not enabled:return
        c=copy.deepcopy(c) if c is not None else a.choice(data)
        c['enabled']=enabled;data[a.CHOICE]=c
        if not enabled:
            st.caption('Opção desativada; declaração salva preservada. Históricos não são recalculados.')
            return
        c['intact_section_model_declared']=st.checkbox(DECLARATION,
            value=c['intact_section_model_declared'],key=key+'_intact')
        c['model_origin']=st.text_input(ORIGIN,value=c['model_origin'],key=key+'_origin')
        reason=a._domain_reason(data,c)
        if reason:st.warning('Complemento EN pendente: '+reason)
        st.caption('Somente Ue100 próprio, N=0, fyb=fya=250 MPa e ELU. Seções efetivas EN; '
            'E=210000 MPa e γM0=1 no critério, sem alterar E/G das ações calculadas. '
            'O modelo Vlasov e suas linhas de carga precisam estar disponíveis. '
            'Flambagem por cisalhamento, interação N–M–V, estabilidade e ELS permanecem separados.')


def rows(ev):
    out=[]
    for row in ev['records']:
        check=row['check'];criteria=check['criteria'] if check else {}
        out.append({'Combinação':row['combination_id'],
            'Teto normal EN':criteria.get('normal',{}).get('index_upper_bound'),
            'Teto cisalhamento EN':criteria.get('shear',{}).get('index_upper_bound'),
            'Teto interação σ–τ EN':criteria.get('interaction',{}).get('index_upper_bound'),
            'Componente de tensões':('Suficiente no campo declarado' if check['section_stress_criteria_sufficiently_satisfied']
                else 'Inconclusivo pelo teto; não é reprovação') if check else 'Pendente',
            'Motivo':row.get('reason') or ''})
    return out


def text_lines(ev):
    c=ev['configuration']
    lines=[a.SCOPE,'Modelo de seção nominal intacta: '+c['model_origin'],
        'Três limites independentes: |σ| ≤ 250 MPa; |τ| ≤ 144,337567 MPa; sqrt(σ²+3τ²) ≤ 275 MPa. '
        'A folga 1,1 da interação não relaxa os outros dois limites.',
        'As duas faces e todo o campo longitudinal são cobertos. O controle de Bernstein é um limite numérico, '
        'não um estado físico de tensões. Nenhum teto acima de 1 é rotulado como falha.',
        'Nesta rota isolada N=0. As tensões normais de flexão usam seções efetivas EN; B/V/Tsv/Tw usam a seção bruta coerente. Material EN fixo: '
        'fyb=fya=250 MPa, E=210000 MPa, ν=0,3, γM0=1. E/G da análise e combinações originais são preservados.',
        'Não conclui flambagem por cisalhamento EN6.1.5, redução N–M–V EN6.1.10, estabilidade, '
        'adequação da primeira ordem, forças locais, ligações ou ELS.',
        f"{ev['computed_cases']} casos ELU calculados; {ev['pending_cases']} pendentes; {ev['ELS_cases_excluded']} casos ELS fora deste critério."]
    if ev.get('reason'):lines.append(ev['reason'])
    return lines


def show(st,result):
    try:ev=a.preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.error('Registro EN isolado inválido: '+str(exc));return
    if ev is None:return
    st.subheader(TITLE)
    for line in text_lines(ev):st.caption(line)
    if ev['records']:st.dataframe(display_frame(rows(ev)),hide_index=True,width='stretch')
    st.caption('Memória e fontes preservadas no JSON. Visualizar ou exportar não executa novo cálculo.')


def report(doc,result):
    try:ev=a.preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_heading('Complemento EN isolado — registro inválido',1)
        doc.add_paragraph(str(exc)+' Nenhum índice EN desse registro foi emitido.');return
    if ev is None:return
    doc.add_heading(TITLE,1)
    for line in text_lines(ev):doc.add_paragraph(line)
    for row in rows(ev):
        doc.add_paragraph(' | '.join(k+': '+(fmt(v) if type(v) in (int,float) else str(v))
            for k,v in row.items() if v is not None))
    doc.add_paragraph('Fonte: EN1993-1-3:2006 §6.1.6(3)–(5), pp.46–47. '
        'Fonte geométrica própria: '+str(ev.get('source_profile',{}).get('profile_id','pendente'))+'. '
        'Hash do snapshot torsional: '+ev['source_torsion_snapshot_sha256']+'.')
