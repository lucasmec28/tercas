"""Restricted action editor: never enters the catalogue/material widgets."""
import copy
import json
from .ue_reference import (REFERENCES, FIELD, SCOPE, FROZEN, TRACE_NOTE,
                                     source, load_reference, assess, evidence, calculate_reference)
from .application import fingerprint
from .presentation import display_frame
from .batch import area_bundle
from .drawing_cases import drawing_cases
from .drawing import svg


def loader(st, revision, load):
    with st.expander('Referência própria Ue100 — opt-in explícito', expanded=False):
        st.caption(SCOPE)
        angle = st.selectbox('Exemplo sintético Ue100', (0, 5, -5),
                            format_func=lambda v: f'{v:+g}° · 58 combinações', key=f'ue_ref_angle_loader_{revision}')
        st.caption('Abre novo estudo sintético próprio de 4 m, separado do catálogo e das referências U. Não converte nem requalifica automaticamente entradas existentes. Inclinação e ações podem ser editadas depois; ELS biaxial continua pendente.')
        if st.button('Carregar referência própria Ue100', key=f'ue_ref_load_{revision}'):
            try:new = load_reference('Ue100', angle)
            except (ValueError, OSError, KeyError) as exc:st.error('Referência não carregada: ' + str(exc))
            else:load(new);st.rerun()


def render_span(st, data, revision, load):
    from .ue_reference import apply_span, reference
    from .presentation import fmt
    st.subheader('Vão próprio Ue100 — 3000 a 6000 mm')
    st.caption('Lx=Ly=Lz=L, K=Cb=Cm=1. Garfos ideais, empenamento livre; sem comprimentos independentes. A proposta não altera entradas até Aplicar. P direto conserva a posição absoluta.')
    key=f'ue_span_{revision}'
    if key not in st.session_state:st.session_state[key]=float(data['L_mm'])
    proposed=st.number_input('Vão proposto Ue L [mm]',value=None,key=key,format='%.6f')
    preview=None
    try:
        preview=apply_span(data,proposed)
        values=reference(preview['L_mm'])['global_criticals']
        st.caption('Prévia não aplicada: Lx=Ly=Lz='+fmt(preview['L_mm'])+' mm. Ne/Me/FLT recalculados para esta proposta.')
        st.dataframe(display_frame([{'Derivado':k,'Valor':v,'Unidade':'N·mm' if k.startswith('Me_') else 'N'} for k,v in values.items()]),hide_index=True)
        st.caption('Critério ELS direto armazenado: L/'+fmt(data['ELS_down_denominator'])+' = '+fmt(preview['ELS_limit_mm'])+' mm. Critério de teste, sem conclusão ELS global. P direto ELU='+str(data['x_uls'])+' mm; ELS='+str(data['x_sls'])+' mm, sem reposicionamento.')
        outside=[k for k in ('x_uls','x_sls') if data[k] is not None and not 0<data[k]<preview['L_mm']]
        if outside:st.warning('P direto fora do novo vão: '+', '.join(outside)+'. Corrija explicitamente antes de calcular em modo direto.')
    except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
        st.error('Proposta Ue não aplicável: '+str(exc))
    pending=preview is None or preview!=data
    if pending:
        st.session_state.pop('result',None)
        st.info('Proposta de vão não aplicada. Resultados retirados; aplique ou descarte antes de calcular. O JSON preserva as entradas já aplicadas.')
        if st.button('Descartar proposta de vão Ue',key=f'ue_discard_span_{revision}'):
            load(data);st.rerun()
    if st.button('Aplicar vão Ue e recalcular críticos',key=f'ue_apply_span_{revision}',disabled=preview is None):
        load(preview);st.rerun()
    return pending


def render(st, data, revision, load, render_results, render_import):
    data = copy.deepcopy(data)
    state = assess(data)
    if not state['active']:raise ValueError('O editor restrito exige referência ativa revalidada.')
    st.subheader('Referência própria Ue100 — R01, 209 nós')
    st.warning(SCOPE)
    st.caption(FROZEN)
    st.caption(TRACE_NOTE)
    st.caption('Ações sintéticas e identificação editáveis; vão somente pela prévia e aplicação explícita abaixo. Não há seletor de painel nem crédito de travamento.')
    if st.button('Encerrar modo referência (inspeção)', key=f'ue_ref_exit_{revision}'):
        data.pop(FIELD, None);load(data);st.rerun()
    with st.expander('Vetor de seção e entradas rastreadas', expanded=False):
        st.json({k: copy.deepcopy(data[k]) for k in ('properties','property_origin','critical_origin',
                  'Ml_Nmm','Mdist_Nmm','L_mm','segments','weak_axis','support_origin','route_domain','ue_model','active_numeric_reference','ue_source_documents')})
    def number(label, key, value):
        return st.number_input(label, value=None if value is None else float(value), key=f'ue_ref_{key}_{revision}', format='%.6f')
    data['project'] = st.text_input('Identificação do estudo', value=data['project'], key=f'ue_ref_project_{revision}')
    data['actions_origin'] = st.text_input('Origem das ações sintéticas', value=data['actions_origin'], key=f'ue_ref_actions_origin_{revision}')
    data['load_mode'] = st.selectbox('Modo das ações da referência', ('area','direct'),
        index=('area','direct').index(data['load_mode']),
        format_func=lambda v: {'area':'Área — matriz de combinações','direct':'Direto — componentes locais combinadas'}[v], key=f'ue_ref_load_mode_{revision}')
    # Roof angle changes action decomposition only; section/material/supports do
    # not rotate into another structural application or change effective lengths.
    data['inclination']['value'] = number('Inclinação da cobertura [graus]', 'inclination', data['inclination']['value'])
    if data['load_mode'] == 'area':
        st.caption('PP calculado uma única vez da massa própria. Matriz de 48 linhas + P nas duas posições prescritas: 58 casos completos com todas as famílias selecionadas.')
        labels = {'spacing_m':'Distância entre terças [m]', 'permanent_kgf_m2':'Permanente [kgf/m²]',
                  'live_kgf_m2':'Sobrecarga [kgf/m²]', 'wind_up_kgf_m2':'Vento para cima [kgf/m²]', 'wind_down_kgf_m2':'Vento para baixo [kgf/m²]'}
        for key, label in labels.items():data['area_inputs'][key] = number(label, key, data['area_inputs'][key])
        data['selected_types'] = st.multiselect('Famílias de combinações', source(state['reference_id'])['selected_types'],
                                              default=data['selected_types'], key=f'ue_ref_types_{revision}')
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
    # Read action widgets before an explicit length commit, so the same event
    # cannot overwrite newly entered actions or absolute P positions.
    length_draft_pending=render_span(st,data,revision,load)
    st.session_state.last_input = copy.deepcopy(data)
    current = assess(data)
    token = fingerprint(data)
    old = st.session_state.get('result')
    if old and (old.get('input_fingerprint') != token or
                old.get('ue_reference_evidence') != (evidence(data) if current.get('calculable') else None)):
        st.session_state.pop('result', None)
        st.info('Entradas ou evidência alteradas. Calcule novamente; resultado anterior retirado.')
    st.session_state.pop('catalog_scan_state', None)
    if not current.get('calculable'):
        st.warning('Cálculo desativado: ' + '; '.join(current['reasons'] + current.get('action_errors', [])))
    else:
        previews = drawing_cases(data)
        chosen = st.selectbox('Combinação mostrada no desenho', range(len(previews)),
                              format_func=lambda i: previews[i][0], key=f'ue_ref_preview_{revision}') if data['load_mode']=='area' else 0
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
            with st.spinner('Calculando a referência própria…'):
                st.session_state.result = calculate_reference(data)
        except (ValueError, TypeError, KeyError, ArithmeticError, OSError) as exc:
            st.error('Não foi possível calcular: ' + str(exc))
    st.download_button('Baixar entradas da referência (JSON)', json.dumps(data, ensure_ascii=False, indent=2),
                       file_name='referencia_propria_ue100_entradas.json', mime='application/json')
    if 'result' in st.session_state:render_results(st.session_state.result, data)
    loader(st, revision, load)
    render_import(revision)
    st.stop()
