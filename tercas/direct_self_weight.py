"""Versioned direct-input contract. Missing token means legacy totals, forever.

Raw fields remain user-entered external actions. This adapter alone adds profile
weight at the centroid, never rotates user actions, and is inactive for area mode.
"""
import copy
from .inclination import number, self_weight

FIELD = 'direct_load_basis'
MODE = 'external_without_profile_self_weight_v1'
FACTORS = {'uls': 1.25, 'sls': 1.0}
TEXT = ('Valores digitados sem o peso próprio do perfil. O programa soma PP no CG '
        'pela massa da seção: 1,25 no ELU e 1,0 no ELS. Demais cargas no topo '
        'selecionado; ações digitadas já locais, sem nova rotação.')
LEGACY = ('Entrada legada: os valores são totais já combinados, incluindo o PP. '
          'Nenhum peso próprio é adicionado. Para adotar a nova entrada, retire '
          'manualmente o PP dos valores antes de selecionar a conversão.')


def selected(data):
    if FIELD not in data: return False
    if data[FIELD] != MODE:
        raise ValueError('Convenção de peso próprio direto desconhecida; entradas preservadas.')
    return True


def active(data):
    return selected(data) and data.get('load_mode') == 'direct'


def activate(data):
    selected(data)
    out = copy.deepcopy(data)
    out[FIELD] = MODE
    return out


def evidence(data):
    if not active(data): return None
    from .member_application import is_girt
    from .inclination_adapter import configuration
    mass = number(data['properties']['mass_kg_m'], 'Massa linear do perfil', True)
    qg = mass * 9.80665 / 1000.
    pp = {'normal': 0., 'parallel': qg} if is_girt(data) else self_weight(mass, configuration(data)[1]['radians'])
    states = {}
    for suffix, factor in FACTORS.items():
        entered = {'normal': number(data['q_'+suffix], 'q '+suffix),
                   'parallel': number(data.get('q_parallel_'+suffix, 0.), 'q paralelo '+suffix)}
        added = {axis: factor*value for axis, value in pp.items()}
        states[suffix] = {'factor': factor, 'external_q_N_mm': entered,
            'profile_PP_q_N_mm': added,
            'total_q_N_mm': {axis: entered[axis]+added[axis] for axis in pp}}
    return {'schema': MODE, 'mass_kg_m': mass, 'gravity_m_s2': 9.80665,
            'profile_characteristic_weight_N_mm': qg,
            'PP_application': 'centroid', 'external_application': 'selected_top_load_line',
            'user_actions_rotated': False, 'states': states, 'scope': TEXT}


def calculation_inputs(data):
    """Numerical scratch copy, idempotent; never use as an exported user input."""
    ev = evidence(data)
    out = copy.deepcopy(data)
    out.pop(FIELD, None)
    if ev:
        for suffix, state in ev['states'].items():
            out['q_'+suffix] = state['total_q_N_mm']['normal']
            out['q_parallel_'+suffix] = state['total_q_N_mm']['parallel']
    return out


def render(st, data, key):
    if data.get('load_mode') != 'direct': return
    if selected(data):
        st.caption(TEXT)
    else:
        st.warning(LEGACY)
        if st.checkbox('Já retirei o PP das cargas: adotar inclusão automática', value=False, key=key):
            data[FIELD] = MODE
            st.caption(TEXT)
