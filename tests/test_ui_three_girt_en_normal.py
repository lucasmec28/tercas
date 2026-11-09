import copy
import pytest
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
    app=imported(monkeypatch,d)
    assert app.session_state.last_input==d  # Import does not migrate legacy input.
    from tercas.current_calculation_inputs import prepare
    adopted=prepare(d)
    assert set(adopted).difference(d)=={'load_application_policy','local_support_verification_scope'}
    assert {k:v for k,v in adopted.items() if k not in ('load_application_policy','local_support_verification_scope')}==d
    widget(app,'checkbox',WARPING).check();run(app)
    assert widget(app,'checkbox',LABEL).value is False
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox',MODEL_LABEL).check()
    widget(app,'text_input','Origem ou hipótese da seção nominal EN').set_value('Synthetic QA intact section; not a physical survey')
    run(app);widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    original=copy.deepcopy(app.session_state[RESULT_KEY])
    assert FIELD in original and saved_component(original) is not None and saved_nbr(original) is not None
    assert original[FIELD]['component_sections']['components']['My_negative']['eligible']
    assert all(item['complete'] for item in original[FIELD]['per_member'].values())
    assert original[FIELD]['whole_member_approved'] is False
    def forbidden(*args,**kwargs):raise AssertionError('Read-only display/export cannot solve')
    monkeypatch.setattr(network,'solve',forbidden)
    run(app);assert app.session_state[RESULT_KEY]==original
    widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state[RESULT_KEY]==original
    widget(app,'text_input','Origem ou hipótese da seção nominal EN').set_value('Changed model declaration');run(app)
    assert RESULT_KEY not in app.session_state
    assert app.session_state.last_input==adopted


def test_EN_missing_declaration_preserves_demand_and_NBR(monkeypatch):
    d=apply(load_reference(2.65,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    result=app.session_state[RESULT_KEY]
    assert FIELD not in result and 'Declare' in result['EN_normal_N_M_B_error']
    assert saved_nbr(result) is not None
    assert result['status']=='conditional_elastic_vlasov_demand'


@pytest.mark.parametrize('t',[1.2,1.5,2.])
def test_reduced_axial_coexists_with_service_and_saved_exports(monkeypatch,t):
    from tercas.three_girt_service.ui import LABEL as SERVICE, INTACT
    from tercas.three_girt_service import application as service
    from tercas.three_girt_en_normal import application as en
    from tercas.three_girt_warping.report import word
    if t==1.2:
        from tercas import ue_reference
        d=apply(ue_reference.load_reference(angle=5.,L_mm=4000.),'wall_girt')
    else:d=apply(load_reference(t,4000.,5.),'wall_girt')
    app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
    widget(app,'checkbox',SERVICE).check();widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox',INTACT).check();widget(app,'checkbox',MODEL_LABEL).check()
    widget(app,'text_input','Origem ou hipótese do modelo de serviço').set_value('Synthetic service / reduced axial QA')
    widget(app,'text_input','Origem ou hipótese da seção nominal EN').set_value('Synthetic service / reduced axial QA')
    run(app);widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    original=copy.deepcopy(app.session_state[RESULT_KEY])
    saved=en.saved_component(original)
    assert saved and saved_nbr(original) and service.saved_component(original)
    assert saved['component_sections']['components']['N_compression']['moment_transport_required']
    assert all(item['complete'] for item in saved['per_member'].values())
    assert saved['component_sections']['components']['My_negative']['eligible']
    for item in saved['per_member'].values():
        normal=item['normal']
        assert normal['index_upper_bound'] is not None
        assert normal['index_lower_witness'] is None or normal['index_upper_bound']>=normal['index_lower_witness']
    assert all(saved[name] is False for name in en.FALSE_FLAGS)
    def forbidden(*args,**kwargs):raise AssertionError('Saved reduced axial UI/export cannot solve')
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(en,'calculate',forbidden)
    monkeypatch.setattr(service,'calculate',forbidden)
    run(app);widget(app,'selectbox','Combinação Vlasov 3D detalhada').select(2);run(app)
    assert app.session_state[RESULT_KEY]==original
    assert word(original)[:2]==b'PK'


def test_EN_6_27_is_available_with_NBR_disabled(monkeypatch):
    from tercas.three_girt_axial.ui import LABEL as NBR_LABEL
    from tercas.three_girt_axial.application import FIELD as NBR_FIELD
    from tercas import three_girt_en_mv as mv
    from tercas.three_girt_warping.report import word
    from docx import Document
    from io import BytesIO
    d=apply(load_reference(3.35,4000.,5.),'wall_girt')
    d['selected_types']=['ELU normal']
    app=imported(monkeypatch,d);widget(app,'checkbox',WARPING).check();run(app)
    widget(app,'checkbox',NBR_LABEL).uncheck();widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'checkbox',MODEL_LABEL).check()
    widget(app,'text_input','Origem ou hipótese da seção nominal EN').set_value('Synthetic independent EN6.27 UI QA')
    run(app);widget(app,'button','Calcular três travessas Vlasov e G8.1').click();run(app)
    assert not app.exception
    result=copy.deepcopy(app.session_state[RESULT_KEY]);source=saved_component(result)
    assert NBR_FIELD not in result and source['EN_bending_shear_schema']==mv.COLLECTION_SCHEMA
    assert all('EN_bending_shear_component' in r for r in source['rows'])
    table=next(w.value for w in app.dataframe if 'Teto_interação_N_M_V_EN' in w.value.columns)
    assert list(table['Travessa'])==['Central'] and table['Teto_interação_N_M_V_EN'].notna().all()
    text='\n'.join(p.text for p in Document(BytesIO(word(result))).paragraphs)
    assert 'Interação N–M–V e cortantes pela EN' in text and 'Mf=0' in text
    def forbidden(*args,**kwargs):raise AssertionError('Independent EN read must not calculate')
    monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(mv,'populate',forbidden)
    run(app);assert app.session_state[RESULT_KEY]==result
    widget(app,'checkbox',LABEL).uncheck();run(app)
    assert RESULT_KEY not in app.session_state
