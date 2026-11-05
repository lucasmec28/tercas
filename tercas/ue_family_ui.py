"""Restricted action editor: never enters the catalogue/material widgets."""
import copy
import json
from .ue_family_reference import (THICKNESSES, FIELD, SCOPE, FROZEN, TRACE_NOTE,
                                     source, load_reference, assess, evidence, calculate_reference)
from .application import fingerprint
from .presentation import display_frame
from .batch import area_bundle
from .drawing_cases import drawing_cases
from .drawing import svg
from .new_study_policy import for_new_study


def loader(st, revision, load):
    with st.expander('Família própria Ue100 — seis espessuras', expanded=False):
        st.caption(SCOPE)
        t=st.selectbox('Espessura da referência Ue100 [mm]',THICKNESSES,
            format_func=lambda v:f'{v:.2f}'.replace('.',','),key=f'ue_family_loader_t_{revision}')
        angle=st.selectbox('Exemplo sintético da família Ue100',(0,5,-5),
            format_func=lambda v:f'{v:+g}° · 58 combinações',key=f'ue_family_loader_angle_{revision}')
        st.caption('Abre novo estudo sintético de 4 m com dados próprios individuais. Não converte automaticamente catálogo ou projetos existentes. Para trocar seção preservando as ações, use a prévia dentro da referência ativa. A referência de 1,20 mm continua separada.')
        if st.button('Carregar família própria Ue100',key=f'ue_family_load_{revision}'):
            try:new=for_new_study(load_reference(t,4000.,angle))
            except (ValueError,OSError,KeyError) as exc:st.error('Família não carregada: '+str(exc))
            else:load(new);st.rerun()


def render_geometry(st,data,revision,load):
    from .ue_family_reference import apply_geometry,reference
    from .presentation import fmt
    st.subheader('Seção e vão próprios — família Ue100')
    st.caption('Somente seis espessuras e 3000≤L≤6000 mm. Lx=Ly=Lz=L, K=Cb=Cm=1. A prévia não altera entradas até Aplicar; ações e posições absolutas de P são preservadas.')
    tkey=f'ue_family_t_{revision}';lkey=f'ue_family_span_{revision}'
    if tkey not in st.session_state:st.session_state[tkey]=float(data['properties']['t'])
    if lkey not in st.session_state:st.session_state[lkey]=float(data['L_mm'])
    proposed_t=st.selectbox('Espessura proposta da família Ue100 [mm]',THICKNESSES,
        key=tkey,format_func=lambda v:f'{v:.2f}'.replace('.',','))
    proposed_L=st.number_input('Vão proposto da família Ue100 [mm]',value=None,key=lkey,format='%.6f')
    preview=None
    try:
        preview=apply_geometry(data,proposed_t,proposed_L)
        ref=reference(proposed_t,proposed_L)
        st.caption('Prévia não aplicada: t='+fmt(proposed_t)+' mm, ri=t, Lx=Ly=Lz='+fmt(proposed_L)+' mm. Propriedades, PP, críticos e resistências individuais recalculados; sem escala de outra espessura.')
        keys=('Me_strong_Nmm','Me_weak_web_Nmm','Me_weak_lips_Nmm')
        from .roof_top_load import enabled as roof_enabled,LEGACY_COMPARATOR_NOTE
        if roof_enabled(data):st.caption(LEGACY_COMPARATOR_NOTE+' Recalcule para obter Me das combinações da cobertura.')
        else:st.dataframe(display_frame([{'Derivado':k,'Valor':ref['global_criticals'][k],'Unidade':'N·mm'} for k in keys]),hide_index=True)
        web=ref['resistances_exterior_primary']['weak_web_compressed']
        st.caption('Piso D da alma desta seção: '+fmt(web['Mdist_lower_bound_Nmm'])+' Nmm. Mdist identificado continua nulo; nenhuma dispensa T14 forte.')
        if preview.get('member_application')=='wall_girt':
            from .member_application import normal_els_limit
            normal_limit=normal_els_limit(preview)
            st.caption('Critério horizontal da travessa: '+fmt(normal_limit['value'])+' mm. '+normal_limit['origin']+' P direto mantém suas posições absolutas.')
        else:st.caption('P direto ELU='+str(data['x_uls'])+' mm; ELS='+str(data['x_sls'])+' mm, sem reposicionamento. Critério ELS de teste L/'+fmt(data['ELS_down_denominator'])+'='+fmt(preview['ELS_limit_mm'])+' mm, sem aprovação global.')
        outside=[k for k in ('x_uls','x_sls') if data[k] is not None and not 0<data[k]<preview['L_mm']]
        if outside:st.warning('P direto fora do novo vão: '+', '.join(outside)+'. Corrija explicitamente antes de calcular em modo direto.')
    except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
        st.error('Proposta da família não aplicável: '+str(exc))
    pending=preview is None or preview!=data
    if pending:
        st.session_state.pop('result',None)
        st.info('Proposta de seção/vão não aplicada. Resultados retirados; aplique ou descarte antes de calcular. O JSON preserva as entradas já aplicadas.')
        if st.button('Descartar proposta da família Ue100',key=f'ue_family_discard_{revision}'):
            load(data);st.rerun()
    if st.button('Aplicar seção e vão da família Ue100',key=f'ue_family_apply_{revision}',disabled=preview is None):
        load(preview);st.rerun()
    return pending


def render(st, data, revision, load, render_results, render_import):
    data = copy.deepcopy(data)
    state = assess(data)
    if not state['active']:raise ValueError('O editor restrito exige referência ativa revalidada.')
    st.subheader('Família própria Ue100 — t='+str(data['properties']['t'])+' mm, R01, 209 nós')
    st.warning(SCOPE)
    st.caption(FROZEN)
    st.caption(TRACE_NOTE)
    st.caption('Ações sintéticas e identificação editáveis; seção e vão somente pela prévia e aplicação explícita abaixo. Não há seletor de painel nem crédito de travamento.')
    if st.button('Encerrar modo referência (inspeção)', key=f'ue_family_ref_exit_{revision}'):
        data.pop(FIELD, None);load(data);st.rerun()
    with st.expander('Vetor de seção e entradas rastreadas', expanded=False):
        st.json({k: copy.deepcopy(data[k]) for k in ('properties','property_origin','critical_origin',
                  'Ml_Nmm','Mdist_Nmm','L_mm','segments','weak_axis','support_origin','route_domain','ue_family_model','ue_family_sources')})
    def number(label, key, value):
        return st.number_input(label, value=None if value is None else float(value), key=f'ue_family_ref_{key}_{revision}', format='%.6f')
    data['project'] = st.text_input('Identificação do estudo', value=data['project'], key=f'ue_family_ref_project_{revision}')
    data['actions_origin'] = st.text_input('Origem das ações sintéticas', value=data['actions_origin'], key=f'ue_family_ref_actions_origin_{revision}')
    data['load_mode'] = st.selectbox('Modo das ações da referência', ('area','direct'),
        index=('area','direct').index(data['load_mode']),
        format_func=lambda v: {'area':'Área — matriz de combinações','direct':'Direto — componentes locais combinadas'}[v], key=f'ue_family_ref_load_mode_{revision}')
    # Roof angle changes action decomposition only; section/material/supports do
    # not rotate into another structural application or change effective lengths.
    girt=data.get('member_application')=='wall_girt'
    if girt:st.caption('Inclinação e SC de cobertura armazenadas, inativas na travessa; nenhuma ação direta é girada novamente.')
    else:data['inclination']['value'] = number('Inclinação da cobertura [graus]', 'inclination', data['inclination']['value'])
    if data['load_mode'] == 'area':
        st.caption('Travessa isolada: PP uma vez, CP vertical por área de influência e vento horizontal. Sem SC usual/P automática de cobertura; 19 casos com todas as famílias selecionadas.' if girt else 'PP calculado uma única vez da massa própria. Matriz de 48 linhas + P nas duas posições prescritas: 58 casos completos com todas as famílias selecionadas.')
        labels = {'spacing_m':'Distância entre terças [m]', 'permanent_kgf_m2':'Permanente [kgf/m²]',
                  'live_kgf_m2':'Sobrecarga [kgf/m²]', 'wind_up_kgf_m2':'Vento para cima [kgf/m²]', 'wind_down_kgf_m2':'Vento para baixo [kgf/m²]'}
        if girt:
            labels={'spacing_m':'Distância entre travessas [m]','permanent_kgf_m2':'Permanente do fechamento [kgf/m²]','wind_up_kgf_m2':'Vento normal negativo [kgf/m²]','wind_down_kgf_m2':'Vento normal positivo [kgf/m²]'}
        for key, label in labels.items():data['area_inputs'][key] = number(label, key, data['area_inputs'][key])
        data['selected_types'] = st.multiselect('Famílias de combinações', source(data['properties']['t'],data['L_mm'])['selected_types'],
                                              default=data['selected_types'], key=f'ue_family_ref_types_{revision}')
    else:
        st.caption('Ações já locais e combinadas: não são giradas novamente, sem PP automático. P na posição informada; limites junto ao apoio permanecem no modo por área. O contrato legado também exige entradas de área armazenadas válidas: se necessário, volte ao modo área para corrigi-las; nada é substituído automaticamente.')
        for suffix, label in (('uls','ELU'), ('sls','ELS')):
            with st.expander(label + ' — ações locais', expanded=True):
                for prefix, title, unit in (('q','q normal','N/mm'), ('q_parallel','q paralelo','N/mm'),
                                          ('P','P normal','N'), ('P_parallel','P paralelo','N'), ('x','Posição de P','mm')):
                    key = prefix + '_' + suffix
                    value = number(f'{title} {label} [{unit}]', key, data.get(key, 0.))
                    # Do not silently append even zero-valued optional fields.
                    if key in data or value != 0:data[key] = value
    from .roof_top_load_ui import render_choice as render_roof_top_load
    render_roof_top_load(st, data, f'roof_top_load_{revision}')
    from .deflection_scope import render_choice
    render_choice(st, data, f'ue_family_ref_deflection_model_{revision}')
    from .torsion_study_ui import render_choice as render_torsion_choice
    render_torsion_choice(st, data, f'torsion_choice_{revision}')
    # Read action widgets before an explicit length commit, so the same event
    # cannot overwrite newly entered actions or absolute P positions.
    from .ue_member_application_ui import render_choice as render_application_choice,render_horizontal_limit
    render_horizontal_limit(st,data,'ue_family_ref_wall_els_'+str(revision))
    application_draft_pending=render_application_choice(st,data,'ue_family_ref_application_'+str(revision),load)
    length_draft_pending=application_draft_pending or render_geometry(st,data,revision,load)
    from .point_contact_ui import render as render_point_contact
    render_point_contact(st, data, f'point_contact_{revision}', disabled=data.get('member_application') == 'wall_girt' and st.session_state.get(f'three_warping_{revision}_enabled', False))
    st.session_state.last_input = copy.deepcopy(data)
    current = assess(data)
    from .three_girt_warping.ui import render_panel as render_three_girt_warping
    render_three_girt_warping(st,data,revision,disabled=not current.get('calculable') or length_draft_pending)
    token = fingerprint(data)
    old = st.session_state.get('result')
    if old and (old.get('input_fingerprint') != token or
                old.get('ue_family_reference_evidence') != (evidence(data) if current.get('calculable') else None)):
        st.session_state.pop('result', None)
        st.info('Entradas ou evidência alteradas. Calcule novamente; resultado anterior retirado.')
    st.session_state.pop('catalog_scan_state', None)
    if not current.get('calculable'):
        st.warning('Cálculo desativado: ' + '; '.join(current['reasons'] + current.get('action_errors', [])))
    else:
        previews = drawing_cases(data)
        chosen = st.selectbox('Combinação mostrada no desenho', range(len(previews)),
                              format_func=lambda i: previews[i][0], key=f'ue_family_ref_preview_{revision}') if data['load_mode']=='area' else 0
        st.markdown(svg(previews[chosen][1]), unsafe_allow_html=True)
        if data['load_mode'] == 'area':
            bundle = area_bundle(data)
            st.caption(f"{len(bundle['combinations'])} casos selecionados; solicitações simultâneas de cada combinação.")
            with st.expander('Ações e combinações sintéticas', expanded=False):
                st.dataframe(display_frame([{'Caso': c['id'], 'Tipo': c['type'],
                    'Expressão': c['expression'], 'q normal [N/mm]': c['q_vector']['normal'],
                    'q paralelo [N/mm]': c['q_vector']['parallel'], 'P normal [N]': c['P_vector']['normal'],
                    'P paralelo [N]': c['P_vector']['parallel']} for c in bundle['combinations']]), hide_index=True)
    c1, c2 = st.columns(2)
    with c1:clicked = st.button('Calcular verificações disponíveis', type='primary', disabled=not current.get('calculable') or length_draft_pending)
    with c2:st.button('Calcular todas as seções do catálogo', disabled=True)
    st.caption('Comparação genérica do catálogo indisponível neste modo: os dados próprios não se transferem a outra seção.')
    if clicked:
        st.session_state.pop('result', None)
        try:
            with st.spinner('Calculando a seção própria da família…'):
                from .study_completion import complete_result
                st.session_state.result = complete_result(calculate_reference(data))
        except (ValueError, TypeError, KeyError, ArithmeticError, OSError) as exc:
            st.error('Não foi possível calcular: ' + str(exc))
    st.download_button('Baixar entradas da referência (JSON)', json.dumps(data, ensure_ascii=False, indent=2),
                       file_name='familia_propria_ue100_entradas.json', mime='application/json')
    if 'result' in st.session_state:render_results(st.session_state.result, data)
    loader(st, revision, load)
    render_import(revision)
    st.stop()
