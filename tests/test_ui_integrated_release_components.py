"""Coexistence of the four released components with unchanged mechanical sources."""
import copy,json,os,time
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL as WARPING,RESULT_KEY
from tercas.three_girt_service.ui import LABEL as SERVICE,INTACT
from tercas.three_girt_en_normal.ui import LABEL as EN,MODEL_LABEL
from tercas.three_girt_uniaxial.ui import LABEL as UNI,DECLARE
from tercas.three_girt_assessment.ui import KEY as INVENTORY_KEY
from tercas.support_web.ui import LABEL as SUPPORT,BUTTON as SUPPORT_BUTTON
from tercas.three_girt_uniaxial import application as uni
from tercas.three_girt_service import application as service
from tercas.three_girt_en_normal import application as en
from tercas.three_girt_axial import application as nbr
from tercas.three_girt_assessment import application as inventory
from tercas.support_web import application as support,mechanics as bearing,report as support_report
from tercas.three_girt_warping import network
from tercas.three_girt_warping.report import word
from tercas import three_girt_scope as scope


@pytest.mark.parametrize('t',[3.35,1.2])
def test_all_components_coexist_without_mutating_or_resolving_saved_model(monkeypatch,tmp_path,t):
    if t==1.2:
        from tercas.ue_reference import load_reference
        data=apply(load_reference(angle=5.,L_mm=4000.),'wall_girt')
    else:
        from tercas.ue_family_reference import load_reference
        data=apply(load_reference(t,4000.,5.),'wall_girt')
    app=imported(monkeypatch,data);widget(app,'checkbox',WARPING).check();run(app)
    for label in (SERVICE,EN,UNI):widget(app,'checkbox',label).check()
    run(app)
    for label in (INTACT,MODEL_LABEL,DECLARE):widget(app,'checkbox',label).check()
    for label in ('Origem ou hipótese da alternativa uniaxial','Origem ou hipótese do modelo de serviço','Origem ou hipótese da seção nominal EN'):
        widget(app,'text_input',label).set_value('Synthetic integrated QA, not a physical project')
    run(app);start=time.perf_counter()
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    calculation_seconds=time.perf_counter()-start
    result=copy.deepcopy(app.session_state[RESULT_KEY])
    assert scope.members(result)==('middle',)
    assert result[scope.FIELD]['model_members']==list(scope.LEVELS)
    assert all({b['girt'] for b in c['model']['beams']}==set(scope.LEVELS) for c in result['cases'])
    u,s,e,n=uni.saved_component(result),service.saved_component(result),en.saved_component(result),nbr.saved_component(result)
    assert u and s and e and n
    assert e['schema']==en.CENTRAL_SCHEMA and set(e['per_member'])=={'middle'}
    assert e[scope.FIELD]==result[scope.FIELD] and all(v['complete'] for v in e['per_member'].values())
    assert all(e[k] is False for k in en.FALSE_FLAGS)
    assert u['whole_member_approved'] is False and s['whole_member_approved'] is False
    def forbidden(*args,**kwargs):raise AssertionError('Saved display/sidecars/export must not resolve the member or capacities')
    monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(uni,'calculate',forbidden)
    monkeypatch.setattr(uni.scalar,'peak',forbidden);monkeypatch.setattr(service,'calculate',forbidden);monkeypatch.setattr(en,'calculate',forbidden)
    widget(app,'button','Montar panorama da travessa central').click();run(app)
    assessment=copy.deepcopy(app.session_state[INVENTORY_KEY]);assert inventory.saved_assessment(result,assessment)==assessment
    assert assessment['assessment_schema']==inventory.CENTRAL_SCHEMA
    assert assessment[scope.FIELD]==result[scope.FIELD]
    assert assessment['whole_member_approved'] is False and assessment['current_adapter_can_approve'] is False
    # Current studies cannot create local support evidence, even in the 3D UI.
    from test_ui_support_web import assert_readonly,forbid_new_support
    forbid_new_support(monkeypatch);assert_readonly(app)
    assert 'support_web_vlasov_saved' not in app.session_state
    start=time.perf_counter();run(app);rerender_seconds=time.perf_counter()-start
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state[RESULT_KEY]==result
    assert 'support_web_vlasov_saved' not in app.session_state
    assert_readonly(app)
    start=time.perf_counter();doc=word(result,assessment=assessment)
    export_seconds=time.perf_counter()-start
    text='\n'.join(p.text for p in Document(BytesIO(doc)).paragraphs)
    for title in ('Panorama do modelo e critérios salvos','Componente horizontal de serviço','Alternativa uniaxial'):
        assert title.lower() in text.lower()
    assert scope.NOTICE in text
    receipt=dict(t_mm=t,calculation_seconds=calculation_seconds,rerender_seconds=rerender_seconds,export_seconds=export_seconds,
        AppTest_timeout_seconds=60,all_four_mechanical_readers_passed=True,inventory_sidecar_passed=True,local_support_actions_absent=True,
        source_unchanged=True,no_solver_on_saved_operations=True,whole_member_approved=False)
    out=Path(os.environ.get('TERCAS_INTEGRATED_QA_DIR',str(tmp_path)));out.mkdir(parents=True,exist_ok=True)
    stem='joint_t'+str(t)
    for name,value in [('snapshot',result),('inventory',assessment),('receipt',receipt)]:
        (out/(stem+'_'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    (out/(stem+'.docx')).write_bytes(doc)
    assert 'support_web_vlasov_saved' not in app.session_state
    assert app.session_state[RESULT_KEY]==result and app.session_state[INVENTORY_KEY]==assessment
    widget(app,'text_input','Origem ou hipótese da alternativa uniaxial').set_value('Changed uniaxial model');run(app)
    assert RESULT_KEY not in app.session_state


@pytest.mark.parametrize('t',[3.35,1.2])
def test_historical_network_support_sidecar_is_readonly(monkeypatch,t):
    """The old producer remains a replay fixture, never an action in the app."""
    from streamlit.testing.v1 import AppTest
    from tercas.three_girt_warping import application as w
    from test_ui_support_web import assert_readonly,forbid_new_support
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    if t==1.2:
        from tercas.ue_reference import load_reference
        data=apply(load_reference(angle=5.,L_mm=4000.),'wall_girt')
    else:
        from tercas.ue_family_reference import load_reference
        data=apply(load_reference(t,4000.,5.),'wall_girt')
    result=w.attach_g81(w.calculate(data,w.current_configuration(data,src['configuration']['three_girt']),verification_scope=scope.SCHEMA))
    cfg=support.reference_configuration(result)
    for detail in cfg['details'].values():
        detail.update(route='web_connection',origin='Synthetic web connection QA, not field verification')
    local=support.calculate(result,cfg);before=copy.deepcopy((result,local))
    assert support.saved_assessment(result,local)==local
    assert set(local['configuration']['details'])=={'middle_left','middle_right'}
    assert {r['source_record']['support_id'] for r in local['rows']}=={'middle_left','middle_right'}
    assert local['summary']['records']==2*sum(c['combination']['limit_state']=='ELU' for c in result['cases'])
    assert local['summary']['exempt']==local['summary']['records'] and local['whole_member_approved'] is False
    def forbidden(*args,**kwargs):raise AssertionError('No member or support solve while reading history')
    monkeypatch.setattr(network,'solve',forbidden);forbid_new_support(monkeypatch)
    app=AppTest.from_string("""
import streamlit as st
from tercas.three_girt_warping.ui import render_saved
render_saved(st,st.session_state.source)
""")
    app.session_state.source=copy.deepcopy(result)
    app.session_state.support_web_vlasov_saved=copy.deepcopy(local)
    run(app);assert_readonly(app)
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state.source==result and app.session_state.support_web_vlasov_saved==local
    local_doc=support_report.word(result,local)
    local_text='\n'.join(p.text for p in Document(BytesIO(local_doc)).paragraphs)
    assert 'Alma nas reações de apoio' in local_text and scope.NOTICE in local_text
    assert any(e.proto.label=='Baixar verificação local dos apoios (JSON)' for e in app.get('download_button'))
    assert (result,local)==before
