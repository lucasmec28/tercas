"""Current and historical UI are read-only; legacy producers stay outside UI."""
import copy,json
from io import BytesIO
import pytest,streamlit as st
from docx import Document
from streamlit.testing.v1 import AppTest
from tercas.support_web import application as a,mechanics as m,completion
from tercas.support_web.ui import LABEL,BUTTON


def widget(app,kind,label):
    return next(v for v in getattr(app,kind) if v.label==label)


def run(app):
    app.run(timeout=20)
    assert not app.exception
    return app


def source(current=False):
    from tercas.application import example,calculate
    from tercas.support_scope import activate
    data=example();data.update(P_uls=0.,q_uls=1.,left_web=False,right_web=False,support_origin='')
    return calculate(activate(data) if current else data)


def fixture(result=None,saved=None,envelope=None):
    script='''
import streamlit as st
from tercas.support_web.ui import render
render(st,st.session_state.source,context='qa')
'''
    app=AppTest.from_string(script)
    app.session_state.source=source() if result is None else copy.deepcopy(result)
    if saved is not None:app.session_state.support_web_qa_saved=copy.deepcopy(saved)
    if envelope is not None:app.session_state.support_web_qa_completion_saved=copy.deepcopy(envelope)
    return run(app)


def forbid_new_support(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('No local support calculation or consolidation in UI')
    for module,name in ((a,'calculate'),(a,'reference_configuration'),(completion,'build'),(m,'evaluate_reaction')):
        monkeypatch.setattr(module,name,forbidden)


def assert_readonly(app):
    assert not any(w.label==LABEL for w in app.checkbox)
    assert not any(w.label in (BUTTON,'Consolidar evidência local no fechamento') for w in app.button)
    assert not any(w.label.startswith(('Caminho da reação:','Origem do detalhe:','Comprimento longitudinal de contato'))
                   for kind in ('selectbox','text_input','number_input') for w in getattr(app,kind))


@pytest.mark.parametrize('current',[False,True])
def test_no_new_support_actions_even_for_unmarked_history(monkeypatch,current):
    result=source(current);before=copy.deepcopy(result)
    forbid_new_support(monkeypatch)
    app=fixture(result)
    assert_readonly(app)
    assert 'support_web_qa_saved' not in app.session_state
    assert not app.get('download_button')
    run(app);assert_readonly(app)
    assert app.session_state.source==before


def test_saved_web_exception_and_source_mismatch_are_readonly(monkeypatch):
    # The old producer is exercised separately, before entering the current UI.
    result=source();cfg=a.reference_configuration(result)
    for detail in cfg['details'].values():detail.update(route='web_connection',origin='Ligação da alma QA')
    saved=a.calculate(result,cfg)
    assert saved['summary']['exempt']==2 and saved['whole_member_approved'] is False
    before=copy.deepcopy((result,saved))
    forbid_new_support(monkeypatch)
    app=fixture(result,saved);assert_readonly(app)
    assert len(app.dataframe)==1
    assert len(app.get('download_button'))==2
    run(app)
    assert app.session_state.source==result and app.session_state.support_web_qa_saved==saved
    other=copy.deepcopy(result);other['input_data']['project']='Another saved source'
    app.session_state.source=other;run(app)
    assert not app.dataframe and not app.get('download_button')
    # Mismatched history is not presented or destroyed on a render.
    assert app.session_state.support_web_qa_saved==saved and (result,saved)==before
    app.session_state.source=copy.deepcopy(result);run(app)
    assert len(app.dataframe)==1 and len(app.get('download_button'))==2


def test_saved_contact_without_P_exports_original_values_without_recalculation(monkeypatch):
    result=source();cfg=a.reference_configuration(result)
    assert cfg['details']['left']['c_mm'] is None and cfg['details']['left']['end_distance_mm'] is None
    cfg['details']['left'].update(route='flange_contact',origin='Contato QA, sem projeto físico',c_mm=40.,
        end_distance_mm=0.,connected=False,no_opposite_force=True,normal_compressive_sign=-1)
    saved=a.calculate(result,cfg)
    assert saved['summary']['pending']==1 and saved['summary']['meets']+saved['summary']['fails']==1
    row=next(v for v in saved['rows'] if v['source_record']['support_id']=='left')
    assert row['local']['status']=='computed' and row['local']['force_N']==result['input_data']['L_mm']/2
    assert result['input_data']['P_uls']==0.
    exports={}
    def download(label,data,**kwargs):exports[label]=data;return False
    monkeypatch.setattr(st,'download_button',download)
    forbid_new_support(monkeypatch)
    app=fixture(result,saved);assert_readonly(app);run(app)
    assert json.loads(exports['Baixar verificação local dos apoios (JSON)'])==saved
    doc=Document(BytesIO(exports['Baixar memória local dos apoios (Word)']))
    assert any('Alma nas reações de apoio' in p.text for p in doc.paragraphs)
    assert app.session_state.source==result and app.session_state.support_web_qa_saved==saved


@pytest.mark.parametrize('mutation',['hash','index','source','global'])
def test_corrupt_saved_assessment_is_not_displayed_or_recomputed(monkeypatch,mutation):
    result=source();saved=a.calculate(result,a.reference_configuration(result))
    if mutation=='hash':saved['content_sha256']='corrupt'
    elif mutation=='index':saved['rows'][0]['local']['index']=0.
    elif mutation=='source':saved['source_fingerprint']='other'
    else:saved['whole_member_approved']=True
    if mutation!='hash':saved['content_sha256']=a.fingerprint({k:v for k,v in saved.items() if k!='content_sha256'})
    forbid_new_support(monkeypatch)
    app=fixture(result,saved);assert_readonly(app)
    assert not app.dataframe and not app.get('download_button')
    assert app.session_state.source==result and app.session_state.support_web_qa_saved==saved


@pytest.mark.parametrize('current',[False,True])
def test_real_app_hook_preserves_result_and_never_offers_support_actions(monkeypatch,current):
    from test_ui_own_girt_application import imported,run as run_main
    result=source(current)
    app=imported(monkeypatch,result['input_data'])
    # Common-editor defaults are part of the actual imported-input payload.
    from tercas.application import calculate
    result=calculate(copy.deepcopy(app.session_state.last_input))
    if not current:
        saved=a.calculate(result,a.reference_configuration(result))
        assert saved['summary']['pending']==2
        app.session_state.support_web_isolated_saved=copy.deepcopy(saved)
    forbid_new_support(monkeypatch)
    app.session_state.result=copy.deepcopy(result);run_main(app)
    original=copy.deepcopy(app.session_state.result)
    assert_readonly(app);run_main(app);assert_readonly(app)
    assert app.session_state.result==original==result
    labels=[e.proto.label for e in app.get('download_button')]
    assert ('Baixar verificação local dos apoios (JSON)' in labels) is (not current)
