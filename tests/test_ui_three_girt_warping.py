"""Actual current-input UI, saved-result render and mutation invalidation."""
import copy
from io import BytesIO
from docx import Document
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL,RESULT_KEY
from tercas.three_girt_warping import network


def test_current_girt_UI_saved_G81_and_input_change(monkeypatch):
    d=apply(load_reference(1.5,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d)
    assert RESULT_KEY not in app.session_state
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert RESULT_KEY in app.session_state
    saved=copy.deepcopy(app.session_state[RESULT_KEY]);assert len(saved['cases'])==19
    assert saved['G81_component_attached'] and app.session_state.last_input==d
    def forbidden(*args,**kwargs):raise AssertionError('Viewing/exporting must not solve structural demand')
    monkeypatch.setattr(network,'solve',forbidden)
    run(app);assert app.session_state[RESULT_KEY]==saved
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(1);run(app)
    assert app.session_state[RESULT_KEY]==saved
    from tercas.three_girt_warping.report import word
    doc=Document(BytesIO(word(saved,1)))
    text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert 'G8.1' in text and 'N+M+B' in text and saved['input_fingerprint'] in text
    widget(app,'number_input','Linha externa Y a partir do CG Vlasov [mm]').set_value(8.);run(app)
    assert RESULT_KEY not in app.session_state
    assert app.session_state.last_input==d
