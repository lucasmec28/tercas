"""The named own-reference creation buttons must open calculable studies."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from tercas import ue_reference as ue, ue_family_reference as family
from tercas.flt_height_effective import COMBINED_FIELD
from tercas.deflection_scope import FIELD, MODE
APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def button(app, label):
    return next(w for w in app.button if w.label == label)


@pytest.mark.parametrize('thickness', [None, *family.THICKNESSES])
def test_own_loader_opens_calculable_source_and_survives_rerender(thickness):
    app = AppTest.from_file(APP).run(timeout=60)
    if thickness is None:
        button(app, 'Carregar referência própria Ue100').click().run(timeout=60)
        module = ue
    else:
        next(w for w in app.selectbox if w.label == 'Espessura da referência Ue100 [mm]').set_value(thickness).run(timeout=60)
        button(app, 'Carregar família própria Ue100').click().run(timeout=60)
        module = family
    assert not app.exception
    assert not button(app, 'Calcular verificações disponíveis').disabled
    data = app.session_state.last_input
    assert module.assess(data)['calculable']
    assert data[FIELD] == MODE and COMBINED_FIELD not in data
    assert not any('Campos protegidos divergentes' in x.value for x in app.error)
    app.run(timeout=60)
    assert not app.exception and app.session_state.last_input == data
    assert not button(app, 'Calcular verificações disponíveis').disabled


def test_ue100_loader_calculates_after_named_creation_click():
    app = AppTest.from_file(APP).run(timeout=60)
    button(app, 'Carregar referência própria Ue100').click().run(timeout=60)
    next(w for w in app.selectbox if w.label == 'Modo das ações da referência').set_value('direct').run(timeout=60)
    next(w for w in app.number_input if w.label == 'q normal ELU [N/mm]').set_value(.3)
    next(w for w in app.number_input if w.label == 'q normal ELS [N/mm]').set_value(.1)
    app.run(timeout=60)
    button(app, 'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception and app.session_state.result
    assert app.session_state.result['input_data'][FIELD] == MODE
    assert COMBINED_FIELD not in app.session_state.result['input_data']
    app.run(timeout=60)
    assert not app.exception and app.session_state.result
