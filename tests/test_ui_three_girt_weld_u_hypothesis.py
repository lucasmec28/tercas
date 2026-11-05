import copy
import pytest
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL,RESULT_KEY
from tercas.three_girt_axial.application import saved_component

CHOICE='Duas soldas longitudinais na mesa: Ct de U para Ue (hipótese)'
L_LABEL='L: comprimento longitudinal de cada cordão [mm]'
X_LABEL='x: distância perpendicular do centróide do Ue ao plano da ligação [mm]'
ADOPT='Adoto a hipótese extrapolada de Ct de U para Ue ligado pela mesa'


def test_weld_hypothesis_save_reject_invalidate_and_switch(monkeypatch):
    d=apply(load_reference(2.65,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox','Fornecer seções líquidas e Ct de tração').check();run(app)
    widget(app,'selectbox','Forma de informar a ligação para tração').select(CHOICE);run(app)
    assert widget(app,'number_input',L_LABEL).value is None
    assert widget(app,'number_input',X_LABEL).value is None
    assert not widget(app,'checkbox',ADOPT).value
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert saved_component(app.session_state[RESULT_KEY])['capacities']['tension']['Nt_Rd_N'] is None
    widget(app,'selectbox','Seção fora das ligações').select('Sem furos ou recortes, confirmar');run(app)
    widget(app,'checkbox','Confirmo ausência de furos e recortes fora das ligações').check()
    widget(app,'text_input','Origem de An0 e caminhos fora da ligação').set_value('Synthetic QA outside no losses')
    widget(app,'number_input',L_LABEL).set_value(100.)
    widget(app,'number_input',X_LABEL).set_value(50.)
    widget(app,'checkbox','Confirmo dois cordões longitudinais contínuos de igual comprimento na mesma mesa, sem transversais').check()
    widget(app,'checkbox','Confirmo seção da ligação sem furos, recortes ou outras perdas').check()
    widget(app,'checkbox',ADOPT).check()
    widget(app,'text_input','Origem e descrição do detalhe para tração').set_value('Synthetic QA flange plane, not actual construction')
    widget(app,'checkbox','Confirmo que os dados informados representam a referência comum de tração das três travessas').check();run(app)
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    saved=copy.deepcopy(app.session_state[RESULT_KEY]);r=saved_component(saved)
    t=r['capacities']['tension'];g=t['connection_detail']['derived']
    assert g['Ct']==pytest.approx(.82) and t['Nt_Rd_N']>0
    assert not r['whole_member_approved'] and app.session_state.last_input==d
    run(app);assert app.session_state[RESULT_KEY]==saved
    widget(app,'checkbox',ADOPT).uncheck();run(app)
    assert RESULT_KEY not in app.session_state
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert saved_component(app.session_state[RESULT_KEY])['capacities']['tension']['Nt_Rd_N'] is None
    widget(app,'checkbox',ADOPT).check()
    widget(app,'number_input',L_LABEL).set_value(20.);run(app)
    assert RESULT_KEY not in app.session_state
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    bad=saved_component(app.session_state[RESULT_KEY])['capacities']['tension']
    assert bad['Nt_Rd_N'] is None and bad['connection_detail']['derived']['Ct'] is None
    assert any('inadmissível' in w.value for w in app.error)
    widget(app,'selectbox','Forma de informar a ligação para tração').select('Solda da mesa inferior no topo da viga');run(app)
    assert RESULT_KEY not in app.session_state
    assert widget(app,'selectbox','Orientação dos cordões da mesa inferior').value=='A definir'
    widget(app,'selectbox','Forma de informar a ligação para tração').select('Manual: An0, An e Ct auditados');run(app)
    assert widget(app,'number_input','An na ligação [mm²]').value is None
    assert widget(app,'number_input','Ct de tração aplicável').value is None
    widget(app,'selectbox','Forma de informar a ligação para tração').select(CHOICE);run(app)
    # Returning after another branch cannot silently reuse the former approval.
    assert not widget(app,'checkbox',ADOPT).value
    assert widget(app,'number_input',L_LABEL).value is None
