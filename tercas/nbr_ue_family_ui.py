"""Shared UI/Word view of validated family component evidence."""
from .nbr_ue_family_application import preserved, SCOPE

TITLE = 'NBR — componentes da família Ue completa'
ROUTES = {'published_nominal_reference': 'Referência nominal publicada', 'own_rounded_contour': 'Contorno próprio'}
NOTE = ('Referência publicada: Wx de catálogo + críticos Pierin inalterados, sem identidade de contorno comprovada. '
        'Contorno próprio: métodos e limites explícitos. Em avaliações v3, lacunas locais de My negativo usam RP23-01 Eq28–30, aproximação publicada com curva NBR; MLE tem prioridade. ri/t=1 não herda a precisão da amostra nem garantia conservadora. Na referência documental nova, FLT com altura e FLT clássico '
        'usam os comprimentos resistentes declarados; esforços mantêm L físico. Casos antigos conservam seu método. '
        'Nos novos estudos, q+P usa o Ritz existente somente com Ly=Lz=L e projeção paralela elegível; alturas individuais são preservadas. '
        'Pisos resistentes por energia/aproximação: índice acima de 1 é inconclusivo, não reprovação. '
        'Índice parcial não é aprovação resistente/global. Denominadores antigos não são alterados.')


def rows(evidence):
    return [dict(Combinação=r['combination_id'], Fonte=ROUTES[c['route']], Método=c['method'],
        Eixo={'normal': 'forte', 'parallel': 'fraco'}[c['demand']['axis']], Sinal=c['demand']['sign'] or 'ambos',
        Resistência_Nmm=c['capacity_Nmm'], Momento_Nmm=c['demand']['Msd_Nmm'],
        Índice=c['index'], Índice_diagnóstico_sem_qualificação=c.get('unqualified_diagnostic_index'), Aproximação=c.get('approximate',False),
        Situação=c['reference_comparison'] or c['status'], Motivo=c['reason'])
        for r in evidence['records'] for c in r['components']]


def coverage_summary(evidence):
    return 'Cobertura: ' + '; '.join(
        key + ': ' + str(value['indexed_cases']) + '/' + str(value['total_ELU_cases'])
        + ' ELU com índice, ' + str(value.get('not_applicable_cases', 0))
        + ' dispensados/não aplicáveis, ' + str(value['pending_cases']) + ' pendentes'
        for key, value in evidence.get('method_coverage', {}).items())


def interaction_rows(evidence):
    rows=[]
    for row in evidence['records']:
        ev=row.get('member_interaction')
        if ev is None:continue
        g=ev['arithmetic']['governing']
        rows.append(dict(Combinação=row['combination_id'],Índice=None if g is None else g['index_upper'],
            Posição_mm=None if g is None else g['x_mm'],Situação=ev['criterion_status'] or ev['status'],
            Motivo=('Piso insuficiente; não prova reprovação.' if ev['status']=='inconclusive_resistance_floor'
                else '; '.join(ev['missing'])),Aproximação_elástica=ev['approximate_elastic_references']))
    return rows


def web_rows(evidence):
    out=[]
    for row in evidence['records']:
        e=row.get('strong_web_MV')
        if e is None:continue
        a=e['arithmetic'];v=e['web_shear']
        out.append(dict(Combinação=row['combination_id'],Índice_V_superior=v['index_upper'],
            Situação_V=v['criterion_status'],Índice_MV_quadrático_superior=None if a is None else a['index_squared_upper'],
            Situação_MV=e['criterion_status'] or e['status'],Motivo='; '.join(e['missing'])))
    return out


def show(st, result):
    try:
        evidence = preserved(result)
    except (ValueError, KeyError, TypeError) as exc:
        st.warning('Componentes NBR da família não exibidas: ' + str(exc)); return
    if evidence is None:
        return
    st.subheader(TITLE)
    st.caption(SCOPE)
    st.caption(NOTE)
    if evidence['pending_reason']:
        st.warning(evidence['pending_reason'])
    st.caption(coverage_summary(evidence))
    st.dataframe(rows(evidence), use_container_width=True)
    if interaction_rows(evidence):
        st.caption('Interação NBR9.9 N=0: máximo contínuo concomitante por eixo/sinal; capacidades da mesma seção. Torção, cortantes e serviço separados.')
        st.dataframe(interaction_rows(evidence),use_container_width=True)
    if web_rows(evidence):
        st.caption('NBR9.8.3/9.8.4: cortante forte da alma e soma quadrática M–V concomitante. MRd local, sem substituir por FLT/D; cortante fraco e torção separados.')
        st.dataframe(web_rows(evidence),use_container_width=True)


def report(doc, result):
    try:
        evidence = preserved(result)
    except (ValueError, KeyError, TypeError) as exc:
        doc.add_paragraph('Componentes NBR da família não exibidas: ' + str(exc)); return
    if evidence is None:
        return
    doc.add_heading(TITLE, 1)
    doc.add_paragraph(SCOPE)
    doc.add_paragraph(NOTE)
    doc.add_paragraph(coverage_summary(evidence))
    if evidence['pending_reason']:
        doc.add_paragraph(evidence['pending_reason'])
    table = doc.add_table(rows=1, cols=6)
    for cell, text in zip(table.rows[0].cells, ['Caso', 'Fonte / método', 'MRd (Nmm)', 'Msd (Nmm)', 'Índice', 'Situação / motivo']):
        cell.text = text
    from docx.table import _Cell
    for row in rows(evidence):
        values = [row['Combinação'], row['Fonte'] + ' / ' + row['Método'], row['Resistência_Nmm'],
                  row['Momento_Nmm'], row['Índice'],
                  ('Referência aproximada. ' if row['Aproximação'] else '') + row['Situação'] + ': ' + row['Motivo']]
        for tc, value in zip(table.add_row()._tr.tc_lst, values):
            cell = _Cell(tc, table)
            cell.text = '—' if value is None else format(value, '.6g') if isinstance(value, (float, int)) else str(value)
    if interaction_rows(evidence):
        doc.add_paragraph('Interação NBR9.9 N=0: máximo contínuo concomitante por eixo/sinal; torção, cortantes e serviço separados.')
        for row in interaction_rows(evidence):
            doc.add_paragraph('; '.join(str(k)+': '+str(v) for k,v in row.items()))
    if web_rows(evidence):
        doc.add_paragraph('Cortante forte da alma e interação NBR9.8.4 com MRd local próprio; cortante fraco e torção separados.')
        for row in web_rows(evidence):
            doc.add_paragraph('; '.join(str(k)+': '+str(v) for k,v in row.items()))
