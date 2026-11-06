"""Explicit source adoption and snapshot-only presentation for Ue catalogue rows."""
from .ue_catalog_reference import FIELD, SCOPE, claims_reference, activate, validate, preserved


def render_choice(st,data,key,load):
    from .catalogs import catalog_entry
    network=data.get('three_girt_model',{})
    if (data.get('member_application','purlin')!='purlin' or not isinstance(network,dict)
        or network.get('enabled') or catalog_entry(data['catalog_index'])['family']!='Ue'):
        return
    with st.expander('Contorno próprio Ue do catálogo',expanded=claims_reference(data)):
        st.caption('Substitui em conjunto as propriedades geométricas e a massa. Mantém material e ações digitadas; PP será calculado uma vez no CG, ações externas no topo escolhido. Os críticos antigos ficam apenas na auditoria.')
        st.caption(SCOPE)
        if claims_reference(data):
            try:validate(data);st.success('Contorno próprio Ue aplicado às entradas atuais.')
            except (ValueError,TypeError,KeyError) as exc:st.warning(str(exc))
        if st.button('Reaplicar contorno próprio Ue' if claims_reference(data) else 'Aplicar contorno próprio Ue',key=key+'_apply'):
            try:changed=activate(data)
            except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
            else:load(changed);st.rerun()


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
