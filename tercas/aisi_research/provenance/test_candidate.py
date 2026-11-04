import math,json
from pathlib import Path
import numpy as np
import unittest
from contextlib import contextmanager
@contextmanager
def raises(cls):
    try:yield
    except cls:return
    raise AssertionError("Expected "+cls.__name__)
from aisi_candidate import flexural_floor,full_DSM,assess,ROOT

def test_bad_scalar(v):
    with raises(ValueError):flexural_floor(v,1.,1.,1.)

def test_non_symmetric_beta_rejected(b):
    with raises(ValueError):flexural_floor(1.,1.,1.,1.,b)

def test_actual_local_domain_gate():
    # A floor-based local slenderness would pass here but REAL bar<=My is not
    # sufficient to establish lambda<=5. Fail closed instead of using the floor.
    with raises(ValueError):flexural_floor(1.,1e-6,1/26.,1.)
    with raises(ValueError):flexural_floor(1.,1.,1.,1/26.)
    assert flexural_floor(1.,1.,1/25.,1/25.)['lambda_local_real_sufficient_upper']==5

def test_F2_boundary_and_continuity():
    a=flexural_floor(1.,.5,2.,2.);b=flexural_floor(1.,.5*(1+1e-10),2.,2.)
    assert a['Mne_floor_Nmm']==.5
    assert abs(b['Mne_floor_Nmm']-.5)<1e-9

def test_conservative_floor_property():
    rng=np.random.default_rng(91823)
    for i in range(10000):
        My=10**rng.uniform(3,9);Mp=My*rng.uniform(1,3);cre=My*10**rng.uniform(-4,3)
        crl=My*10**rng.uniform(math.log10(.04),3);crd=My*10**rng.uniform(math.log10(.04),3)
        floor=flexural_floor(My,cre,crl,crd);exact=full_DSM(My,Mp,cre,crl,crd,*rng.uniform(0,1,2))
        for a,b in [('Mne_floor_Nmm','Mne'),('Mnl_floor_Nmm','Mnl'),('Mnd_floor_Nmm','Mnd'),('Mn_floor_Nmm','Mn')]:
            assert floor[a]<=exact[b]*(1+1e-14)

def test_all_reference_cases_keep_approvals_false_and_scale_only_demand():
    rows=json.loads((ROOT/'inputs/elastic_inputs.json').read_text())['profiles']
    for row in rows:
        a=assess(row,4000,1);b=assess(row,4000,.01)
        assert a['flexure']==b['flexure'] and a['bimoment']==b['bimoment']
        assert math.isclose(b['H4_ratio_upper'],.01*a['H4_ratio_upper'],rel_tol=1e-14)
        assert not a['whole_member_approved'] and not a['physical_design_approved'] and not a['NBR_design_check']
        assert a['H4_sufficiency_is_conditional_on_remaining_applicability']

def test_source_registry_does_not_contain_nbr_capacities():
    text=(ROOT/'inputs/elastic_inputs.json').read_text()
    assert 'MRd_Nmm' not in text and 'local_strong_primary' not in text

if __name__=='__main__':
    for v in [True,0.,-1.,float('nan'),float('inf')]:test_bad_scalar(v)
    for b in [0.,.4,2.,float('nan')]:test_non_symmetric_beta_rejected(b)
    tests=[v for k,v in list(globals().items()) if k.startswith('test_') and k not in ['test_bad_scalar','test_non_symmetric_beta_rejected']]
    for test in tests:test()
    print(str(9+len(tests))+" checks passed; 10,000 random floor comparisons included")
