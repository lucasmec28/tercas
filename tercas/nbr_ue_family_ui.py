"""Shared UI/Word view of validated family component evidence."""
from .nbr_ue_family_application import preserved, SCOPE

TITLE = 'NBR — componentes da família Ue completa'
ROUTES = {'published_nominal_reference': 'Referência nominal publicada', 'own_rounded_contour': 'Contorno próprio'}
NOTE = ('Referência publicada: Wx de catálogo + críticos Pierin inalterados, sem identidade de contorno comprovada. '
        'Contorno próprio: métodos e limites explícitos. FLT com altura usa L físico; FLT clássico usa comprimentos '
        'resistentes. Índice parcial não é aprovação resistente/global. Denominadores antigos não são alterados.')


def rows(evidence):
    return [dict(Combinação=r['combination_id'], Fonte=ROUTES[c['route']], Método=c['method'],
        Eixo={'normal': 'forte', 'parallel': 'fraco'}[c['demand']['axis']], Sinal=c['demand']['sign'] or 'ambos',
        Resistência_Nmm=c['capacity_Nmm'], Momento_Nmm=c['demand']['Msd_Nmm'],
        Índice=c['index'], Situação=c['reference_comparison'] or c['status'], Motivo=c['reason'])
        for r in evidence['records'] for c in r['components']]


def coverage_summary(evidence):
    return 'Cobertura: ' + '; '.join(
        key + ': ' + str(value['indexed_cases']) + '/' + str(value['total_ELU_cases'])
        + ' ELU com índice, ' + str(value.get('not_applicable_cases', 0))
        + ' dispensados/não aplicáveis, ' + str(value['pending_cases']) + ' pendentes'
        for key, value in evidence.get('method_coverage', {}).items())


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
                  row['Momento_Nmm'], row['Índice'], row['Situação'] + ': ' + row['Motivo']]
        for tc, value in zip(table.add_row()._tr.tc_lst, values):
            cell = _Cell(tc, table)
            cell.text = '—' if value is None else format(value, '.6g') if isinstance(value, (float, int)) else str(value)
