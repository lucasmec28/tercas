"""Saved completion exports remain available; there is no new UI consolidation."""
import copy,json
from io import BytesIO
import pytest,streamlit as st
from docx import Document
from test_ui_support_web import fixture,run,forbid_new_support,assert_readonly
from test_support_web_completion import fixture as historical_fixture,rehash
from tercas.support_web import completion


@pytest.mark.parametrize('assessment_separately_saved',[False,True])
def test_historical_complement_keeps_original_and_old_exports(monkeypatch,assessment_separately_saved):
    # Historical producer/replay is intentionally outside the UI boundary.
    result,assessment=historical_fixture();envelope=completion.build(result,assessment)
    assert completion.saved(result,envelope)==envelope
    before=copy.deepcopy((result,assessment,envelope));exports={}
    def download(label,data,**kwargs):exports[label]=data;return False
    monkeypatch.setattr(st,'download_button',download)
    forbid_new_support(monkeypatch)
    app=fixture(result,assessment if assessment_separately_saved else None,envelope)
    assert_readonly(app);run(app);assert_readonly(app)
    assert json.loads(exports['Baixar verificação local dos apoios (JSON)'])==assessment
    assert json.loads(exports['Baixar fechamento complementar (JSON)'])==envelope
    doc=Document(BytesIO(exports['Baixar fechamento complementar (Word)']))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert completion.SCOPE in text and completion.PERSISTENCE in text and completion.HISTORICAL_READ in text
    assert 'resistência local reconciliados por verificação escalar' not in text
    assert any(completion.HISTORICAL_READ==v.value for v in app.caption)
    assert app.session_state.source==result and app.session_state.support_web_qa_completion_saved==envelope
    assert (result,assessment,envelope)==before and not envelope['whole_member_approved']
    if not assessment_separately_saved:assert 'support_web_qa_saved' not in app.session_state
    # Switching sources hides, but never rewrites or destroys, the saved file.
    other=copy.deepcopy(result);other['input_data']['project']='Other source'
    exports.clear();app.session_state.source=other;run(app)
    assert not exports and app.session_state.support_web_qa_completion_saved==envelope
    app.session_state.source=copy.deepcopy(result);run(app)
    assert json.loads(exports['Baixar fechamento complementar (JSON)'])==envelope


@pytest.mark.parametrize('mutation',['hash','inventory','arithmetic','metadata','source_record','global'])
def test_historical_complement_rejects_incoherent_saved_content_without_formula(monkeypatch,mutation):
    result,assessment=historical_fixture();envelope=completion.build(result,assessment)
    if mutation=='hash':envelope['snapshot_sha256']='corrupt'
    elif mutation=='inventory':envelope['completion']['records'].pop()
    elif mutation=='arithmetic':envelope['assessment']['rows'][0]['local']['index']=999.
    elif mutation=='metadata':envelope['assessment']['source_metadata']='corrupt'
    elif mutation=='source_record':envelope['assessment']['rows'][0]['source_record']['x_mm']+=1
    else:envelope['whole_member_approved']=True
    if mutation!='hash':rehash(envelope)
    forbid_new_support(monkeypatch)
    app=fixture(result,envelope=envelope);assert_readonly(app)
    assert app.warning and not app.dataframe and not app.get('download_button')
    assert app.session_state.source==result and app.session_state.support_web_qa_completion_saved==envelope
