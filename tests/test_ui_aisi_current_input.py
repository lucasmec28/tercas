"""Real AppTest integration, no silent rerun or stale new component."""
import copy
from test_ui_torsion_nominal import prepared
from tercas import aisi_torsion_component as component


def test_current_component_render_and_invalidation(monkeypatch):
    app=prepared(monkeypatch)
    assert any('Verificação complementar de flexão e empenamento' in x.value for x in app.subheader)
    assert app.session_state.result[component.FIELD]['H4_computed_cases']==40
    base=copy.deepcopy(app.session_state.result)
    def forbidden(*args,**kwargs):raise AssertionError('Rendering must not recalculate current H4')
    monkeypatch.setattr(component,'_aisi_demand',forbidden)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==base
    assert any('combinações LRFD AISI' in x.value for x in app.caption)
    next(x for x in app.number_input if x.label=='CP: x a partir do CG [mm]').set_value(7.).run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
