"""Explicit opt-in/preview/application, cache removal and recoverable actions."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas.homogeneous_reference import load_reference, assess, calculate_reference, evidence
from tercas.new_study_policy import for_new_study
from tercas.homogeneous_lengths import apply_lengths, FIELD, REPORTING_VERSION
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(app,label):return next(w for w in app.button if w.label==label)
def number(app,label):return next(w for w in app.number_input if w.label==label)
def select(app,label):return next(w for w in app.selectbox if w.label==label)
def upload(monkeypatch,data):
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
def imported(monkeypatch,data):
    upload(monkeypatch,data);app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app

def fixed():
    data=load_reference('U125',5)
    data.update(load_mode='direct',q_uls=.4,q_sls=.2,P_uls=80.,P_sls=-40.,x_uls=1700.,x_sls=1800.,q_parallel_uls=.05,q_parallel_sls=.02)
    return data

def extension():return apply_lengths(fixed(),L_mm=3000.)

def test_fixed_is_separate_opt_in_and_preview_never_commits_or_keeps_stale_result(monkeypatch):
    data=fixed();app=imported(monkeypatch,data)
    assert FIELD not in app.session_state.last_input
    assert not any(w.label=='Vão proposto L [mm]' for w in app.number_input)
    button(app,'Habilitar edição de vão e comprimentos').click().run(timeout=30)
    active=copy.deepcopy(app.session_state.last_input)
    assert active==extension()
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert 'result' in app.session_state
    number(app,'Vão proposto L [mm]').set_value(6000.).run(timeout=30)
    assert not app.exception and app.session_state.last_input==active
    assert 'result' not in app.session_state and button(app,'Calcular verificações disponíveis').disabled
    assert any('proposta de comprimentos não aplicada' in w.value for w in app.info)
    app.run(timeout=30)
    assert app.session_state.last_input==active
    button(app,'Aplicar vão e comprimentos').click().run(timeout=30)
    updated=app.session_state.last_input
    assert updated==apply_lengths(active,L_mm=6000.)
    assert updated['x_uls']==1700. and updated['x_sls']==1800.
    assert not button(app,'Calcular verificações disponíveis').disabled
    button(app,'Aplicar vão e comprimentos').click().run(timeout=30)
    assert app.session_state.last_input==updated and 'result' not in app.session_state
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert app.session_state.result['homogeneous_reference_evidence']['reporting_version']==REPORTING_VERSION
    number(app,'Vão proposto L [mm]').set_value(4500.).run(timeout=30)
    assert 'result' not in app.session_state
    button(app,'Descartar proposta de comprimentos').click().run(timeout=30)
    assert app.session_state.last_input==updated and number(app,'Vão proposto L [mm]').value==6000.
    assert not button(app,'Calcular verificações disponíveis').disabled


@pytest.mark.parametrize('value',(-1.,0.,None))
def test_invalid_span_draft_is_recoverable_and_discard_never_repositions_P(monkeypatch,value):
    data=extension();app=imported(monkeypatch,data)
    app.session_state['result']=calculate_reference(data)
    app.run(timeout=30);assert 'result' in app.session_state
    number(app,'Vão proposto L [mm]').set_value(value).run(timeout=30)
    app.run(timeout=30)
    assert not app.exception and app.session_state.last_input==data
    assert 'result' not in app.session_state
    assert button(app,'Aplicar vão e comprimentos').disabled
    assert button(app,'Calcular verificações disponíveis').disabled
    button(app,'Descartar proposta de comprimentos').click().run(timeout=30)
    assert app.session_state.last_input==data and not app.exception
    assert not button(app,'Calcular verificações disponíveis').disabled


def test_declared_lengths_origin_and_draft_mode_switch_preserve_values(monkeypatch):
    data=extension();app=imported(monkeypatch,data)
    select(app,'Modelo dos comprimentos').set_value('declared').run(timeout=30)
    assert button(app,'Aplicar vão e comprimentos').disabled
    for label,value in [('Lx efetivo — flexão em x [mm]',4000.),('Ly efetivo comum — flexão em y [mm]',2500.),('Lz efetivo — torção [mm]',5000.)]:
        number(app,label).set_value(value).run(timeout=30)
    next(w for w in app.text_input if w.label=='Origem e justificativa dos comprimentos').set_value('Distâncias sintéticas para teste, vínculos não comprovados.').run(timeout=30)
    select(app,'Modelo dos comprimentos').set_value('span').run(timeout=30)
    select(app,'Modelo dos comprimentos').set_value('declared').run(timeout=30)
    assert number(app,'Lx efetivo — flexão em x [mm]').value==4000.
    assert number(app,'Ly efetivo comum — flexão em y [mm]').value==2500.
    assert number(app,'Lz efetivo — torção [mm]').value==5000.
    assert app.session_state.last_input==data
    button(app,'Aplicar vão e comprimentos').click().run(timeout=30)
    new=app.session_state.last_input
    assert assess(new)['calculable'] and new[FIELD]['mode']=='declared'
    assert new['segments'][0]['Ly_top_effective_mm']==new['segments'][0]['Ly_bottom_effective_mm']==2500.
    assert new['L_mm']==3000. and new['x_uls']==1700.
    number(app,'Lx efetivo — flexão em x [mm]').set_value(None).run(timeout=30)
    app.run(timeout=30)
    assert not app.exception and app.session_state.last_input==new
    assert button(app,'Aplicar vão e comprimentos').disabled
    select(app,'Modelo dos comprimentos').set_value('span').run(timeout=30)
    select(app,'Modelo dos comprimentos').set_value('declared').run(timeout=30)
    assert number(app,'Lx efetivo — flexão em x [mm]').value is None
    number(app,'Lx efetivo — flexão em x [mm]').set_value(3500.).run(timeout=30)
    button(app,'Aplicar vão e comprimentos').click().run(timeout=30)
    assert app.session_state.last_input[FIELD]['Lx_effective_mm']==3500.


def test_shorter_span_keeps_absolute_P_and_requires_explicit_repair_for_direct(monkeypatch):
    data=extension();app=imported(monkeypatch,data)
    number(app,'Vão proposto L [mm]').set_value(1000.).run(timeout=30)
    assert any('fora do novo vão' in w.value for w in app.warning)
    button(app,'Aplicar vão e comprimentos').click().run(timeout=30)
    small=app.session_state.last_input
    assert small['L_mm']==1000. and small['x_uls']==1700. and small['x_sls']==1800.
    assert not app.exception and button(app,'Calcular verificações disponíveis').disabled
    app.run(timeout=30)
    assert number(app,'Posição de P ELU [mm]').value==1700.
    select(app,'Modo das ações da referência').set_value('area').run(timeout=30)
    assert not button(app,'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['x_uls']==1700.
    select(app,'Modo das ações da referência').set_value('direct').run(timeout=30)
    number(app,'Posição de P ELU [mm]').set_value(500.).run(timeout=30)
    number(app,'Posição de P ELS [mm]').set_value(600.).run(timeout=30)
    assert not button(app,'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['P_uls']==80. and app.session_state.last_input['P_sls']==-40.
    assert app.session_state.last_input['ELS_limit_mm']==1000/180


@pytest.mark.parametrize('mutation',('Nex','Nez','segment','ELS','origin','missing_contract','extra_K','asymmetric_Ly'))
def test_tampered_derived_import_is_preserved_inspection(monkeypatch,mutation):
    data=apply_lengths(fixed(),L_mm=6000.)
    if mutation=='Nex':data['weak_axis']['positive']['Nex_N']*=4
    if mutation=='Nez':data['weak_axis']['negative']['Nez_N']+=1
    if mutation=='segment':data['segments'][0]['end_mm']=3000.
    if mutation=='ELS':data['ELS_limit_mm']=3000/180
    if mutation=='origin':data[FIELD]['origin']='unrecorded replacement'
    if mutation=='missing_contract':data.pop(FIELD)
    if mutation=='extra_K':data[FIELD]['Kz']=.5
    if mutation=='asymmetric_Ly':data['segments'][0]['Ly_bottom_effective_mm']=3000.
    app=imported(monkeypatch,data)
    assert not app.exception and not app.number_input
    assert app.session_state.last_input==data
    assert button(app,'Calcular verificações disponíveis').disabled
    assert any(w.label=='Baixar entradas preservadas (JSON)' for w in app.get('download_button'))
    app.run(timeout=30);assert app.session_state.last_input==data


def test_roundtrip_export_contains_only_applied_values_and_profile_escape_strips_lengths(monkeypatch):
    data=apply_lengths(fixed(),L_mm=6000.);app=imported(monkeypatch,data)
    downloads=[];old=st.download_button
    def record(label,data,*a,**kw):
        if label=='Baixar entradas da referência (JSON)':downloads.append(json.loads(data))
        return old(label,data,*a,**kw)
    monkeypatch.setattr(st,'download_button',record)
    number(app,'Vão proposto L [mm]').set_value(4500.).run(timeout=30)
    assert downloads[-1]==data
    upload(monkeypatch,downloads[-1]);button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert app.session_state.last_input==data
    assert number(app,'Vão proposto L [mm]').value==6000.
    assert not button(app,'Calcular verificações disponíveis').disabled
    select(app,'Perfil de catálogo').set_value(0).run(timeout=30)
    assert not app.exception
    assert FIELD not in app.session_state.last_input and 'homogeneous_reference' not in app.session_state.last_input


def test_stale_length_evidence_is_removed_with_identical_input_fingerprint(monkeypatch):
    data=apply_lengths(fixed(),L_mm=4500.);app=imported(monkeypatch,data)
    old=calculate_reference(data)
    old['homogeneous_reference_evidence'].pop('global_length_derivation')
    app.session_state['result']=old;app.run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input==data
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert app.session_state.result['homogeneous_reference_evidence']==evidence(data)


def test_explicit_fixed_reload_and_exit_preserve_clear_identity(monkeypatch):
    data=apply_lengths(fixed(),L_mm=6000.);app=imported(monkeypatch,data)
    button(app,'Encerrar modo referência (inspeção)').click().run(timeout=30)
    assert app.session_state.last_input[FIELD]==data[FIELD]
    assert 'homogeneous_reference' not in app.session_state.last_input
    assert button(app,'Calcular verificações disponíveis').disabled
    button(app,'Ativar esta referência para cálculo').click().run(timeout=30)
    assert app.session_state.last_input==data
    select(app,'Referência nominal própria').set_value('U100').run(timeout=30)
    button(app,'Carregar referência de cálculo').click().run(timeout=30)
    assert app.session_state.last_input==for_new_study(load_reference('U100',0))
    assert FIELD not in app.session_state.last_input


def test_real_r3_fixed_high_action_cache_is_invalidated_without_rewriting_history(monkeypatch):
    from io import BytesIO
    from docx import Document
    from tercas.report import word
    from tercas.application import fingerprint
    from tercas.homogeneous_reference import REPORTING_VERSION as FIXED_REPORTING_VERSION
    old=json.loads((Path(__file__).parent/'data/homogeneous_u100_3m_high_action_r3.json').read_text())
    before=copy.deepcopy(old);data=old['input_data']
    assert old['homogeneous_reference_evidence']['reporting_version']=='homogeneous_reference_mv_trace_c26a5bf_20261103_r3'
    assert old['input_fingerprint']==fingerprint(data) and data['L_mm']==3000.
    assert FIELD not in data
    app=imported(monkeypatch,data)
    app.session_state['result']=old;app.run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input==data
    assert old==before
    # Generating Word neither requalifies old evidence nor mutates its snapshot.
    assert Document(BytesIO(word(old))).paragraphs and old==before
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    new=app.session_state.result
    assert new['input_data']==data and new['input_fingerprint']==old['input_fingerprint']
    assert new['homogeneous_reference_evidence']['reporting_version']==FIXED_REPORTING_VERSION
    assert new['ELS']['deflection_mm']!=old['ELS']['deflection_mm']
    assert new['ELS']['criterion_status']==old['ELS']['criterion_status']=='fails'
    assert new['whole_member_approved'] is False


def test_same_event_action_changes_are_read_before_explicit_length_apply(monkeypatch):
    data=extension();app=imported(monkeypatch,data)
    number(app,'Vão proposto L [mm]').set_value(4500.)
    number(app,'q normal ELU [N/mm]').set_value(-.7)
    number(app,'Posição de P ELU [mm]').set_value(3400.)
    number(app,'P normal ELU [N]').set_value(-125.)
    button(app,'Aplicar vão e comprimentos').click().run(timeout=30)
    assert not app.exception
    applied=app.session_state.last_input
    assert applied['L_mm']==4500. and applied['q_uls']==-.7
    assert applied['x_uls']==3400. and applied['P_uls']==-125.
    assert applied['x_sls']==data['x_sls'] and applied['q_sls']==data['q_sls']
    assert assess(applied)['calculable'] and 'result' not in app.session_state
