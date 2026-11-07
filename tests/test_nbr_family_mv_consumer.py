"""Pure source-to-presentation integration; no eigen/member solver."""
import copy
import pytest
from tercas import nbr_ue_family_application as app, nbr_family_panorama as panorama
from tercas import nbr_ue_family_ui as ui, ue_catalog_reference as own
from test_nbr_ue_family_application import source
from test_nbr_family_shear_lag_consumer import short


@pytest.mark.parametrize('index',[0,26,79,80,81,82])
def test_own_local_capacity_not_absent_legacy_Ml_drives_MV(index):
    result=app.attach(source(index));row=result[app.FIELD]['records'][0];mv=row['strong_web_MV']
    assert result['input_data']['Ml_Nmm'] is None
    assert mv['arithmetic'] is not None and mv['own_contour_only'] and not mv['FLT_distortional_denominator_used']
    assert mv['local_source']['MRd_Nmm']==result[app.FIELD]['sources']['own_rounded_contour']['strong']['local']['MRd_Nmm']
    assert mv['web_shear']['index_upper']>=mv['web_shear']['index_lower']
    result['model_domain_evidence']=dict(status='fixed_model_domain',conflict=False)
    old=[dict(id='ELU:DIRECT_ELU:'+s,status='pending') for s in ('MV','shear')]
    records,binding=panorama.apply(result,old)
    assert len([r for r in records if r['id']=='ELU:DIRECT_ELU:MV'])==1
    assert next(r for r in records if r['id']=='ELU:DIRECT_ELU:MV')['status']==mv['criterion_status']
    assert next(r for r in records if r['id']=='ELU:DIRECT_ELU:shear')['status']==mv['web_shear']['criterion_status']
    result['global_verification']={'checks':records,panorama.BINDING:binding};panorama.validate_saved(result)
    assert len(ui.web_rows(result[app.FIELD]))==1
    bad=copy.deepcopy(result);bad[app.FIELD]['records'][0]['strong_web_MV']['web_shear']['index_upper']=0.
    bad[app.FIELD]['snapshot_sha256']=own.digest(bad[app.FIELD])
    with pytest.raises(ValueError):app.preserved(bad)


def test_pending94_keeps_independent_web_shear_but_not_MV():
    result=app.attach(short());row=result[app.FIELD]['records'][0];mv=row['strong_web_MV']
    assert mv['arithmetic'] is None and mv['criterion_status'] is None
    assert mv['web_shear']['criterion_status'] in ('meets','fails')
    result['model_domain_evidence']=dict(status='fixed_model_domain',conflict=False)
    records,_=panorama.apply(result,[])
    assert next(r for r in records if r['id']=='ELU:DIRECT_ELU:MV')['status']=='pending'
    assert next(r for r in records if r['id']=='ELU:DIRECT_ELU:shear')['status']==mv['web_shear']['criterion_status']


def test_forged_panorama_MV_and_missing_shear_rejected():
    result=app.attach(source());result['model_domain_evidence']=dict(status='fixed_model_domain',conflict=False)
    records,binding=panorama.apply(result,[]);result['global_verification']={'checks':records,panorama.BINDING:binding}
    for key in ('MV','shear'):
        bad=copy.deepcopy(result);bad['global_verification']['checks']=[r for r in bad['global_verification']['checks'] if r['id']!='ELU:DIRECT_ELU:'+key]
        with pytest.raises(ValueError):panorama.validate_saved(bad)
