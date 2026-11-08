"""Direct combined roof inputs adopt a scalar envelope, never a PP estimate."""
import copy

from streamlit.testing.v1 import AppTest

from tercas.roof_top_load import FIELD, choice
from tercas.roof_top_load_ui import LABEL, diagram, report

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


def _selected_direct():
    app = AppTest.from_string(SCRIPT).run()
    data = copy.deepcopy(app.session_state.data)
    data['load_mode'] = 'direct'
    data['inclination']['value'] = 5.
    data[FIELD]=choice('web_midplane')
    app.session_state.data = data
    app.run()
    assert not app.exception
    return app


def test_current_direct_editor_keeps_saved_top_choice_inactive_without_new_controls():
    app=_selected_direct()
    assert not app.selectbox and not app.number_input and not app.checkbox
    assert not app.caption and not app.info and not app.warning
    assert app.session_state.data[FIELD]==choice('web_midplane')
    assert app.session_state.data['inclination']['value']==5.


def test_direct_area_round_trip_does_not_change_q_or_p_or_other_inputs():
    app = _selected_direct()
    original = copy.deepcopy(app.session_state.data)
    for mode in ('area', 'direct'):
        data = copy.deepcopy(app.session_state.data)
        data['load_mode'] = mode
        app.session_state.data = data
        app.run()
        assert not app.exception
        assert {k:v for k,v in app.session_state.data.items() if k != 'load_mode'} == {
            k:v for k,v in original.items() if k != 'load_mode'}
    assert app.session_state.data == original


def test_direct_diagram_shows_only_combined_surrogate_not_second_pp_arrow():
    g = dict(h_mm=100., bf_mm=50., load_line='web_midplane', height_above_SC_mm=50.,
             x_from_CG_mm=-15., load_x_from_web_midplane_mm=0.)
    direct = diagram(g, {'load_mode':'direct', 'properties':{'lip':17.}})
    assert 'Total combinado: substituto no topo' in direct
    assert 'PP já incluído no total informado' in direct
    assert 'Não é quantificado nem adicionado' in direct
    assert 'fill="#15803d"' not in direct
    assert 'PP não é deslocado ao topo' not in direct
    assert 'não representa o torque real' in direct
    area = diagram(g, {'load_mode':'area', 'properties':{'lip':17.}})
    assert 'PP do perfil: CG, separado da cobertura' in area
    assert 'fill="#15803d"' in area
    assert 'Total combinado' not in area


def test_saved_direct_report_uses_saved_scope_without_solver(monkeypatch):
    # Presentation contract only: evidence validation and numerical validity are
    # tested by the backend suite. A renderer must consume the saved evidence.
    import tercas.roof_top_load_ui as ui
    import tercas.roof_top_load as roof
    from docx import Document
    evidence = dict(schema='roof_top_load_evidence_v2', load_basis='direct_total_top_envelope',
                    scope='Escopo salvo da envoltória direta.', direct_envelope_assumptions={'saved':True},
                    choice_snapshot=choice(), records=[], geometry={}, source_input_fingerprint='saved-input')
    monkeypatch.setattr(ui, 'preserved', lambda result: evidence)
    monkeypatch.setattr(roof, 'refined', lambda **kw: (_ for _ in ()).throw(AssertionError('recalculation')))
    doc = Document()
    report(doc, {})
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert evidence['scope'] in text
    assert "'saved': True" in text
    assert 'PP já incluído, não quantificado nem adicionado' in text
    assert 'PP do perfil no CG; cobertura no topo' not in text
    assert 'saved-input' in text


def test_historical_area_report_preserves_separate_pp_description(monkeypatch):
    import tercas.roof_top_load_ui as ui
    from docx import Document
    evidence = dict(schema='roof_top_load_evidence_v1', choice_snapshot=choice(), records=[], geometry={})
    monkeypatch.setattr(ui, 'preserved', lambda result: evidence)
    doc = Document()
    report(doc, {})
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'PP do perfil no CG; cobertura no topo' in text
    assert 'Total combinado representado' not in text
