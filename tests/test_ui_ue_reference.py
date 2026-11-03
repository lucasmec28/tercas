"""Opt-in own Ue UI: no silent repairs, stale results or lost actions."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import ue_reference as ue
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(app,label):return next(b for b in app.button if b.label==label)
def select(app,label):return next(b for b in app.selectbox if b.label==label)
def number(app,label):return next(b for b in app.number_input if b.label==label)
def upload(monkeypatch,data):
    payload=json.dumps(data).encode();monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
def imported(monkeypatch,data):
    upload(monkeypatch,data);a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not a.exception
    return a

def test_loader_span_preview_apply_discard_and_no_independent_lengths():
    a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Carregar referência própria Ue100').click().run(timeout=30)
    assert not a.exception and a.session_state.last_input==ue.load_reference()
    assert button(a,'Calcular todas as seções do catálogo').disabled
    assert not any('Lx ' in n.label or 'Ly ' in n.label or 'Lz ' in n.label for n in a.number_input)
    number(a,'Vão proposto Ue L [mm]').set_value(4750.).run(timeout=30)
    assert a.session_state.last_input['L_mm']==4000.
    assert button(a,'Calcular verificações disponíveis').disabled
    button(a,'Aplicar vão Ue e recalcular críticos').click().run(timeout=30)
    assert a.session_state.last_input==ue.apply_span(ue.load_reference(),4750.)
    number(a,'Vão proposto Ue L [mm]').set_value(6000.00001).run(timeout=30)
    assert button(a,'Aplicar vão Ue e recalcular críticos').disabled
    assert button(a,'Calcular verificações disponíveis').disabled
    assert a.session_state.last_input['L_mm']==4750.
    button(a,'Descartar proposta de vão Ue').click().run(timeout=30)
    assert not button(a,'Calcular verificações disponíveis').disabled
    assert a.session_state.last_input['L_mm']==4750.

@pytest.mark.parametrize('mutation',['G','span','origin','marker','source','removed_weak','wall','torque','segment','D','ELS'])
def test_modified_inputs_open_exact_inspection(monkeypatch,mutation):
    d=ue.load_reference()
    if mutation=='G':d['properties']['G_MPa']=77000.
    elif mutation=='span':d['L_mm']=4100.
    elif mutation=='origin':d['weak_axis']['positive']['provenance']='edited'
    elif mutation=='marker':d[ue.FIELD]['reference_id']='other'
    elif mutation=='source':d['ue_source_documents']['vector_sha256']='changed'
    elif mutation=='removed_weak':d.pop('weak_axis')
    elif mutation=='wall':d['member_application']='wall_girt'
    elif mutation=='torque':d['ue_model']['imposed_primary_torque_Nmm']=1.
    elif mutation=='segment':d['segments'][0]['Lz_effective_mm']=3999.
    elif mutation=='D':d['weak_axis']['positive']['Mdist_Nmm']=None
    elif mutation=='ELS':d['combined_ELS_approved']=True
    before=copy.deepcopy(d);a=imported(monkeypatch,d)
    assert a.session_state.last_input==before and a.session_state.base==before
    assert button(a,'Calcular verificações disponíveis').disabled
    assert button(a,'Calcular todas as seções do catálogo').disabled
    assert not a.number_input
    a.run(timeout=30);assert a.session_state.last_input==before


def test_exact_source_requires_explicit_activation_and_exports_without_normalization(monkeypatch):
    d=ue.source(angle=-5,L_mm=4750.);a=imported(monkeypatch,d)
    assert button(a,'Calcular verificações disponíveis').disabled
    button(a,'Ativar esta referência para cálculo').click().run(timeout=30)
    assert a.session_state.last_input==ue.activate(d)
    exports=[];old=st.download_button
    def record(label,data,*args,**kw):
        if label=='Baixar entradas da referência (JSON)':exports.append(json.loads(data))
        return old(label,data,*args,**kw)
    monkeypatch.setattr(st,'download_button',record);a.run(timeout=30)
    assert exports[-1]==ue.activate(d)
    upload(monkeypatch,exports[-1]);a.run(timeout=30)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not a.exception and a.session_state.last_input==exports[-1]


def test_direct_actions_source_results_invalidation_and_span_preserve_absolute_P(monkeypatch):
    d=ue.load_reference();d.update(load_mode='direct',q_uls=.1,q_sls=.05,x_uls=3500.,x_sls=3500.)
    a=imported(monkeypatch,d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception and 'ue_reference_evidence' in a.session_state.result
    assert a.session_state.result['ELS'].get('index') is not None
    number(a,'q paralelo ELS [N/mm]').set_value(.1).run(timeout=30)
    assert 'result' not in a.session_state
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert a.session_state.result['ELS'].get('index') is None
    assert 'Fonte numérica ativa' in '\n'.join(c.value for c in a.caption)
    number(a,'Vão proposto Ue L [mm]').set_value(3000.).run(timeout=30)
    assert 'result' not in a.session_state
    button(a,'Aplicar vão Ue e recalcular críticos').click().run(timeout=30)
    assert not a.exception and a.session_state.last_input['x_sls']==3500.
    assert a.number_input and button(a,'Calcular verificações disponíveis').disabled
    number(a,'Posição de P ELS [mm]').set_value(1500.).run(timeout=30)
    number(a,'Posição de P ELU [mm]').set_value(1600.).run(timeout=30)
    assert not button(a,'Calcular verificações disponíveis').disabled


def test_explicit_profile_change_preserves_actions_project_and_inclination(monkeypatch):
    d=ue.load_reference(angle=13.);d.update(project='Projeto preservado',actions_origin='Ações editadas',load_mode='direct',q_uls=.8,P_uls=250.,x_uls=2350.)
    d['area_inputs']['live_kgf_m2']=33.;a=imported(monkeypatch,d)
    select(a,'Perfil de catálogo').set_value(20).run(timeout=30)
    assert not a.exception
    current=a.session_state.last_input
    for k in ('project','actions_origin','load_mode','q_uls','P_uls','x_uls','L_mm','area_inputs','inclination'):
        assert current[k]==d[k],k
    assert not ue.claims_reference(current)
    assert current['properties']!=d['properties']
    assert not button(a,'Calcular todas as seções do catálogo').disabled
