"""Explicit opt-in and retained legacy inputs for the roof-height model."""
import copy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from tercas.roof_top_load import FIELD, choice
from tercas.roof_top_load_ui import LABEL, LABELS, diagram, report

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def select(app, label):
    return next(widget for widget in app.selectbox if widget.label == label)


def button(app, label):
    return next(widget for widget in app.button if widget.label == label)


SCRIPT = '''
import copy
import streamlit as st
from tercas.ue_reference import load_reference
from tercas.roof_top_load_ui import render_choice, show_result
if 'data' not in st.session_state:
    st.session_state.data = load_reference()
data = copy.deepcopy(st.session_state.data)
render_choice(st, data, 'roof')
st.session_state.data = data
if 'evidence_result' in st.session_state:
    show_result(st, st.session_state.evidence_result)
'''


def test_render_only_does_not_activate_and_has_no_technical_inputs():
    app = AppTest.from_string(SCRIPT).run()
    assert not app.exception
    assert FIELD not in app.session_state.data
    assert not app.number_input
    assert len(app.selectbox) == 1
    original = copy.deepcopy(app.session_state.data)
    app.run()
    assert app.session_state.data == original


def test_selection_is_explicit_and_disabling_preserves_line_and_other_data():
    app = AppTest.from_string(SCRIPT).run()
    original = copy.deepcopy(app.session_state.data)
    select(app, LABEL).set_value('web_midplane').run()
    assert not app.exception
    assert app.session_state.data[FIELD] == choice('web_midplane')
    assert {k:v for k,v in app.session_state.data.items() if k != FIELD} == original
    select(app, LABEL).set_value('flange_midwidth').run()
    assert app.session_state.data[FIELD] == choice('flange_midwidth')
    select(app, LABEL).set_value('legacy').run()
    assert app.session_state.data[FIELD]['enabled'] is False
    assert app.session_state.data[FIELD]['load_line'] == 'flange_midwidth'
    assert {k:v for k,v in app.session_state.data.items() if k != FIELD} == original


def test_direct_and_inclined_scope_are_precise():
    app = AppTest.from_string(SCRIPT).run()
    data = copy.deepcopy(app.session_state.data)
    data['load_mode'] = 'direct'
    data['inclination']['value'] = 5.
    app.session_state.data = data
    select(app, LABEL).set_value('web_midplane').run()
    assert not app.exception
    assert not any('Pendente no modo direto' in widget.value for widget in app.warning)
    assert any('PP' in widget.value and 'não negativa' in widget.value for widget in app.caption)
    assert any('acoplamento de flexão nos dois eixos' in widget.value for widget in app.info)
    assert any('não comprova a ligação' in widget.value for widget in app.caption)


def test_no_centroid_is_guessed():
    svg = diagram({'h_mm':100., 'bf_mm':50., 'load_line':'web_midplane',
                   'height_above_SC_mm':50.}, {'properties':{'lip':17.}})
    assert 'CG não desenhado' in svg
    assert 'PP: CG; posição horizontal não qualificada' in svg
    assert 'fill="#15803d"' not in svg


def test_generic_hides_ct_selector_without_granting_route_domain():
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    original = app.session_state.last_input['route_domain']
    assert select(app, 'Domínio da expressão de Me nesta emissão')
    select(app, LABEL).set_value('web_midplane').run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['route_domain'] == original
    assert not any(w.label == 'Domínio da expressão de Me nesta emissão' for w in app.selectbox)
    select(app, LABEL).set_value('legacy').run(timeout=30)
    assert select(app, 'Domínio da expressão de Me nesta emissão')
    assert app.session_state.last_input['route_domain'] == original
    select(app, 'Domínio da expressão de Me nesta emissão').set_value(
        'Eixo forte de simetria; cargas no CT ou estabilizantes, sem torção primária').run(timeout=30)
    assert app.session_state.last_input['route_domain'] is True
    select(app, LABEL).set_value('flange_midwidth').run(timeout=30)
    assert app.session_state.last_input['route_domain'] is True
    assert not any('Sem torção primária significa' in w.value for w in app.caption)


@pytest.mark.parametrize('loader', ['Carregar referência própria Ue100', 'Carregar família própria Ue100'])
def test_own_reference_editors_expose_scheme_without_technical_fields(loader):
    app = AppTest.from_file(APP).run(timeout=30)
    button(app, loader).click().run(timeout=30)
    assert not app.exception
    old = copy.deepcopy(app.session_state.last_input)
    assert FIELD not in old
    select(app, LABEL).set_value('flange_midwidth').run(timeout=30)
    assert not app.exception
    new = app.session_state.last_input
    assert new[FIELD] == choice('flange_midwidth')
    assert {k:v for k,v in new.items() if k != FIELD} == old
    assert not button(app, 'Calcular verificações disponíveis').disabled
    assert not any(w.label == 'Analisar torção Vlasov (diagnóstico elástico)' for w in app.checkbox)
    assert not any('a partir do CG' in w.label for w in app.number_input)
    assert any('Declarações manuais anteriores preservadas' in w.value for w in app.caption)


def test_saved_result_and_report_surface_pending_records_without_recomputation(monkeypatch):
    from tercas import ue_family_reference as family
    from tercas.roof_top_load import attach
    d=family.load_reference(2.,4000.,5.)
    d[FIELD]=choice();d['selected_types']=['ELS quase permanente']
    result=attach(family.calculate_reference(d))
    # Rendering and exporting must not call the solver again.
    import tercas.roof_top_load as roof
    monkeypatch.setattr(roof,'refined',lambda **kwargs: (_ for _ in ()).throw(AssertionError('recalculation')))
    app = AppTest.from_string(SCRIPT).run()
    app.session_state.evidence_result = result
    app.run()
    assert not app.exception
    assert len(app.dataframe) == 1
    assert 'biaxial' in app.dataframe[0].value.to_string()
    from docx import Document
    doc = Document()
    report(doc, result)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert result['input_fingerprint'] in text
    assert 'componentes paralelas' in text
    assert 'não momento resistente' in text
    bad=copy.deepcopy(result);bad['roof_top_load_evidence']['computed_cases']=100
    doc=Document();report(doc,bad)
    assert 'não exibido' in '\n'.join(p.text for p in doc.paragraphs)


def test_scheme_survives_hidden_application_and_profile_switch():
    app=AppTest.from_file(APP).run(timeout=30)
    select(app,LABEL).set_value('flange_midwidth').run(timeout=30)
    original=copy.deepcopy(app.session_state.last_input[FIELD])
    select(app,'Aplicação do elemento').set_value('wall_girt').run(timeout=30)
    assert not app.exception and app.session_state.last_input[FIELD]==original
    app.run(timeout=30)
    assert app.session_state.last_input[FIELD]==original
    select(app,'Aplicação do elemento').set_value('purlin').run(timeout=30)
    assert not app.exception and app.session_state.last_input[FIELD]==original
    select(app,'Perfil de catálogo').set_value(1).run(timeout=30)
    assert not app.exception and app.session_state.last_input[FIELD]==original
