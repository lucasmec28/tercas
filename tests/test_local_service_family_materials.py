"""Fresh 66-row service coverage with declared material variations, not a project."""
import pytest
from test_own_service_critical import data
from tercas import ue_catalog_reference as own
from tercas.application import build_spec
from tercas.catalogs import apply_material
from tercas.core.especificacao_unica import evaluate
from tercas.pierin_ue_registry import new_study_indices


@pytest.mark.parametrize('grade,custom',[
    ('USI-CIVIL 300',None),
    ('USI-CIVIL 350',None),
    ('Personalizado',{'fy_MPa':550.,'fu_MPa':600.,'origin':'Synthetic material variant'}),
])
def test_all_complete_rows_offer_local_service_for_declared_material(grade,custom):
    counts={'MSE':0,'MLE':0}
    for index in new_study_indices():
        d=apply_material(data(index),grade,custom);d['steel_name']=grade
        d=own.activate(d)
        spec=build_spec(d);result=evaluate(spec)
        assert result['ELS']['status']=='computed_bending_component',(grade,index,result['ELS'])
        assert result['ELS']['index']>=0
        assert spec['Ml_SLS']['evidence']['source_binding']['material']['fy_MPa']==d['properties']['fy_MPa']
        counts['MLE' if 'service_mle_evidence' in result['ELS'] else 'MSE']+=1
        assert result['whole_member_approved'] is False
    assert counts=={'MSE':62,'MLE':4}
