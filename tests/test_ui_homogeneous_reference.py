"""UI opt-in, exact preservation, restricted editing and invalidation."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas.homogeneous_reference import source, load_reference, assess, FIELD
from tercas.application import fingerprint
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(app,label):return next(b for b in app.button if b.label==label)
def select(app,label):return next(b for b in app.selectbox if b.label==label)
def upload(monkeypatch,data):
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
def imported(monkeypatch,data):
    upload(monkeypatch,data);app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app

@pytest.mark.parametrize('ref',('U100','U125','U150'))
def test_explicit_loader_keeps_own_physics_and_all_58_cases(ref):
    app=AppTest.from_file(APP).run(timeout=30)
    select(app,'Referência nominal própria').set_value(ref).run(timeout=30)
    select(app,'Caso sintético verificado').set_value(-5).run(timeout=30)
    button(app,'Carregar referência de cálculo').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input==load_reference(ref,-5)
    assert button(app,'Calcular todas as seções do catálogo').disabled
    assert not any(n.label.startswith(('Vão entre','fy personalizado','Ly ','Lz ')) for n in app.number_input)
    button(app,'Calcular verificações disponíveis').click().run(timeout=120)
    assert not app.exception
    result=app.session_state.result
    assert len(result['cases'])==58 and result['whole_member_approved'] is False
    assert result['input_data']==load_reference(ref,-5)
    assert result['homogeneous_reference_evidence']['reference_id']==ref
    app.run(timeout=30)
    assert app.session_state.result==result


def test_exact_legacy_stays_inspection_until_activation_then_roundtrips(monkeypatch):
    data=source('U100');data.pop('model_domain',None)
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data
    assert button(app,'Calcular verificações disponíveis').disabled
    button(app,'Ativar esta referência para cálculo').click().run(timeout=30)
    active=copy.deepcopy(app.session_state.last_input)
    assert {k:v for k,v in active.items() if k!=FIELD}==data
    assert assess(active)['active']
    downloads=[];old=st.download_button
    def record(label,data,*a,**kw):
        if label=='Baixar entradas da referência (JSON)':downloads.append(json.loads(data))
        return old(label,data,*a,**kw)
    monkeypatch.setattr(st,'download_button',record)
    app.run(timeout=30)
    assert downloads[-1]==active
    upload(monkeypatch,downloads[-1]);app.run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert app.session_state.last_input==active and not app.exception
    assert not button(app,'Calcular verificações disponíveis').disabled

@pytest.mark.parametrize('mutation',('property','span','weak_catalog','axial','marker','geometry','removed_weak','3d'))
def test_modified_physics_or_marker_goes_to_exact_inspection(monkeypatch,mutation):
    data=load_reference('U125')
    if mutation=='property':data['properties']['G_MPa']=77000.
    if mutation=='span':data['L_mm']=3100.
    if mutation=='weak_catalog':data['weak_catalog']={}
    if mutation=='axial':data['N_N']=1.
    if mutation=='marker':data[FIELD]['reference_id']='U100'
    if mutation=='geometry':data['properties']['h']+=1
    if mutation=='removed_weak':data.pop('weak_axis')
    if mutation=='3d':data['three_girt_model']={'enabled':False}
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data and app.session_state.base==data
    assert button(app,'Calcular verificações disponíveis').disabled
    assert button(app,'Calcular todas as seções do catálogo').disabled
    assert not app.number_input
    app.run(timeout=30)
    assert app.session_state.last_input==data


def test_actions_edit_signs_mode_rerun_and_cached_evidence(monkeypatch):
    app=imported(monkeypatch,load_reference('U150',5))
    select(app,'Modo das ações da referência').set_value('direct').run(timeout=30)
    next(n for n in app.number_input if n.label=='q paralelo ELU [N/mm]').set_value(-.2).run(timeout=30)
    next(n for n in app.number_input if n.label=='q normal ELU [N/mm]').set_value(.4).run(timeout=30)
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    assert result['inclination_evidence']['ELU']['q_vector']=={'normal':.4,'parallel':-.2}
    result.pop('homogeneous_reference_evidence')
    app.session_state['result']=result
    app.run(timeout=30)
    assert 'result' not in app.session_state
    assert assess(app.session_state.last_input)['active']
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    next(n for n in app.number_input if n.label=='q paralelo ELU [N/mm]').set_value(.2).run(timeout=30)
    assert 'result' not in app.session_state
    before=copy.deepcopy(app.session_state.last_input)
    app.run(timeout=30)
    assert app.session_state.last_input==before
    button(app,'Encerrar modo referência (inspeção)').click().run(timeout=30)
    assert FIELD not in app.session_state.last_input
    assert app.session_state.last_input['q_parallel_uls']==.2
    assert button(app,'Calcular verificações disponíveis').disabled


def test_profile_change_discards_reference_and_does_not_transfer_criticals(monkeypatch):
    app=imported(monkeypatch,load_reference('U100'))
    select(app,'Perfil de catálogo').set_value(105).run(timeout=30)
    assert not app.exception
    data=app.session_state.last_input
    assert FIELD not in data and 'W_mm3' not in data['weak_axis']['positive']
    assert data['properties']!=source('U125')['properties']
    assert not button(app,'Calcular todas as seções do catálogo').disabled


def test_invalid_actions_remain_editable_and_recover_without_replacing_vector(monkeypatch):
    app=imported(monkeypatch,load_reference('U125'))
    families=next(w for w in app.multiselect if w.label=='Famílias de combinações')
    families.set_value([]).run(timeout=30)
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['selected_types']==[]
    assert button(app,'Calcular verificações disponíveis').disabled
    assert app.number_input
    next(w for w in app.multiselect if w.label=='Famílias de combinações').set_value(['ELU normal']).run(timeout=30)
    assert not button(app,'Calcular verificações disponíveis').disabled
    next(n for n in app.number_input if n.label=='Distância entre terças [m]').set_value(-1.).run(timeout=30)
    app.run(timeout=30)
    assert not app.exception and button(app,'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['area_inputs']['spacing_m']==-1.
    next(n for n in app.number_input if n.label=='Distância entre terças [m]').set_value(1.5).run(timeout=30)
    assert not button(app,'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['properties']==source('U125')['properties']


@pytest.mark.parametrize('mutation', ('missing_project','missing_mode','missing_q','wrong_mode','bad_steel','bad_3d','bad_3d_enabled','missing_angle','bad_area_scalar'))
def test_malformed_marked_input_stays_downloadable_and_profile_escape_works(monkeypatch,mutation):
    data=load_reference('U100')
    if mutation=='missing_project':data.pop('project')
    if mutation=='missing_mode':data.pop('load_mode')
    if mutation=='missing_q':data.pop('q_uls')
    if mutation=='wrong_mode':data['load_mode']='alien'
    if mutation=='bad_steel':data['steel_name']='unknown'
    if mutation=='bad_3d':data['three_girt_model']='x'
    if mutation=='bad_3d_enabled':data['three_girt_model']={'enabled':1}
    if mutation=='missing_angle':data['inclination'].pop('value')
    if mutation=='bad_area_scalar':data['area_inputs']['spacing_m']='string'
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data
    assert not app.exception and not app.number_input
    assert any(w.label=='Baixar entradas preservadas (JSON)' for w in app.get('download_button'))
    select(app,'Perfil de catálogo').set_value(0).run(timeout=30)
    assert not app.exception and app.number_input
    assert FIELD not in app.session_state.last_input


@pytest.mark.parametrize('value',(float('nan'),float('inf'),-float('inf')))
def test_non_json_numeric_constants_rejected_before_overwriting_state(monkeypatch,value):
    data=load_reference('U100');data['properties']['G_MPa']=value
    upload(monkeypatch,data);app=AppTest.from_file(APP).run(timeout=30)
    before=copy.deepcopy(app.session_state.last_input)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input==before
    assert any('Constante JSON não finita' in e.value for e in app.error)


def test_mode_changes_preserve_inactive_actions_without_using_them(monkeypatch):
    app=imported(monkeypatch,load_reference('U125'))
    next(w for w in app.multiselect if w.label=='Famílias de combinações').set_value([]).run(timeout=30)
    next(n for n in app.number_input if n.label=='Distância entre terças [m]').set_value(-1.).run(timeout=30)
    select(app,'Modo das ações da referência').set_value('direct').run(timeout=30)
    # The unchanged backend validates the stored area shape/range even in
    # direct mode. Preserve it and let the user correct it, never normalize it.
    assert not app.exception and button(app,'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['area_inputs']['spacing_m']==-1.
    select(app,'Modo das ações da referência').set_value('area').run(timeout=30)
    next(n for n in app.number_input if n.label=='Distância entre terças [m]').set_value(1.5).run(timeout=30)
    select(app,'Modo das ações da referência').set_value('direct').run(timeout=30)
    assert not button(app,'Calcular verificações disponíveis').disabled
    next(n for n in app.number_input if n.label=='Posição de P ELU [mm]').set_value(-1.).run(timeout=30)
    app.run(timeout=30)
    assert button(app,'Calcular verificações disponíveis').disabled
    select(app,'Modo das ações da referência').set_value('area').run(timeout=30)
    assert app.session_state.last_input['x_uls']==-1.
    assert app.session_state.last_input['area_inputs']['spacing_m']==1.5
    next(w for w in app.multiselect if w.label=='Famílias de combinações').set_value(['ELU normal']).run(timeout=30)
    assert not button(app,'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['x_uls']==-1.
