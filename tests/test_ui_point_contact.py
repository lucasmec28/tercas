"""Explicit contact choice: blank defaults, exact import/export and stale removal."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas.point_contact import FIELD, DECLARATIONS, blank_choice
from tercas.point_contact_ui import LABEL, C_LABEL, ORIGIN_LABEL
from tercas import ue_reference as ue, ue_family_reference as family
from tercas.application import defaults, fingerprint

APP=str(Path(__file__).resolve().parents[1]/'app.py')


def widget(app, kind, label):return next(x for x in getattr(app,kind) if x.label==label)
def run(app):
    app.run(timeout=60)
    assert not app.exception
    return app


def imported(monkeypatch,data):
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=run(AppTest.from_file(APP))
    widget(app,'button','Aplicar entradas do arquivo').click()
    return run(app)


@pytest.mark.parametrize('t',[1.2,1.5])
def test_reference_optin_blank_and_edit_invalidates_without_touching_legacy(monkeypatch,t):
    data=ue.load_reference() if t==1.2 else family.load_reference(t)
    data.update(load_mode='direct',q_uls=.2,q_sls=.1)
    app=imported(monkeypatch,data)
    assert FIELD not in app.session_state.last_input
    widget(app,'button','Calcular verificações disponíveis').click();run(app)
    assert 'result' in app.session_state
    widget(app,'checkbox',LABEL).check();run(app)
    changed=copy.deepcopy(app.session_state.last_input)
    expected=blank_choice();expected['enabled']=True
    assert changed.pop(FIELD)==expected
    assert changed==data and 'result' not in app.session_state
    assert widget(app,'number_input',C_LABEL).value is None
    assert widget(app,'text_input',ORIGIN_LABEL).value==''
    assert all(not widget(app,'checkbox',label).value for label in DECLARATIONS.values())
    widget(app,'number_input',C_LABEL).set_value(40.);run(app)
    widget(app,'text_input',ORIGIN_LABEL).set_value('Medição declarada');run(app)
    first=next(iter(DECLARATIONS.values()))
    widget(app,'checkbox',first).check();run(app)
    saved=copy.deepcopy(app.session_state.last_input)
    widget(app,'checkbox',LABEL).uncheck();run(app)
    saved[FIELD]['enabled']=False
    assert app.session_state.last_input==saved
    widget(app,'checkbox',LABEL).check();run(app)
    saved[FIELD]['enabled']=True
    assert app.session_state.last_input==saved
    assert app.session_state.last_input['patch_mm']==data['patch_mm']
    for field in ('left_web','right_web'):
        assert app.session_state.last_input[field]==data[field]


@pytest.mark.parametrize('t',[1.2,1.5])
@pytest.mark.parametrize('enabled',[False,True])
def test_reference_import_export_exact(monkeypatch,t,enabled):
    data=ue.load_reference() if t==1.2 else family.load_reference(t)
    data[FIELD]=blank_choice();data[FIELD].update(enabled=enabled,c_mm=37.5,origin='Detalhe de contato próprio')
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data
    records=[];original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':records.append(json.loads(data))
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    run(app)
    assert records[-1]==data


def test_generic_absence_and_fields_persist_across_unrelated_edits():
    app=run(AppTest.from_file(APP))
    assert FIELD not in app.session_state.last_input
    assert any('não altera as declarações existentes sobre telha/painel' in x.value for x in app.caption)
    token=fingerprint(app.session_state.last_input)
    app.session_state['result']={'input_fingerprint':token}
    app.session_state['catalog_scan_state']={'fingerprint':token}
    widget(app,'checkbox',LABEL).check();run(app)
    assert 'result' not in app.session_state and 'catalog_scan_state' not in app.session_state
    widget(app,'number_input',C_LABEL).set_value(35.);run(app)
    widget(app,'text_input',ORIGIN_LABEL).set_value('Contato medido');run(app)
    saved=copy.deepcopy(app.session_state.last_input[FIELD])
    widget(app,'text_input','Identificação do estudo').set_value('Estudo atualizado');run(app)
    assert app.session_state.last_input[FIELD]==saved
    widget(app,'checkbox',LABEL).uncheck();run(app)
    saved['enabled']=False
    assert app.session_state.last_input[FIELD]==saved


def test_generic_3d_unavailable_preserves_contact(monkeypatch):
    data=defaults();data['member_application']='wall_girt'
    data[FIELD]=blank_choice();data[FIELD].update(enabled=True,c_mm=40.,origin='Preservar')
    app=imported(monkeypatch,data)
    widget(app,'checkbox','Analisar sistema 3D de três travessas — diagnóstico sem resistência').check();run(app)
    assert widget(app,'checkbox',LABEL).disabled
    assert not any(x.label==C_LABEL for x in app.number_input)
    assert app.session_state.last_input[FIELD]==data[FIELD]


@pytest.mark.parametrize('t',[1.2,1.5])
def test_reference_malformed_import_is_preserved_inspection(monkeypatch,t):
    data=ue.load_reference() if t==1.2 else family.load_reference(t)
    data[FIELD]={'enabled':True}
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data
    assert widget(app,'button','Calcular verificações disponíveis').disabled
    assert not any(x.label==C_LABEL for x in app.number_input)


def test_own_vlasov_panel_unavailable_preserves_contact(monkeypatch):
    from tercas.ue_member_application import apply
    from tercas.three_girt_warping.ui import LABEL as VLASOV_LABEL
    data=apply(family.load_reference(1.5),'wall_girt')
    data[FIELD]=blank_choice();data[FIELD].update(enabled=True,c_mm=40.,origin='Preservar')
    app=imported(monkeypatch,data)
    widget(app,'checkbox',VLASOV_LABEL).check();run(app)
    assert widget(app,'checkbox',LABEL).disabled
    assert not any(x.label==C_LABEL for x in app.number_input)
    assert app.session_state.last_input==data
    widget(app,'checkbox',VLASOV_LABEL).uncheck();run(app)
    assert not widget(app,'checkbox',LABEL).disabled
    assert widget(app,'number_input',C_LABEL).value==40.
    assert app.session_state.last_input==data


def _saved_panel(result):
    import streamlit as st
    from tercas.point_contact_ui import show_saved_results
    show_saved_results(st,result)


def saved_direct(linked=True):
    from tercas.point_contact import reference_basis
    from tercas.application import example,calculate
    data=example();data.update(load_mode='direct',P_uls=100.,P_parallel_uls=0.,x_uls=data['L_mm']/2)
    choice=blank_choice();choice.update(enabled=True,c_mm=40.,origin='QA sintético: detalhe P; apoios A/B',basis=reference_basis(data))
    choice['declarations']={key:True for key in DECLARATIONS}
    data[FIELD]=choice
    result=calculate(data)
    assert result['NBR_branches']['point']['status']=='computed'
    if not linked:
        # Model an older saved result: never synthesize an evidence hash.
        result['NBR_branches']['point'].pop('evidence_sha256')
    return result


@pytest.mark.parametrize('linked',[False,True])
def test_saved_result_panel_never_recalculates_or_changes_history(monkeypatch,linked):
    import tercas.point_contact as contact
    from tercas.point_contact_ui import RESULTS_TITLE
    result=saved_direct(linked);original=copy.deepcopy(result)
    def forbidden(*args,**kwargs):raise AssertionError('Saved display must not validate or calculate')
    monkeypatch.setattr(contact,'evaluate',forbidden)
    monkeypatch.setattr(contact,'configuration',forbidden)
    app=run(AppTest.from_function(_saved_panel,args=(result,)))
    assert any(x.label==RESULTS_TITLE for x in app.expander)
    frame=app.dataframe[0].value
    assert frame.iloc[0]['P normal [N]']==100.
    if linked:
        assert frame.iloc[0]['FRd [N]']==original['NBR_branches']['point']['FRd_N']
        assert frame.iloc[0]['Situação local']=='Calculado — critério local'
    else:
        assert frame.iloc[0]['Situação local']=='Pendente'
        assert frame.iloc[0]['Índice']=='—'
    run(app)
    assert result==original


def test_saved_result_panel_absent_without_active_saved_choice():
    result=saved_direct();result['input_data'][FIELD]['enabled']=False
    assert not run(AppTest.from_function(_saved_panel,args=(result,))).dataframe
    result['input_data'].pop(FIELD)
    assert not run(AppTest.from_function(_saved_panel,args=(result,))).dataframe


@pytest.mark.parametrize('change',['span','application','section'])
def test_binding_preserved_until_explicit_geometry_reconfirmation(change):
    from tercas.point_contact import reference_basis,basis_matches
    app=run(AppTest.from_file(APP))
    widget(app,'checkbox',LABEL).check();run(app)
    geometry=DECLARATIONS['section_geometry_and_material_verified']
    widget(app,'checkbox',geometry).check();run(app)
    original=copy.deepcopy(app.session_state.last_input[FIELD])
    assert original['basis']==reference_basis(app.session_state.last_input)
    assert basis_matches(app.session_state.last_input)
    if change=='span':
        widget(app,'number_input','Vão entre apoios [mm]').set_value(5000.)
    elif change=='application':
        widget(app,'selectbox','Aplicação do elemento').set_value('wall_girt')
    else:
        current=widget(app,'selectbox','Perfil de catálogo')
        current.set_value(1 if current.value!=1 else 2)
    run(app)
    assert app.session_state.last_input[FIELD]==original
    assert not basis_matches(app.session_state.last_input)
    assert any('desmarque e reconfirme' in x.value for x in app.warning)
    widget(app,'checkbox',LABEL).uncheck();run(app)
    widget(app,'checkbox',LABEL).check();run(app)
    assert app.session_state.last_input[FIELD]['basis']==original['basis']
    assert not basis_matches(app.session_state.last_input)
    widget(app,'checkbox',geometry).uncheck();run(app)
    widget(app,'checkbox',geometry).check();run(app)
    assert basis_matches(app.session_state.last_input)
    assert app.session_state.last_input[FIELD]['basis']!=original['basis']


def test_saved_batch_separates_math_limit_and_parallel_pending_without_solver(monkeypatch):
    import tercas.point_contact as contact
    from tercas.application import calculate
    from tercas.batch import calculate_batch
    direct=saved_direct()
    data=copy.deepcopy(direct['input_data']);data.update(load_mode='area',selected_types=['ELU normal'])
    data[FIELD]['basis']=contact.reference_basis(data)
    complete=calculate_batch(data)
    center=next(case for case in complete['cases'] if case['combination'].get('P_N') and case['combination'].get('point_position')=='center')
    support=next(case for case in complete['cases'] if case['combination'].get('P_N') and case['combination'].get('point_position')=='support_limit')
    parallel_data=copy.deepcopy(data)
    parallel_data.update(load_mode='direct',P_uls=center['combination']['P_vector']['normal'],P_parallel_uls=50.,x_uls=center['combination']['x_mm'])
    parallel_result=calculate(parallel_data)
    parallel_case={'combination':{'id':'DIRECT_ELU_PARALLEL','limit_state':'ELU',
                    'x_mm':parallel_data['x_uls'],'P_N':parallel_data['P_uls'],
                    'P_vector':{'normal':parallel_data['P_uls'],'parallel':parallel_data['P_parallel_uls']}},
                   'evidence':parallel_result}
    result=copy.deepcopy(complete)
    result['cases']=[copy.deepcopy(center),copy.deepcopy(support),parallel_case]
    original=copy.deepcopy(result)
    def forbidden(*args,**kwargs):raise AssertionError('Saved display must not calculate')
    monkeypatch.setattr(contact,'evaluate',forbidden)
    monkeypatch.setattr(contact,'configuration',forbidden)
    app=run(AppTest.from_function(_saved_panel,args=(result,)))
    frame=app.dataframe[0].value
    assert list(frame['Combinação'])==[center['combination']['id'],support['combination']['id'],'DIRECT_ELU_PARALLEL']
    assert list(frame['Situação local'])==['Calculado — critério local','Não aplicável — limite matemático','Pendente']
    assert 'apoio' in frame.iloc[1]['Motivo / alcance']
    assert frame.iloc[2]['Motivo / alcance']==parallel_result['NBR_branches']['point']['reason']
    assert result==original


def test_real_optin_result_shown_only_in_separate_saved_block(monkeypatch):
    from tercas.point_contact import reference_basis
    from tercas.point_contact_ui import RESULTS_TITLE
    import tercas.point_contact as contact
    data=family.load_reference(1.5)
    data.update(load_mode='direct',P_uls=100.,P_parallel_uls=0.,x_uls=2000.,q_uls=.2,q_sls=.1)
    cfg=blank_choice();cfg.update(enabled=True,c_mm=40.,origin='Detalhe P e apoios A/B',basis=reference_basis(data))
    cfg['declarations']={key:True for key in DECLARATIONS};data[FIELD]=cfg
    app=imported(monkeypatch,data)
    widget(app,'button','Calcular verificações disponíveis').click();run(app)
    assert any(x.label==RESULTS_TITLE for x in app.expander)
    frames=[x.value for x in app.dataframe if 'FRd [N]' in x.value.columns]
    assert len(frames)==1 and frames[0].iloc[0]['FRd [N]']>0
    saved=copy.deepcopy(app.session_state.result)
    def forbidden(*args,**kwargs):raise AssertionError('Rendering saved results cannot recalculate contact')
    monkeypatch.setattr(contact,'evaluate',forbidden)
    run(app)
    assert app.session_state.result==saved


@pytest.mark.parametrize('t',[1.2,1.5])
def test_v2_explicit_choice_real_position_and_reconfirmation(monkeypatch,t):
    from tercas.point_contact import SCHEMA_V2, SCHEMA, basis_matches
    from tercas.point_contact_ui import VERSION_LABEL
    data=ue.load_reference() if t==1.2 else family.load_reference(t)
    data.update(load_mode='direct',q_uls=.2,q_sls=.1,P_uls=100.,P_parallel_uls=0.)
    app=imported(monkeypatch,data)
    assert FIELD not in app.session_state.last_input
    widget(app,'checkbox',LABEL).check();run(app)
    assert not widget(app,'checkbox',VERSION_LABEL).value
    assert app.session_state.last_input[FIELD]['schema']==SCHEMA
    widget(app,'checkbox',VERSION_LABEL).check();run(app)
    assert app.session_state.last_input[FIELD]['schema']==SCHEMA_V2
    assert len([x for x in app.number_input if x.label=='Posição de P ELU [mm]'])==1
    widget(app,'number_input','Posição de P ELU [mm]').set_value(20.);run(app)
    assert any('posição de P ELU informada = 20.0 mm' in x.value for x in app.caption)
    widget(app,'number_input',C_LABEL).set_value(40.);run(app)
    widget(app,'text_input',ORIGIN_LABEL).set_value('Detalhe P e apoios A/B');run(app)
    for label in DECLARATIONS.values():widget(app,'checkbox',label).check()
    run(app);assert basis_matches(app.session_state.last_input)
    widget(app,'button','Calcular verificações disponíveis').click();run(app)
    b=app.session_state.result['NBR_branches']['point']
    assert b['status']=='computed' and b['domain']['table_location']=='end'
    widget(app,'number_input','Posição de P ELU [mm]').set_value(19.);run(app)
    assert not basis_matches(app.session_state.last_input) and 'result' not in app.session_state
    assert any('desmarque e reconfirme' in x.value for x in app.warning)
    for key in ('patch_mm','patch_origin','left_web','right_web','support_origin'):
        assert app.session_state.last_input[key]==data[key]


def test_v2_import_is_not_automatically_changed(monkeypatch):
    from tercas.point_contact import SCHEMA_V2
    data=family.load_reference(1.5);data[FIELD]=blank_choice()
    data[FIELD].update(schema=SCHEMA_V2,enabled=True)
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data
    assert any('P_APOIO é a→0+' in x.value for x in app.caption)


def test_v2_area_missing_span_does_not_infer_center():
    from tercas.point_contact_ui import VERSION_LABEL
    app=run(AppTest.from_file(APP))
    widget(app,'radio','Forma de entrada').set_value('Cargas por área e combinações automáticas');run(app)
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox',VERSION_LABEL).check();run(app)
    widget(app,'checkbox',DECLARATIONS['section_geometry_and_material_verified']).check();run(app)
    widget(app,'number_input','Vão entre apoios [mm]').set_value(None);run(app)
    # The full app stops at its existing geometry guard before the contact panel.
    assert not app.exception


def _missing_span_contact_panel():
    import streamlit as st
    from tercas.point_contact import blank_choice, FIELD, SCHEMA_V2, reference_basis
    from tercas.point_contact_ui import render
    from tercas.application import example
    data=example();data.update(load_mode='area')
    cfg=blank_choice();cfg.update(enabled=True,schema=SCHEMA_V2,basis=reference_basis(data))
    cfg['declarations']['section_geometry_and_material_verified']=True
    data[FIELD]=cfg;data['L_mm']=None
    render(st,data,'missing_span')


def test_v2_area_panel_missing_span_caption():
    app=run(AppTest.from_function(_missing_span_contact_panel))
    assert any('P_CENTRO em L/2 = não informado' in x.value for x in app.caption)
    assert any('desmarque e reconfirme' in x.value for x in app.warning)
