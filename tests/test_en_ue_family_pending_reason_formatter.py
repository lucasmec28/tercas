"""Pure formatting of synthetic validated views; no solver, UI or snapshots."""
import copy

import pytest

from tercas import isolated_en_ue_family_ui as ui


OLD_REASON='Dispensa antiga v3: Le>50b0'


def view(supplement=None):
    check=dict(component_status=dict(stress='pending',mv='pending',shear='computed'),
        stress=dict(criteria={}),shear={},mv=dict(reason=OLD_REASON),
        shear_source_snapshot=dict(shear_capacity_lower_N={}),
        applicability=dict(qualified=False,reason=OLD_REASON))
    if supplement is not None:check['concurrent_shear_lag_supplement']=supplement
    return dict(material=dict(fya_MPa=300,fyb_MPa=300,gamma_M0=1),
        configuration=dict(model_origin='Synthetic formatter only'),
        shear_computed_cases=1,stress_computed_cases=0,mv_computed_cases=0,
        partial_cases=1,pending_demand_cases=0,ELS_cases_excluded=0,
        records=[dict(combination_id='ULS',status='pending',reason=OLD_REASON,check=check)])


def test_pending_simultaneous_ceiling_replaces_legacy_reasons_without_mutation():
    ev=view(dict(eligible=False,blocking_reasons=[
        dict(code='SIMULTANEOUS_LOCAL_D_CEILING_NOT_PROVED',stress_upper_MPa=154.36,ceiling_MPa=35.74),
        dict(code='UNIFORM_LOCAL_D_REFERENCE_NOT_QUALIFIED',stress_upper_MPa=154.36,ceiling_MPa=35.74)]))
    ev['records'][0]['check']['stress']['criteria']={
        name:dict(diagnostic_index_upper_bound=2.0,reason=OLD_REASON,
            criterion='Synthetic '+name,bound_control=None)
        for name in ('normal','interaction')}
    before=copy.deepcopy(ev)
    reason=ui.rows(ev)[0]['Motivo']
    lines=ui.text_lines(ev)
    assert '154.36 MPa' in reason and '35.74 MPa' in reason
    assert 'Condição suficiente local/distorcional simultânea não demonstrada' in reason
    assert 'sem inferência de reprovação física' in reason
    assert reason.count('35.74')==1
    assert OLD_REASON not in reason and OLD_REASON not in '\n'.join(lines)
    assert 'ULS: shear lag simultâneo pendente: '+reason in next(x for x in lines if 'shear lag simultâneo pendente:' in x)
    assert 'Aplicabilidade pendente: '+reason in lines
    assert ev==before


@pytest.mark.parametrize('code,expected',[
    ('UNIFORM_LOCAL_D_REFERENCE_NOT_QUALIFIED','Referência uniforme local/distorcional não qualificada'),
    ('PURE_COMPONENT_CURLING_NOT_QUALIFIED','curling das componentes puras não demonstrada nos eixos Mx, My'),
    ('SOURCE_SIGNED_OPERATOR_NOT_QUALIFIED','operadores resistentes por sentido da fonte não demonstrada'),
    ('CONCURRENT_SHEAR_LAG_REFERENCE_NOT_QUALIFIED','referência de shear lag simultâneo não demonstrada'),
])
def test_remaining_guard_messages(code,expected):
    check=dict(concurrent_shear_lag_supplement=dict(eligible=False,
        blocking_reasons=[dict(code=code,axes=['Mx','My'])]))
    reason=ui._concurrent_pending_reason(check)
    assert expected in reason
    assert 'sem inferência de reprovação física' in reason


@pytest.mark.parametrize('supplement',[None,dict(eligible=True,blocking_reasons=[])])
def test_absent_or_eligible_supplement_keeps_old_reason(supplement):
    ev=view(supplement)
    assert ui._concurrent_pending_reason(ev['records'][0]['check']) is None
    assert ui.rows(ev)[0]['Motivo']==OLD_REASON
    if supplement is not None:
        supplement.update(pure_Mx_construction={},pure_My_construction={},
            simultaneous_normal_stress_upper_MPa=10,integral_local_D_design_ceiling_MPa=35.74)
    assert 'Aplicabilidade pendente: '+OLD_REASON in ui.text_lines(ev)
