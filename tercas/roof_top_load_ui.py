"""Explicit roof load-height scheme; no automatic restraint or domain credit."""
import copy
import html
import math

from .roof_top_load import FIELD, configuration, choice, geometry, preserved
from .presentation import display_frame, fmt

LABEL = 'Esquema da carga da cobertura'
OPTIONS = ('legacy', 'web_midplane', 'flange_midwidth')
LABELS = {
    'legacy': 'Legado — sem modelo de carga no topo',
    'web_midplane': 'Carga no topo — plano médio da alma',
    'flange_midwidth': 'Carga no topo — meio da largura da mesa',
}
ASSUMPTIONS = ('Modelo adotado: garfos nas extremidades, empenamento livre, sem travamentos intermediários. '
               'A telha não fornece rigidez lateral nem torsional. A escolha não comprova a ligação física.')
SCOPE = ('Me é um crítico elástico de FLT do modelo de carga no topo, não momento resistente, '
         'capacidade à torção ou aprovação global da terça. O núcleo calcula a componente forte; '
         'a interação NBR §9.9 usa resistências por eixo quando a posição das ações fracas permite.')

DIRECT_ASSUMPTIONS = (
    'Ao escolher este esquema no modo direto, adota-se a envoltória conservadora escalar de Me: '
    'q/P locais já combinados, com PP já incluído, são representados integralmente no topo selecionado, '
    'mantendo o mesmo momento fletor. Nenhum PP é quantificado ou adicionado. '
    'Hipóteses: contribuição normal do PP não negativa (gravidade usual, inclusive zero); '
    'demais forças na linha de topo selecionada; flexão uniaxial sem ações paralelas ocultas que se cancelem. '
    'Vale para resultante de gravidade ou sucção. Componente paralela resultante não nula permanece pendente.'
)
DIRECT_SCOPE = (
    'A envoltória é somente de Me elástico, não de torção, torque, bimomento ou aprovação global. '
    'Torção e H4 permanecem pendentes sem a decomposição das ações.'
)


def _direct_evidence(evidence):
    return evidence.get('load_basis') == 'direct_total_top_envelope'


def _finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def diagram(g, data):
    """Schematic only: do not fabricate a centroid or shear-centre location."""
    from .direct_self_weight import active as pp_active
    direct = data.get('load_mode') == 'direct' and not pp_active(data)
    h, bf = g.get('h_mm'), g.get('bf_mm')
    if not all(_finite(v) and v > 0 for v in (h, bf)):
        raise ValueError('Dimensões da seção não disponíveis para desenho.')
    # Midline outline is deliberately labelled schematic, not a section mesh.
    left, right, top, bottom = 60., 220., 75., 255.
    mid = (top + bottom) / 2
    load_x = left if g.get('load_line') == 'web_midplane' else (left + right) / 2
    lip = data.get('properties', {}).get('lip')
    path = f'M{right},{top} H{left} V{bottom} H{right}'
    if _finite(lip) and lip > 0:
        path = f'M{right},{top + min(55,180*lip/h)} V{top} H{left} V{bottom} H{right} V{bottom-min(55,180*lip/h)}'
    aria = ('Esquema da envoltória: carga total combinada representada no topo; PP já incluído' if direct
            else 'Esquema da seção com carga da cobertura no topo e peso próprio separado no CG')
    top_label = 'Total combinado: substituto no topo' if direct else 'Cobertura: ponto no topo selecionado'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{aria}" viewBox="0 0 720 330" style="width:100%;max-width:800px;background:#f8fafc;font-family:Arial,sans-serif">',
        '<text x="16" y="20" font-size="13">Seção local esquemática, sem escala; abertura à direita</text>',
        f'<path d="{path}" fill="none" stroke="#475569" stroke-width="5"/>',
        f'<path d="M{load_x},35 V{top-7} m-5,-8 l5,8 l5,-8" fill="none" stroke="#2563eb" stroke-width="2"/>',
        f'<circle cx="{load_x}" cy="{top}" r="5" fill="#2563eb"/>',
        f'<text x="300" y="65" font-size="13" fill="#2563eb">{top_label}</text>',
        '<text x="300" y="88" font-size="12">Seta ilustrativa; sucção inverte a força.</text>']
    midpoint = g.get('web_midplane_to_flange_midwidth_mm')
    width = 2*midpoint if _finite(midpoint) and midpoint > 0 else bf
    load_physical_x = g.get('load_x_from_web_midplane_mm')
    cg_offset = g.get('x_from_CG_mm')
    if direct:
        out.extend(['<text x="300" y="140" font-size="13">PP já incluído no total informado.</text>',
                    '<text x="300" y="160" font-size="12">Não é quantificado nem adicionado.</text>'])
    elif _finite(cg_offset) and _finite(load_physical_x):
        cg_x = left + (load_physical_x-cg_offset)/width*(right-left)
        out.extend([f'<circle cx="{cg_x}" cy="{mid}" r="5" fill="#15803d"/>',
                    f'<path d="M{cg_x},{mid+6} v25 m-5,-8 l5,8 l5,-8" fill="none" stroke="#15803d" stroke-width="2"/>',
                    '<text x="300" y="140" font-size="13" fill="#15803d">PP do perfil: CG, separado da cobertura</text>'])
    else:
        out.append('<text x="300" y="140" font-size="13" fill="#92400e">PP: CG; posição horizontal não qualificada</text>')
        out.append('<text x="300" y="160" font-size="12">CG não desenhado por falta de dado coerente.</text>')
    for i,(label,value) in enumerate((('Altura acima do centro de cisalhamento [mm]',g.get('height_above_SC_mm')),('x da carga a partir do CG [mm]',cg_offset),('x da carga a partir do CC [mm]',g.get('x_from_SC_mm')))):
        out.append(f'<text x="300" y="{202+22*i}" font-size="11">{html.escape(label)}: {html.escape(fmt(value) if _finite(value) else "não qualificado")}</text>')
    footer = ('Substituto conservador apenas para Me; não representa o torque real.' if direct
              else 'PP não é deslocado ao topo. Telha sem crédito de travamento.')
    out.append(f'<text x="16" y="310" font-size="12">{footer}</text></svg>')
    return ''.join(out)


def render_choice(st, data, key):
    current = configuration(data)
    if data.get('member_application', 'purlin') != 'purlin':
        if current is not None:st.caption('Modelo de carga no topo da cobertura inativo nesta aplicação; configuração armazenada preservada.')
        return
    selected = current.get('load_line') if current and current.get('enabled') else 'legacy'
    with st.expander('FLT — cobertura aplicada no topo', expanded=True):
        value = st.selectbox(LABEL, OPTIONS, index=OPTIONS.index(selected), format_func=LABELS.get, key=key)
        if value == 'legacy':
            if current is not None and current.get('enabled'):
                updated = copy.deepcopy(current);updated['enabled'] = False;data[FIELD] = updated
            st.caption('Sem novo modelo adotado. Entradas e rota legadas são preservadas.')
            return
        # Rendering an absent field never activates a model; only explicit selection does.
        if value != selected:data[FIELD] = choice(value)
        st.caption(ASSUMPTIONS)
        st.warning(SCOPE)
        from .direct_self_weight import active as pp_active
        if data.get('load_mode') == 'direct' and not pp_active(data):
            st.caption(DIRECT_ASSUMPTIONS)
            st.caption(DIRECT_SCOPE)
            st.info('As entradas diretas já estão nos eixos locais e não são giradas novamente. '
                    'A inclinação, isoladamente, não impede esta envoltória. Gravidade inclinada com '
                    'ações paralelas ocultas ou canceladas não está qualificada por esta idealização; '
                    'o acoplamento de flexão nos dois eixos e torção exige outro modelo.')
        else:
            st.caption('CP, SC, vento e manutenção no topo selecionado; PP do perfil no CG, uma única vez. '
                       'A carga na mesa pode gerar torção primária; este componente não verifica essa resistência.')
            inclination = data.get('inclination', {})
            if inclination.get('value') not in (None, 0, 0.):
                st.info('Inclinação: gravidade e PP podem produzir componente paralela. A interação NBR §9.9 usa '
                        'resistências por eixo quando cada ação fraca está no CT ou em posição estabilizante. '
                        'Posição fraca desestabilizante ou desconhecida permanece pendente. '
                        'Não se calcula autovalor biaxial nem se encerra torção/empenamento.')
        st.caption('Os controles legados de Cb e comprimentos não definem os vínculos deste modelo separado.')
        try:
            g = geometry(data)
            st.markdown(diagram(g, data), unsafe_allow_html=True)
            st.caption('Fonte da geometria: '+str(g.get('source', 'não informada')))
            if not g.get('coherent_torsion_section'):
                st.caption('Seção torsional coerente não qualificada. Coordenadas não demonstradas não são inferidas; consulte as pendências do cálculo.')
        except (ValueError, TypeError, KeyError, ArithmeticError, OSError) as exc:
            st.warning('Geometria do modelo pendente: '+str(exc))


STATUS_LABELS = {
    'elastic_critical_component':'Me elástico calculado no modelo declarado',
    'research_elastic_critical_computed':'Crítico elástico calculado',
    'pending_model_scope':'Pendente no modelo implementado',
    'pending_biaxial_model':'Pendente: flexão biaxial',
    'pending_numerical_qualification':'Pendente: qualificação numérica',
    'numerical_refinement_inconclusive':'Refinamento numérico inconclusivo',
    'no_positive_eigenvalue':'Sem autovalor positivo no modelo',
    'rotational_eigenvalue_without_reference_bending':'Instabilidade de giro sem momento de referência',
}


def summary_rows(evidence):
    rows = []
    for record in evidence.get('records', []):
        me = record.get('Me_Nmm')
        rows.append({'Combinação': record.get('combination_id'), 'Estado limite': record.get('limit_state'),
                     'Situação': STATUS_LABELS.get(record.get('status'),record.get('status')), 'Me elástico [kN·m]': me/1e6 if _finite(me) else None,
                     'λ crítico': record.get('lambda_cr'), 'Modos': str(record.get('modes', '')),
                     'Pendência / motivo': record.get('reason') or record.get('separate_axis_capacity_scope',{}).get('scope','')})
    return rows


def show_result(st, result):
    try:evidence = preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.warning('Me no topo não exibido: '+str(exc));return
    if evidence is None:return
    st.subheader('FLT — componente elástico com carga no topo')
    st.warning(SCOPE)
    st.caption(ASSUMPTIONS)
    if _direct_evidence(evidence):
        st.caption(str(evidence.get('scope') or DIRECT_SCOPE))
        st.caption(DIRECT_ASSUMPTIONS)
    st.caption('Situação: '+STATUS_LABELS.get(evidence.get('status'),str(evidence.get('status', 'não informada'))))
    if evidence.get('reason'):st.warning(evidence['reason'])
    rows = summary_rows(evidence)
    if rows:st.dataframe(display_frame(rows), hide_index=True, width='stretch')
    with st.expander('Modelo de topo: escolha e geometria salvas', expanded=False):
        st.json({k: evidence.get(k) for k in ('choice_snapshot','geometry','scope','load_basis','direct_envelope_assumptions','source_input_fingerprint')})
    st.caption('Me isolado não é resistência. O consumo NBR, quando salvo, aparece abaixo; torção e aprovação global permanecem separados.')
    from .roof_top_nbr_ui import show as show_nbr
    show_nbr(st,result)


def report(doc, result):
    return _report(doc,result)


def _report(doc,result,nbr_report=None):
    try:evidence = preserved(result)
    except (ValueError,TypeError,KeyError) as exc:
        doc.add_paragraph('Me no topo não exibido: '+str(exc));return
    if evidence is None:return
    doc.add_heading('FLT — componente elástico com carga no topo', 1)
    doc.add_paragraph(SCOPE)
    doc.add_paragraph(ASSUMPTIONS)
    if _direct_evidence(evidence):
        doc.add_paragraph(str(evidence.get('scope') or DIRECT_SCOPE))
        doc.add_paragraph(DIRECT_ASSUMPTIONS)
        doc.add_paragraph('Hipóteses salvas: '+str(evidence.get('direct_envelope_assumptions', {})))
    doc.add_paragraph('Situação: '+STATUS_LABELS.get(evidence.get('status'),str(evidence.get('status', 'não informada'))))
    if evidence.get('reason'):doc.add_paragraph(str(evidence['reason']))
    selected = evidence.get('choice_snapshot') or {}
    doc.add_paragraph('Linha adotada: '+LABELS.get(selected.get('load_line'), str(selected.get('load_line', 'não informada')))+('. Total combinado representado no topo para envoltória de Me; PP já incluído, não quantificado nem adicionado.'
        if _direct_evidence(evidence) else '. PP do perfil no CG; cobertura no topo.'))
    g = evidence.get('geometry') or {}
    for field in ('h_mm','bf_mm','t_mm','height_above_SC_mm','x_from_CG_mm','x_from_SC_mm','source','coherent_torsion_section'):
        doc.add_paragraph(field+': '+str(g.get(field, 'não qualificado')))
    for row in summary_rows(evidence):
        doc.add_paragraph(' | '.join(k+': '+(fmt(v) if _finite(v) else str(v)) for k,v in row.items()))
    doc.add_paragraph('Rastreabilidade das entradas: '+str(evidence.get('source_input_fingerprint', 'não informada')))
    doc.add_paragraph('Resultados legados separados. Nenhuma resistência à torção ou aprovação global é demonstrada por este componente.')
    from .roof_top_nbr_ui import report as report_nbr
    if nbr_report is None:report_nbr(doc,result)
    else:nbr_report(doc)
