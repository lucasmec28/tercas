"""Family selection and imported-state persistence, without catalogue migration."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import ue_family_reference as f
from tercas.new_study_policy import for_new_study

APP=str(Path(__file__).resolve().parents[1]/'app.py')
def button(a,label):return next(x for x in a.button if x.label==label)
def select(a,label):return next(x for x in a.selectbox if x.label==label)
def number(a,label):return next(x for x in a.number_input if x.label==label)
def text(a,label):return next(x for x in a.text_input if x.label==label)


def imported(monkeypatch,d):
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app


def test_loader_and_section_span_preview_preserve_applied_state():
    a=AppTest.from_file(APP).run(timeout=30)
    assert button(a,'Carregar referência própria Ue100')
    select(a,'Espessura da referência Ue100 [mm]').set_value(2.65).run(timeout=30)
    button(a,'Carregar família própria Ue100').click().run(timeout=30)
    assert not a.exception and a.session_state.last_input==for_new_study(f.load_reference(2.65))
    text(a,'Identificação do estudo').set_value('Nome preservado').run(timeout=30)
    number(a,'Permanente [kgf/m²]').set_value(13.).run(timeout=30)
    old=copy.deepcopy(a.session_state.last_input)
    select(a,'Espessura proposta da família Ue100 [mm]').set_value(3.35).run(timeout=30)
    number(a,'Vão proposto da família Ue100 [mm]').set_value(4750.).run(timeout=30)
    assert a.session_state.last_input==old and button(a,'Calcular verificações disponíveis').disabled
    button(a,'Aplicar seção e vão da família Ue100').click().run(timeout=30)
    assert a.session_state.last_input==f.apply_geometry(old,3.35,4750.)
    assert button(a,'Calcular todas as seções do catálogo').disabled
    number(a,'Vão proposto da família Ue100 [mm]').set_value(6000.01).run(timeout=30)
    assert button(a,'Aplicar seção e vão da família Ue100').disabled
    assert button(a,'Calcular verificações disponíveis').disabled
    button(a,'Descartar proposta da família Ue100').click().run(timeout=30)
    assert not button(a,'Calcular verificações disponíveis').disabled


@pytest.mark.parametrize('malformed',[None,[],{'t':1.5}])
def test_malformed_import_is_exact_inspection(monkeypatch,malformed):
    d=f.load_reference(1.5);d['properties']=malformed
    a=imported(monkeypatch,d)
    assert a.session_state.last_input==d
    assert button(a,'Calcular verificações disponíveis').disabled
    assert not a.number_input


def test_exact_unactivated_source_activation_and_export(monkeypatch):
    d=f.source(3.,4750.,-5.);a=imported(monkeypatch,d)
    assert button(a,'Calcular verificações disponíveis').disabled
    button(a,'Ativar esta referência para cálculo').click().run(timeout=30)
    assert a.session_state.last_input==f.activate(d)
    records=[];old=st.download_button
    def record(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':records.append(json.loads(data))
        return old(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',record);a.run(timeout=30)
    assert records[-1]==f.activate(d)


def test_direct_els_guard_and_stale_results_after_section_draft(monkeypatch):
    d=f.load_reference(1.5,4000.,0.);d.update(load_mode='direct',q_uls=.2,q_sls=.1)
    a=imported(monkeypatch,d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception and a.session_state.result['ELS'].get('index') is not None
    number(a,'q paralelo ELS [N/mm]').set_value(.05).run(timeout=30)
    assert 'result' not in a.session_state
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert a.session_state.result['ELS'].get('index') is None
    select(a,'Espessura proposta da família Ue100 [mm]').set_value(2.).run(timeout=30)
    assert 'result' not in a.session_state and button(a,'Calcular verificações disponíveis').disabled


def test_catalogue_change_leaves_family_and_preserves_actions(monkeypatch):
    d=f.load_reference(1.5,4750.,13.);d.update(project='Preservado',actions_origin='Ações próprias',q_uls=.7,x_uls=2350.)
    d['area_inputs']['permanent_kgf_m2']=33.
    a=imported(monkeypatch,d)
    select(a,'Perfil de catálogo').set_value(19).run(timeout=30)
    assert not a.exception
    z=a.session_state.last_input
    assert not f.claims_reference(z)
    for key in ('project','actions_origin','q_uls','x_uls','L_mm','area_inputs','inclination'):
        assert z[key]==d[key]
    assert z['properties']['t']==1.2
    assert not button(a,'Calcular todas as seções do catálogo').disabled
    button(a,'Carregar referência própria Ue100').click().run(timeout=30)
    from tercas import ue_reference as old
    assert a.session_state.last_input==for_new_study(old.load_reference())


def test_research_marker_does_not_activate_app_route(monkeypatch):
    d=f.load_reference(2.25);d[f.FIELD]['schema']='own_Ue100_six_scalar_components_research_v1'
    a=imported(monkeypatch,d)
    assert a.session_state.last_input==d and button(a,'Calcular verificações disponíveis').disabled
