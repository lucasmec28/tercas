"""Exact strong reference geometry, unchanged weak proof, no solver."""
import copy
from fractions import Fraction as F
import json
import math
import subprocess
import sys

import pytest

from tercas import nbr_ue_shear_lag as legacy, nbr_ue_shear_lag_strong as current
from tercas import pierin_ue_registry as registry

DIMS = dict(h=200., bf=75., lip=20., t=2.)


def params(L=2790., P=1., Py=0., dims=None, ri=3.):
    return dict(physical_span_mm=L, external_dimensions_mm=copy.deepcopy(DIMS if dims is None else dims),
                inner_radius_mm=ri, actions=[dict(kind='point',P_down_N=P,P_parallel_N=Py,s_mm=L/2)],
                member_model=current.MEMBER_MODEL)


def old(inputs):
    return legacy.assess(**{k:v for k,v in inputs.items() if k!='inner_radius_mm'})


@pytest.mark.parametrize('L,expected', [(math.nextafter(2790.,-math.inf),False), (2790.,True),
                                       (math.nextafter(2790.,math.inf),True), (2849.,True), (2850.,True)])
@pytest.mark.parametrize('sign',[1.,-1.])
def test_exact_strong_threshold_inclusive_and_sign_independent(L,expected,sign):
    r=current.assess(**params(L,P=sign));axis=r['axes']['normal']
    assert axis['qualified'] is expected
    assert axis['bf0_exact_mm']=='93' and axis['bf0_exact_determined']
    assert axis['sufficient_span_exact_mm']=='2790'
    assert not r['reductions_applied'] and not r['section_properties_changed']


@pytest.mark.parametrize('L',[2790.,2800.,2849.,math.nextafter(2850.,-math.inf)])
def test_narrow_old_pending_band_recovers_only_span_dispensation(L):
    p=params(L);a=old(p);b=current.assess(**p)
    assert not a['axes']['normal']['qualified']
    assert b['axes']['normal']['qualified']
    assert b['axes']['normal']['previous_external_bound']==a['axes']['normal']
    assert b['schema']!=a['schema']


@pytest.mark.parametrize('Py',[0.,1.,-1.,1e-300,-1e-300])
@pytest.mark.parametrize('L',[1000.,2790.,5999.,6000.])
def test_entire_weak_record_is_byte_equivalent(Py,L):
    p=params(L,Py=Py)
    assert current.assess(**p)['axes']['parallel']==old(p)['axes']['parallel']


def test_q_only_short_span_no_point_reactions_and_opposing_individual_points():
    p=params(1000.);p['actions']=[dict(kind='uniform',q_down_N_mm=-2.,q_parallel_N_mm=1.)]
    assert current.assess(**p)['qualified']
    p['actions'] += [dict(kind='point',P_down_N=v,P_parallel_N=0.,s_mm=500.) for v in (1.,-1.)]
    r=current.assess(**p)
    assert not r['axes']['normal']['qualified']
    assert r['axes']['normal']['concentrated_action_indices']==[1,2]
    assert not r['support_reactions_invented'] and not r['multiple_point_spacing_exemption_used']


def test_radius_affects_flat_geometry_not_reference_projection():
    a=current.assess(**params(ri=1.));b=current.assess(**params(ri=4.))
    ag=a['axes']['normal']['reference_geometry'];bg=b['axes']['normal']['reference_geometry']
    assert ag['bf0_exact_mm']==bg['bf0_exact_mm']=='93'
    assert ag['local_flange_flat_exact_mm']!=bg['local_flange_flat_exact_mm']
    assert not ag['flat_width_substituted_for_projection']


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_all66_documented_geometries_and_exact_binary_frontier(index):
    row=registry.select_new_study(index,include_routes=False);d=row['dimensions_mm']
    threshold=30*(F(d['bf'])-F(d['t'])+F(d['lip']))
    L=float(threshold)
    p=params(L,dims=d,ri=row['published_properties']['ri_mm'])
    b=current.assess(**p)
    assert b['axes']['normal']['qualified'] is (F(L)>=threshold)
    assert b['axes']['normal']['bf0_exact_mm']==str(threshold/30)
    assert F(b['axes']['normal']['sufficient_span_upper_mm'])>=threshold
    assert b['axes']['parallel']==old(p)['axes']['parallel']


@pytest.mark.parametrize('ri',[True,None,-1.,float('nan'),float('inf'),100.])
def test_invalid_or_nonfitting_radius_rejected(ri):
    with pytest.raises(ValueError):current.assess(**params(ri=ri))


def test_json_exact_replay_and_input_immutability():
    p=params();before=copy.deepcopy(p);r=current.assess(**p)
    assert p==before
    assert current.validate_saved(json.loads(json.dumps(r)),**p)==r
    for field in ('bf0_exact_mm','qualified','bf0_exact_determined'):
        bad=copy.deepcopy(r);bad['axes']['normal'][field]=None
        with pytest.raises(ValueError):current.validate_saved(bad,**p)


def test_scalar_import_does_not_load_numpy_or_section_solver():
    subprocess.run([sys.executable,'-c','import sys; from tercas import nbr_ue_shear_lag_strong; assert "numpy" not in sys.modules'],check=True)
