import copy
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL,RESULT_KEY
from tercas.three_girt_axial.ui import LABEL as NBR_LABEL
from tercas.three_girt_axial.application import FIELD,saved_component
from tercas.three_girt_warping import network


def test_current_NBR_UI_saved_partial_and_invalidation(monkeypatch):
    d=apply(load_reference(1.5,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',LABEL).check();run(app)
    assert widget(app,'checkbox',NBR_LABEL).value is True
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    saved=copy.deepcopy(app.session_state[RESULT_KEY]);assert FIELD in saved
    c=saved_component(saved);assert c['per_member']['middle']['missing_capacity_keys']==['Nt']
    assert c['per_member']['middle']['complete_reference_envelope'] is None
    def forbidden(*args,**kwargs):raise AssertionError('Display/export cannot rerun structural demand')
    monkeypatch.setattr(network,'solve',forbidden)
    run(app);assert app.session_state[RESULT_KEY]==saved
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state[RESULT_KEY]==saved
    widget(app,'checkbox','Fornecer seções líquidas e Ct de tração').check();run(app)
    assert RESULT_KEY not in app.session_state
    assert app.session_state.last_input==d


def test_ELS_only_keeps_solved_demand_when_NBR_has_no_ELU(monkeypatch):
    d=apply(load_reference(1.5,4000.,5.),'wall_girt');d['selected_types']=['ELS quase permanente']
    app=imported(monkeypatch,d);widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    result=app.session_state[RESULT_KEY]
    assert result['status']=='conditional_elastic_vlasov_demand' and len(result['cases'])==1
    assert FIELD not in result and 'No ELU combination' in result['NBR_axial_bending_error']
    assert result['cases'][0]['model']['diagnostics']['passed']
