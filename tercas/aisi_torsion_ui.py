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
            'Parcela longitudinal':('Condição algébrica H4 satisfeita, sob hipóteses declaradas' if h['ratio']<=1 else 'Piso não demonstra H4; resultado inconclusivo') if h else 'H4 pendente',
            'x H4 [mm]':h['witness']['x_mm'] if h else None,
            'Dados ausentes':'; '.join(record['missing'])})
        if evidence.get('roof_height_source'):
            roof=record.get('roof_height') or {};cap=roof.get('strong_capacity');m=roof.get('Mcre')
            out[-1].update({'Mcre AISI [kN·m]':m['Me_Nmm']/1e6 if m and m.get('Me_Nmm') is not None else None,
                'Ma,piso AISI [kN·m]':cap['Ma_floor_Nmm']/1e6 if cap else None,
                'Máx. |giro| AISI [rad]':record.get('AISI_analysis',{}).get('max_abs_phi_rad'),
                'Primeira ordem física':'Adequação não estabelecida',
                'Aviso de giro':record.get('first_order_small_rotation_warning')})
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
        if ev.get('roof_height_source'):
            source=ev['roof_height_source']
            lines.extend([source['model'],source['adequacy_note'],source['interpretation']])
            lines.append('Mcre e Ma,piso calculados para cada ELU, em material nominal AISI, sem usar Me/MRd NBR e sem novo Cb. PP permanece no CG; forças externas no topo. Torque primário e avisos preservados. Flexão fraca real mantém H4 pendente; não se transfere o denominador fraco no CT.')
            lines.append('Geometria, linha de aplicação e garfos são hipóteses explícitas do esquema, não comprovação das ligações/forças reais. P conserva posições prescritas e limite analítico no apoio; não se declara envelope móvel. A escolha física do esquema existente basta; nenhum Me ou Cb é solicitado.')
        else:
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
    with st.expander('Memória G8.1/H4, capacidades e estados concomitantes',expanded=False):
        if result.get('schema')=='tercas_three_girt_results_v1' or result.get('input_data',{}).get('member_application','purlin')!='purlin':st.json(ev)
        else:st.caption('As capacidades e todos os estados estão preservados no arquivo JSON. Em “Memória numérica e rastreabilidade”, selecione explicitamente uma combinação para consultar o registro AISI salvo, sem novo cálculo.')


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
        doc.add_paragraph(' | '.join(k+': '+(('Sim' if v else 'Não') if isinstance(v,bool) else fmt(v) if isinstance(v,(int,float)) else str(v)) for k,v in row.items() if v is not None))
    doc.add_paragraph('Fonte primária: '+ev['reference'])
