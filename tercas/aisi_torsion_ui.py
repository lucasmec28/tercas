"""Read-only presentation of the separately saved current-input AISI component."""
from .aisi_torsion_component import preserved, SCOPE, LIMITS, FIELD
from .presentation import display_frame,fmt


def rows(evidence):
    out=[]
    for record in evidence['records']:
        g=record.get('G81');h=record.get('H4')
        out.append({'Combinação':record['combination_id'],
            'G8.1 |B|/Ba':g['ratio'] if g else None,
            'H4 Mx/Max + My/May + B/Ba':h['ratio'] if h else None,
            'Parcela longitudinal':('Satisfaz H4 no modelo declarado' if h['ratio']<=1 else 'Piso não demonstra H4; resultado inconclusivo') if h else 'H4 pendente',
            'x H4 [mm]':h['witness']['x_mm'] if h else None,
            'Dados ausentes':'; '.join(record['missing'])})
    return out


def text_lines(ev):
    lines=[SCOPE,LIMITS,ev['load_basis'],ev['resistance_basis'],ev['implemented_domain']]
    if ev.get('reason'):lines.append(ev['reason'])
    if ev.get('capacity_missing'):lines.append('Capacidade G8.1 ausente: '+ev['capacity_missing'])
    cap=ev.get('bimoment_capacity')
    if cap:
        lines.append('G8.1: By='+fmt(cap['By_Nmm2'])+' N·mm²; φB=0,90; Ba='+fmt(cap['Ba_Nmm2'])+' N·mm². Bp e Bcr não são exigidos nesta opção.')
    if ev.get('analysis_material'):
        mat=ev['material'];analysis=ev['analysis_material'];old=ev['original_analysis_material']
        lines.append('Complemento independente: capacidades com E='+fmt(mat['E_MPa'])+' MPa, G='+fmt(mat['G_MPa'])+' MPa e Fy='+fmt(mat['Fy_MPa'])+' MPa. '+
            'Análise com 0,90 das rigidezes: Ea='+fmt(analysis['E_MPa'])+' MPa e Ga='+fmt(analysis['G_MPa'])+' MPa. '+
            'O fator de rigidez não é aplicado novamente à resistência. φb=φB=0,90, uma única vez.')
        lines.append('Análise NBR preservada: E='+fmt(old['E_MPa'])+' MPa e G='+fmt(old['G_MPa'])+' MPa. Mesmas ações, posições, geometria e vínculos declarados; nenhum PP acrescentado.')
        lines.append('H4: envelope longitudinal concomitante no campo existente, com pisos algébricos AISI F2/F3/F4 como denominadores. My físico positivo comprime lábios; negativo comprime alma. '+
            'F4 não aplicável na alma refere-se somente à capacidade de flexão fraca pura; não é dispensa para o campo misto.')
        lines.append('As excentricidades declaradas geram torque em relação ao centro de cisalhamento na configuração inicial. As forças mantêm direção fixa. Mcre dos denominadores é de flexão pura Cb=1, não um crítico do campo misto com altura de carga; efeitos geométricos de altura/Wagner não estão incluídos.')
        lines.append('Primeira ordem racional, membro isolado N=0: não há efeitos P–δ/P–Δ de força axial. Não declara certificação estrutural C1.2/C1.3. '+
            'O aviso de giro do diagnóstico existente permanece triagem, não limite normativo adicional.')
    lines.append(str(ev['G81_computed_cases'])+' casos ELU com G8.1; '+str(ev['H4_computed_cases'])+' com H4; '+str(ev['pending_cases'])+' pendentes. ELS não é verificado por H4.')
    return lines


def _saved(result):
    if result.get(FIELD) is not None and not isinstance(result[FIELD],dict):
        raise ValueError('Registro do complemento deve ser um objeto de memória.')
    return preserved(result)


def show(st,result):
    try:ev=_saved(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.error('Registro do complemento AISI inválido: '+str(exc))
        return
    if ev is None:return
    st.subheader('Verificação complementar de flexão e empenamento — critério AISI 2024')
    lines=text_lines(ev)
    st.warning(lines[0])
    for line in lines[1:]:st.caption(line)
    if ev['records']:st.dataframe(display_frame(rows(ev)),hide_index=True,width='stretch')
    with st.expander('Memória G8.1/H4, capacidades e estados concomitantes',expanded=False):st.json(ev)


def report(doc,result):
    try:ev=_saved(result)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_heading('Complemento AISI — registro inválido',1)
        doc.add_paragraph('Registro do complemento AISI inválido: '+str(exc)+' Nenhum índice AISI desse registro foi emitido.')
        return
    if ev is None:return
    doc.add_heading('Verificação complementar de flexão e empenamento — critério AISI 2024',1)
    for line in text_lines(ev):doc.add_paragraph(line)
    for row in rows(ev):
        doc.add_paragraph(' | '.join(k+': '+(fmt(v) if isinstance(v,(int,float)) else str(v)) for k,v in row.items() if v is not None))
    doc.add_paragraph('Fonte primária: '+ev['reference'])
