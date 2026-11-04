import copy
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL as WARPING,RESULT_KEY
from tercas.three_girt_en_normal.ui import LABEL,MODEL_LABEL
from tercas.three_girt_en_normal.application import FIELD,saved_component
from tercas.three_girt_axial.application import saved_component as saved_nbr
from tercas.three_girt_warping import network


def test_EN_opt_in_coexists_and_changes_invalidate(monkeypatch):
    d=apply(load_reference(2.65,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
    assert widget(app,'checkbox',LABEL).value is False
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox',MODEL_LABEL).check()
    widget(app,'text_input','Origem ou hipótese da seção nominal EN').set_value('Synthetic QA intact section; not a physical survey')
    run(app);widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    original=copy.deepcopy(app.session_state[RESULT_KEY])
    assert FIELD in original and saved_component(original) is not None and saved_nbr(original) is not None
    def forbidden(*args,**kwargs):raise AssertionError('Read-only display/export cannot solve')
    monkeypatch.setattr(network,'solve',forbidden)
    run(app);assert app.session_state[RESULT_KEY]==original
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state[RESULT_KEY]==original
    widget(app,'text_input','Origem ou hipótese da seção nominal EN').set_value('Changed model declaration');run(app)
    assert RESULT_KEY not in app.session_state
    assert app.session_state.last_input==d


def test_EN_missing_declaration_preserves_demand_and_NBR(monkeypatch):
    d=apply(load_reference(2.65,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    result=app.session_state[RESULT_KEY]
    assert FIELD not in result and 'Declare' in result['EN_normal_N_M_B_error']
    assert saved_nbr(result) is not None
    assert result['status']=='conditional_elastic_vlasov_demand'
