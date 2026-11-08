"""Explicit source adoption and snapshot-only presentation for Ue catalogue rows."""
from .ue_catalog_reference import FIELD, SCOPE, claims_reference, activate, validate, preserved


def adopt_combined_for_calculation(state, data, load):
    """Explicit adoption keeps the complete earlier study in restorable history."""
    from .flt_height_effective import activate_combined
    from .pierin_ue_registry_ui import HISTORY, _snapshot
    from .pierin_ue_registry import select_new_study
    validate(data)
    select_new_study(data['catalog_index'], include_routes=False)
    changed = activate_combined(data)
    history = list(state.get(HISTORY, [])) + [_snapshot(state)]
    load(changed)
    state[HISTORY] = history


def preserve_then_load(state,changed,load):
    """Explicit contour adoption keeps the earlier durable study restorable."""
    from .pierin_ue_registry_ui import HISTORY, _snapshot
    history=list(state.get(HISTORY,[]))+[_snapshot(state)]
    load(changed)
    state[HISTORY]=history


def render_choice(st,data,key,load):
    from .catalogs import catalog_entry
    network=data.get('three_girt_model',{})
    if (not isinstance(network,dict) or network.get('enabled') or catalog_entry(data['catalog_index'])['family']!='Ue'):
        return
    with st.expander('Contorno próprio Ue do catálogo',expanded=claims_reference(data)):
        st.caption('Substitui em conjunto as propriedades geométricas e a massa. Mantém material e ações digitadas; PP calculado uma única vez. Os críticos antigos ficam apenas na auditoria.')
        from .ue_catalog_reference import scope_for
        from .load_application_policy import adopt, active, applies_to_new
        st.caption(scope_for(adopt(data)))
        if claims_reference(data):
            try:validate(data);st.success('Contorno próprio Ue aplicado às entradas atuais.')
            except (ValueError,TypeError,KeyError) as exc:st.warning(str(exc))
        if st.button('Reaplicar contorno próprio Ue' if claims_reference(data) else 'Aplicar contorno próprio Ue',key=key+'_apply'):
            try:changed=activate(adopt(data))
            except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
            else:
                preserve_then_load(st.session_state,changed,load)
                st.rerun()
        if (claims_reference(data) and data.get('member_application','purlin')=='purlin'
                and not (active(data) or applies_to_new(data))):
            from .flt_height_effective import COMBINED_FIELD, COMBINED_METHOD
            from .pierin_ue_registry import select_new_study
            try:
                validate(data)
                select_new_study(data['catalog_index'], include_routes=False)
            except (ValueError, TypeError, KeyError):
                return
            if data.get(COMBINED_FIELD) != COMBINED_METHOD:
                st.caption('Adesão explícita para recálculo: q+P com alturas próprias somente com Ly=Lz=L e projeção paralela elegível. Preserva o estudo anterior no histórico restaurável; não atualiza resultados salvos.')
                if st.button('Adotar FLT q+P para novo cálculo', key=key+'_combined'):
                    adopt_combined_for_calculation(st.session_state, data, load)
                    st.rerun()
    if claims_reference(data) and data.get('member_application')=='wall_girt':
        from .wall_girt_isolated import render_choice as render_girt_lines
        render_girt_lines(st,data,key+'_girt_lines')


def show(st,result):
    try:ev=preserved(result)
    except (ValueError,KeyError,TypeError) as exc:st.warning('Referência própria não exibida: '+str(exc));return
    if ev is None:return
    with st.expander('Fonte geométrica própria Ue e auditoria'):
        st.caption(ev['scope'])
        st.json(ev)


def report(doc,result):
    try:ev=preserved(result)
    except (ValueError,KeyError,TypeError) as exc:doc.add_paragraph('Referência própria não exibida: '+str(exc));return
    if ev is None:return
    doc.add_heading('Contorno próprio Ue: geometria e origem das ações',1)
    doc.add_paragraph(ev['scope'])
    b=ev['source_binding'];doc.add_paragraph('Perfil: '+b['catalog_id']+'; identidade nominal: '+b['nominal_identity_sha256']+'; nós: '+b['nodes_sha256'])
    doc.add_paragraph('Propriedades geométricas próprias: '+str(ev['geometric_properties']))
    doc.add_paragraph('Material original preservado: '+str(b['material']))
    doc.add_paragraph('Dados substituídos, apenas para auditoria: '+str(ev['superseded_section_inputs']))
