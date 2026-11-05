import copy
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL as WARPING,RESULT_KEY
from tercas.three_girt_service.ui import LABEL,INTACT
from tercas.three_girt_service.application import FIELD,saved_component
from tercas.three_girt_axial.application import saved_component as saved_nbr
from tercas.three_girt_warping import network


def test_service_explicit_optin_export_and_invalidation(monkeypatch):
 d=apply(load_reference(3.35,4000.,5.),'wall_girt')
 app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
 assert widget(app,'checkbox',LABEL).value is False
 widget(app,'checkbox',LABEL).check();run(app)
 widget(app,'checkbox',INTACT).check()
 widget(app,'text_input','Origem ou hipótese do modelo de serviço').set_value('Synthetic QA section')
 run(app);widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
 result=copy.deepcopy(app.session_state[RESULT_KEY])
 assert FIELD in result and saved_component(result) and saved_nbr(result)
 def forbidden(*x,**y):raise AssertionError('Saved result cannot solve')
 monkeypatch.setattr(network,'solve',forbidden);run(app)
 widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
 assert app.session_state[RESULT_KEY]==result
 widget(app,'text_input','Origem ou hipótese do modelo de serviço').set_value('Changed QA origin');run(app)
 assert RESULT_KEY not in app.session_state
 assert app.session_state.last_input==d


def test_service_missing_declaration_preserves_demand(monkeypatch):
 d=apply(load_reference(2.65,4000.,5.),'wall_girt')
 app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
 widget(app,'checkbox',LABEL).check();run(app)
 widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
 result=app.session_state[RESULT_KEY]
 assert FIELD not in result and 'Declare' in result['horizontal_service_error']
 assert saved_nbr(result) and result['status']=='conditional_elastic_vlasov_demand'
