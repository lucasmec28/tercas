import copy
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL as WARPING,RESULT_KEY
from tercas.three_girt_uniaxial.ui import LABEL,DECLARE
from tercas.three_girt_uniaxial import application as a
from tercas.three_girt_axial.application import saved_component as saved_nbr
from tercas.three_girt_warping import network


def test_uniaxial_optin_saved_view_and_invalidation(monkeypatch):
 data=apply(load_reference(1.5,6000.,5.),'wall_girt')
 app=imported(monkeypatch,data);widget(app,'checkbox',WARPING).check();run(app)
 assert widget(app,'checkbox',LABEL).value is False
 widget(app,'checkbox',LABEL).check();run(app)
 widget(app,'checkbox',DECLARE).check()
 widget(app,'text_input','Origem ou hipótese da alternativa uniaxial').set_value('Synthetic isolated option QA')
 run(app);widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
 result=copy.deepcopy(app.session_state[RESULT_KEY]);assert a.saved_component(result) and saved_nbr(result)
 def forbidden(*x,**y):raise AssertionError('Saved UI cannot recalculate')
 monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(a.scalar,'peak',forbidden)
 run(app);widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
 assert app.session_state[RESULT_KEY]==result
 widget(app,'text_input','Origem ou hipótese da alternativa uniaxial').set_value('Changed QA origin');run(app)
 assert RESULT_KEY not in app.session_state and app.session_state.last_input==data


def test_missing_uniaxial_declaration_preserves_network(monkeypatch):
 data=apply(load_reference(1.5,4000.,5.),'wall_girt')
 app=imported(monkeypatch,data);widget(app,'checkbox',WARPING).check();run(app)
 widget(app,'checkbox',LABEL).check();run(app)
 widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
 result=app.session_state[RESULT_KEY]
 assert a.FIELD not in result and 'Declare' in result[a.ERROR]
 assert result['status']=='conditional_elastic_vlasov_demand' and saved_nbr(result)
 widget(app,'checkbox',LABEL).uncheck();run(app)
 assert RESULT_KEY not in app.session_state
