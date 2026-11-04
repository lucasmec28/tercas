import copy
from test_ui_own_girt_application import imported,widget,run
from tercas.ue_family_reference import load_reference
from tercas.ue_member_application import apply
from tercas.three_girt_warping.ui import LABEL,RESULT_KEY
from tercas.three_girt_axial.application import saved_component


def test_simple_row_save_invalidate_and_manual_switch(monkeypatch):
    d=apply(load_reference(2.65,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox','Fornecer seções líquidas e Ct de tração').check();run(app)
    assert widget(app,'selectbox','Forma de informar a ligação para tração').value=='Manual: An0, An e Ct auditados'
    widget(app,'selectbox','Forma de informar a ligação para tração').select('Parafusos na alma, uma fileira vertical');run(app)
    assert widget(app,'number_input','Parafusos na vertical').value==2
    assert widget(app,'selectbox','Diâmetro nominal do parafuso').value=='Selecione o diâmetro'
    widget(app,'selectbox','Seção fora das ligações').select('Sem furos ou recortes, confirmar');run(app)
    widget(app,'checkbox','Confirmo ausência de furos e recortes fora das ligações').check()
    widget(app,'text_input','Origem de An0 e caminhos fora da ligação').set_value('QA synthetic no outside holes')
    widget(app,'selectbox','Diâmetro nominal do parafuso').select('Ø1/2″ (12,7 mm)')
    widget(app,'number_input','Passo vertical regular entre centros [mm]').set_value(50.)
    widget(app,'checkbox','Confirmo uma única fileira vertical, na mesma seção transversal, inteiramente na alma plana').check()
    widget(app,'checkbox','Confirmo que esta seção não possui outros furos ou recortes').check()
    widget(app,'text_input','Origem e descrição do detalhe para tração').set_value('QA synthetic, not an actual connection')
    widget(app,'checkbox','Confirmo que os dados informados representam a referência comum de tração das três travessas').check();run(app)
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    saved=copy.deepcopy(app.session_state[RESULT_KEY]);r=saved_component(saved)
    assert r['capacities']['tension']['Nt_Rd_N']>0
    assert r['capacities']['tension']['connection_detail']['derived']['hole_diameter_mm']==14.7
    assert not r['whole_member_approved'] and app.session_state.last_input==d
    run(app);assert app.session_state[RESULT_KEY]==saved
    widget(app,'number_input','Passo vertical regular entre centros [mm]').set_value(51.);run(app)
    assert RESULT_KEY not in app.session_state
    widget(app,'selectbox','Forma de informar a ligação para tração').select('Manual: An0, An e Ct auditados');run(app)
    assert widget(app,'number_input','An na ligação [mm²]').value is None
    assert widget(app,'number_input','Ct de tração aplicável').value is None
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert saved_component(app.session_state[RESULT_KEY])['capacities']['tension']['Nt_Rd_N'] is None


def test_weld_selection_alone_is_pending_and_branch_switch_clears(monkeypatch):
    d=apply(load_reference(2.65,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox','Fornecer seções líquidas e Ct de tração').check();run(app)
    widget(app,'selectbox','Forma de informar a ligação para tração').select('Solda da mesa inferior no topo da viga');run(app)
    assert widget(app,'selectbox','Orientação dos cordões da mesa inferior').value=='A definir'
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert saved_component(app.session_state[RESULT_KEY])['capacities']['tension']['Nt_Rd_N'] is None
    widget(app,'selectbox','Orientação dos cordões da mesa inferior').select('Somente transversais');run(app)
    widget(app,'number_input','Área bruta somente das partes efetivamente conectadas [mm²]').set_value(80.)
    run(app)
    widget(app,'selectbox','Orientação dos cordões da mesa inferior').select('Longitudinais');run(app)
    assert widget(app,'number_input','An auditado para a solda da mesa inferior [mm²]').value is None
    assert widget(app,'number_input','Ct auditado para a solda da mesa inferior').value is None
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert saved_component(app.session_state[RESULT_KEY])['capacities']['tension']['Nt_Rd_N'] is None
