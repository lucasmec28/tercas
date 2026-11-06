import copy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas.application import example
from tercas.direct_self_weight import FIELD,MODE,activate,TEXT
APP=str(Path(__file__).resolve().parents[1]/'app.py')


def test_fresh_app_has_automatic_PP_without_new_numeric_field():
    a=AppTest.from_file(APP).run(timeout=45)
    assert not a.exception
    assert a.session_state.last_input[FIELD]==MODE
    assert any('1,25 no ELU e 1,0 no ELS' in x.value for x in a.caption)
    assert any('q em kN/m equivale a N/mm; P em kN' in x.value for x in a.caption)
    assert not any('Parcela PP' in x.label for x in a.number_input)
    # Ordinary section switch preserves entered load and recomputes selected mass.
    old=copy.deepcopy(a.session_state.last_input)
    next(x for x in a.selectbox if x.label=='Perfil de catálogo').set_value((old['catalog_index']+1)%209).run(timeout=45)
    assert not a.exception
    assert a.session_state.last_input[FIELD]==MODE
    assert a.session_state.last_input['q_uls']==old['q_uls']


def test_old_session_needs_explicit_adoption_and_keeps_raw_values():
    a=AppTest.from_file(APP);old=example()
    a.session_state.base=copy.deepcopy(old);a.session_state.last_input=copy.deepcopy(old)
    a.run(timeout=45)
    assert not a.exception and FIELD not in a.session_state.last_input
    assert any('Entrada legada' in x.value for x in a.warning)
    next(x for x in a.checkbox if x.label=='Já retirei o PP das cargas: adotar inclusão automática').check().run(timeout=45)
    assert not a.exception and a.session_state.last_input[FIELD]==MODE
    a.run(timeout=45)
    assert not a.exception and a.session_state.last_input[FIELD]==MODE
    for key in ('q_uls','q_sls','P_uls','P_sls'):assert a.session_state.last_input[key]==old[key]


def test_new_own_U_reference_also_adopts_PP_contract():
    a=AppTest.from_file(APP).run(timeout=45)
    next(x for x in a.button if x.label=='Carregar referência de cálculo').click().run(timeout=45)
    assert not a.exception and a.session_state.last_input[FIELD]==MODE
