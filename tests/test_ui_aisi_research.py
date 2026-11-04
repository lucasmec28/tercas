"""Real AppTest flows, including project early-stop paths."""
import copy,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas.aisi_research import adapter as a
from tercas.aisi_research.panel import RESULT,PREFIX,technical
from tercas import ue_family_reference as family
APP=str(Path(__file__).resolve().parents[1]/'app.py')
def button(app,label):return next(x for x in app.button if x.label==label)
def activate(app):
    app.toggle(key=PREFIX+'enabled').set_value(True).run(timeout=60);assert not app.exception
    return app
def calculate(app):
    button(app,'Calcular índice longitudinal AISI').click().run(timeout=60)
    assert not app.exception and RESULT in app.session_state
    return copy.deepcopy(app.session_state[RESULT])
def protected(app):
    return {key:copy.deepcopy(app.session_state[key]) for key in ['base','last_input','result','revision','catalog_scan_state','catalog_scan_history'] if key in app.session_state}
def test_default_off():
    app=AppTest.from_file(APP).run(timeout=60)
    assert not app.exception and not app.toggle(key=PREFIX+'enabled').value and RESULT not in app.session_state
    assert not any('AISI' in x.label for x in app.selectbox)
    assert not any('AISI' in x.label for x in app.get('download_button'))
def test_repeat_clear_close_reopen_and_export_preserve_project(monkeypatch):
    downloads=[];original=st.download_button
    def capture(label,data,*args,**kw):
        if label=='Baixar somente pesquisa AISI (JSON)':downloads.append(json.loads(data))
        return original(label,data,*args,**kw)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(APP).run(timeout=60);app.button[0].click().run(timeout=60)
    button(app,'Calcular verificações disponíveis').click().run(timeout=120);assert 'result' in app.session_state
    before=protected(app);activate(app);assert protected(app)==before
    first=calculate(app);second=calculate(app);assert first==second and protected(app)==before
    assert downloads[-1]==first and 'input_data' not in downloads[-1]
    assert all(downloads[-1][k] is False for k in a.FLAGS)
    assert len(app.get('download_button'))==4
    app.run(timeout=60);assert app.session_state[RESULT]==first and protected(app)==before
    button(app,'Limpar resultado AISI').click().run(timeout=60)
    assert RESULT not in app.session_state and protected(app)==before
    app.run(timeout=60);assert RESULT not in app.session_state
    calculate(app);app.toggle(key=PREFIX+'enabled').set_value(False).run(timeout=60)
    assert RESULT not in app.session_state and protected(app)==before
    activate(app);assert RESULT not in app.session_state and protected(app)==before
    assert len(app.get('download_button'))==3
@pytest.mark.parametrize('key,value',[('thickness',3.35),('length',6000.),('factor',.01)])
def test_choice_change_then_back_does_not_restore(key,value):
    app=AppTest.from_file(APP).run(timeout=60);before=protected(app);activate(app);old=calculate(app)
    original=app.selectbox(key=PREFIX+key).value
    app.selectbox(key=PREFIX+key).set_value(value).run(timeout=60)
    assert RESULT not in app.session_state and protected(app)==before
    app.selectbox(key=PREFIX+key).set_value(original).run(timeout=60);assert RESULT not in app.session_state
    assert calculate(app)==old and protected(app)==before
def test_project_edit_does_not_change_research():
    app=AppTest.from_file(APP).run(timeout=60)
    # Load didactic case before enabling; later project edits do not change the isolated snapshot.
    app.button[0].click().run(timeout=60);activate(app);old=calculate(app)
    next(x for x in app.number_input if 'Vão entre' in x.label).set_value(4321.).run(timeout=60)
    assert app.session_state[RESULT]==old
    assert app.session_state.last_input['L_mm']==4321.
@pytest.mark.parametrize('route',['family','ue','u','inspection'])
def test_single_panel_before_early_stops(monkeypatch,route):
    app=AppTest.from_file(APP).run(timeout=60)
    if route=='family':button(app,'Carregar família própria Ue100').click().run(timeout=60)
    elif route=='ue':button(app,'Carregar referência própria Ue100').click().run(timeout=60)
    elif route=='u':
        label='Carregar referência de cálculo'
        button(app,label).click().run(timeout=60)
    else:
        payload=family.load_reference(1.5);payload['properties']=None;raw=json.dumps(payload).encode()
        monkeypatch.setattr(st,'file_uploader',lambda *args,**kw:SimpleNamespace(size=len(raw),getvalue=lambda:raw))
        app.run(timeout=60);button(app,'Aplicar entradas do arquivo').click().run(timeout=60)
    assert not app.exception;before=protected(app);activate(app)
    assert sum(x.label=='Ativar pesquisa isolada AISI 2024' for x in app.toggle)==1
    calculate(app);assert protected(app)==before
    if route=='inspection':assert app.session_state.last_input==payload
def test_corrupt_snapshot_cleared_no_repair():
    app=AppTest.from_file(APP).run(timeout=60);activate(app);calculate(app);before=protected(app)
    app.session_state[RESULT]['physical_design_approved']=True;app.run(timeout=60)
    assert RESULT not in app.session_state and protected(app)==before and not app.exception
    assert any('incompatibilidade' in x.value for x in app.warning)
    app.run(timeout=60);assert RESULT not in app.session_state
def test_bad_pin_clears_only_research_without_resurrection(monkeypatch,tmp_path):
    app=AppTest.from_file(APP).run(timeout=60);activate(app);calculate(app);before=protected(app)
    root=a.ROOT;shutil.copytree(root,tmp_path/'bundle',ignore=shutil.ignore_patterns('__pycache__'))
    monkeypatch.setattr(a,'ROOT',tmp_path/'bundle');(a.ROOT/'inputs/elastic_inputs.json').write_text('{}')
    app.run(timeout=60)
    assert not app.exception and RESULT not in app.session_state and protected(app)==before
    assert any('Fonte da pesquisa AISI alterada' in x.value for x in app.error)
    monkeypatch.setattr(a,'ROOT',root);app.run(timeout=60)
    assert RESULT not in app.session_state and protected(app)==before
def test_smallest_control_shows_nonzero_technical_values_and_official_link():
    records=json.loads((a.ROOT/'RESULTS.json').read_text())['records']
    smallest=min(records,key=lambda r:abs(r['required_midspan']['phi_rad']))
    app=AppTest.from_file(APP).run(timeout=60);activate(app)
    for key,field in [('thickness','thickness_mm'),('length','length_mm'),('factor','load_factor')]:
        app.selectbox(key=PREFIX+key).set_value(smallest[field]).run(timeout=60)
    result=calculate(app)
    texts=[str(frame.value) for frame in app.dataframe]
    assert any(technical(smallest['required_midspan']['phi_rad']) in t for t in texts)
    assert any(technical(smallest['declared_uniform_force_N_mm'][1]) in t for t in texts)
    assert any('https://sdi.org/' in item.value for item in app.markdown)
    assert not app.success


def test_research_notation_distinguishes_yield_and_transverse_moments():
    app=AppTest.from_file(APP).run(timeout=60);activate(app)
    result=calculate(app)
    captions='\n'.join(item.value for item in app.caption)
    assert 'My transversal é zero' in captions
    assert 'M_esc = Fy·Wx' in captions
    assert 'primeira fibra exterior' in captions
    assert 'distinto do momento transversal My' in captions
    assert 'Derivação: P=M_esc·' in captions
    assert 'D=M_esc/(1+0,60·M_esc/Mcrd)' in captions
    assert 'Derivação: P=My' not in captions
    assert all(result[key] is False for key in a.FLAGS)
    assert not app.success
