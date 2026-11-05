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
from tercas.three_girt_assessment.ui import LABEL as INVENTORY,KEY as INVENTORY_KEY
from tercas.support_web.ui import LABEL as SUPPORT,BUTTON as SUPPORT_BUTTON
from tercas.three_girt_uniaxial import application as uni
from tercas.three_girt_service import application as service
from tercas.three_girt_en_normal import application as en
from tercas.three_girt_axial import application as nbr
from tercas.three_girt_assessment import application as inventory
from tercas.support_web import application as support,mechanics as bearing,report as support_report
from tercas.three_girt_warping import network
from tercas.three_girt_warping.report import word


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
    u,s,e,n=uni.saved_component(result),service.saved_component(result),en.saved_component(result),nbr.saved_component(result)
    assert u and s and e and n
    assert e['schema']==en.SCHEMA and all(v['complete'] for v in e['per_member'].values())
    assert all(e[k] is False for k in en.FALSE_FLAGS)
    assert u['whole_member_approved'] is False and s['whole_member_approved'] is False
    def forbidden(*args,**kwargs):raise AssertionError('Saved display/sidecars/export must not resolve the member or capacities')
    monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(uni,'calculate',forbidden)
    monkeypatch.setattr(uni.scalar,'peak',forbidden);monkeypatch.setattr(service,'calculate',forbidden);monkeypatch.setattr(en,'calculate',forbidden)
    widget(app,'button',INVENTORY).click();run(app)
    assessment=copy.deepcopy(app.session_state[INVENTORY_KEY]);assert inventory.saved_assessment(result,assessment)==assessment
    assert assessment['whole_member_approved'] is False and assessment['current_adapter_can_approve'] is False
    widget(app,'checkbox',SUPPORT).check();run(app)
    for item in list(app.selectbox):
        if item.label.startswith('Caminho da reação: '):item.select('web_connection')
    for item in list(app.text_input):
        if item.label.startswith('Origem do detalhe: '):item.set_value('Synthetic web connection QA, not field verification')
    run(app);widget(app,'button',SUPPORT_BUTTON).click();run(app)
    local=copy.deepcopy(app.session_state['support_web_vlasov_saved'])
    assert support.saved_assessment(result,local)==local
    assert local['summary']['records']==6*sum(c['combination']['limit_state']=='ELU' for c in result['cases'])
    assert local['summary']['exempt']==local['summary']['records'] and local['whole_member_approved'] is False
    assert app.session_state[RESULT_KEY]==result and app.session_state[INVENTORY_KEY]==assessment
    monkeypatch.setattr(bearing,'evaluate_reaction',forbidden)
    start=time.perf_counter();run(app);rerender_seconds=time.perf_counter()-start
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state[RESULT_KEY]==result
    assert app.session_state['support_web_vlasov_saved']==local
    start=time.perf_counter();doc=word(result,assessment=assessment);local_doc=support_report.word(result,local)
    export_seconds=time.perf_counter()-start
    text='\n'.join(p.text for p in Document(BytesIO(doc)).paragraphs)
    for title in ('Panorama do modelo e critérios salvos','Componente horizontal de serviço','Alternativa uniaxial'):
        assert title.lower() in text.lower()
    assert 'Alma nas reações de apoio' in '\n'.join(p.text for p in Document(BytesIO(local_doc)).paragraphs)
    receipt=dict(t_mm=t,calculation_seconds=calculation_seconds,rerender_seconds=rerender_seconds,export_seconds=export_seconds,
        AppTest_timeout_seconds=60,all_four_mechanical_readers_passed=True,two_sidecars_passed=True,
        source_unchanged=True,no_solver_on_saved_operations=True,whole_member_approved=False)
    out=Path(os.environ.get('TERCAS_INTEGRATED_QA_DIR',str(tmp_path)));out.mkdir(parents=True,exist_ok=True)
    stem='joint_t'+str(t)
    for name,value in [('snapshot',result),('inventory',assessment),('support',local),('receipt',receipt)]:
        (out/(stem+'_'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    (out/(stem+'.docx')).write_bytes(doc);(out/(stem+'_support.docx')).write_bytes(local_doc)
    widget(app,'text_input','Origem do detalhe: upper_left').set_value('Changed support detail');run(app)
    assert 'support_web_vlasov_saved' not in app.session_state
    assert app.session_state[RESULT_KEY]==result and app.session_state[INVENTORY_KEY]==assessment
    widget(app,'text_input','Origem ou hipótese da alternativa uniaxial').set_value('Changed uniaxial model');run(app)
    assert RESULT_KEY not in app.session_state
