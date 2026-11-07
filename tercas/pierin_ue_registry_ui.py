"""Explicit creation only; browsing never changes an open study or its caches."""
import copy

from .pierin_ue_registry import inventory, select_new_study

PREFIX = 'pierin_new_'
HISTORY = PREFIX + 'history'
DURABLE_KEYS = ('base', 'last_input', 'result', 'custom_steel_draft',
                'catalog_scan_state', 'three_girt_warping_result',
                'manual_result_history', 'manual_catalog_history')


def _snapshot(state):
    # Never copy button, upload or widget state back into Streamlit.
    return copy.deepcopy({k: state[k] for k in DURABLE_KEYS if k in state})


def start(state, index, factory, creation_policy, load):
    """Validate everything before switching; retain the full prior session study."""
    select_new_study(index, include_routes=False)
    new = creation_policy(factory(index))
    prior = _snapshot(state)
    history = list(state.get(HISTORY, []))
    history.append(prior)
    # Existing load semantics are explicit here; removed active caches survive
    # unchanged in history and can be restored, never reused for the new inputs.
    load(new)
    for key in ('three_girt_warping_result', 'manual_result_history', 'manual_catalog_history'):
        state.pop(key, None)
    state[HISTORY] = history


def restore(state, position):
    history = state.get(HISTORY, [])
    if type(position) is not int or not 0 <= position < len(history):
        raise ValueError('Estudo preservado inválido.')
    chosen = copy.deepcopy(history[position])
    current = _snapshot(state)
    revision = state.get('revision', 0) + 1
    for key in DURABLE_KEYS:
        state.pop(key, None)
    state.update(chosen)
    # Rehydrate fresh widgets from the actual saved inputs, not stale defaults.
    if 'last_input' in chosen:
        state['base'] = copy.deepcopy(chosen['last_input'])
    state['revision'] = revision
    state[HISTORY] = list(history) + [current]


def render(st, factory, creation_policy, load):
    with st.expander('Novo estudo Ue — dados tabulados completos', expanded=False):
        inv = inventory()
        options = [r['catalog_index'] for r in inv['records'] if r['selectable_for_new_study']]
        labels = {r['catalog_index']: 'Ue ' + r['name'] for r in inv['records']}
        st.caption(f"{inv['complete']} de {inv['total']} perfis Ue com dados tabulados completos. "
                   'Isso não é dimensionamento completo nem aprovação. Medidas genéricas ficam para implementação futura.')
        st.caption('Este comando inicia entradas padrão separadas. O estudo aberto, seus resultados e rascunhos duráveis '
                   'ficam preservados nesta sessão e podem ser restaurados abaixo. Não transfere ações, '
                   'hipóteses ou certificados. Apenas consultar este bloco não altera o estudo aberto. '
                   'O histórico é temporário: exporte seus arquivos antes de encerrar a sessão.')
        st.caption('O novo estudo começa como terça de cobertura, modo direto, inclinação zero em graus, '
                   'vão em mm, q em kN/m e P em kN. As ações externas começam zeradas; PP automático '
                   'do novo perfil segue o contrato de novos estudos. Não mantém modo ou unidades escolhidos '
                   'no estudo anterior. Controles transitórios ainda não aplicados não são restaurados.')
        index = st.selectbox('Perfil Ue para novo estudo', options,
                             format_func=lambda i: labels[i], key=PREFIX + 'index')
        confirmed = st.checkbox('Confirmo iniciar outro estudo e preservar o atual nesta sessão',
                                key=PREFIX + 'confirmed')
        if st.button('Iniciar novo estudo Ue', disabled=not confirmed, key=PREFIX + 'start'):
            try:
                start(st.session_state, index, factory, creation_policy, load)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                st.error('Novo estudo não iniciado: ' + str(exc))
            else:
                st.rerun()
        st.caption('Linhas incompletas continuam na auditoria e nos arquivos históricos; não são completadas automaticamente.')
        st.dataframe([{'Índice': row['catalog_index'], 'Perfil': labels[row['catalog_index']],
                       'Campos faltantes': ', '.join(row['missing_or_invalid_fields']),
                       'Conflitos': '; '.join(row['conflicts'])} for row in inv['incomplete']],
                     hide_index=True)
        history = st.session_state.get(HISTORY, [])
        if history:
            position = st.selectbox('Estudo preservado nesta sessão', range(len(history)),
                format_func=lambda i: f"{i + 1}: " + str(history[i].get('last_input', history[i].get('base', {})).get('project', 'Estudo')),
                key=PREFIX + 'restore_index')
            if st.button('Restaurar estudo preservado', key=PREFIX + 'restore'):
                restore(st.session_state, position)
                st.rerun()
