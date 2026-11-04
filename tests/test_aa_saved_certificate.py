"""Adversarial saved-data consistency checks and exact saved-root certificates."""
import copy,math
from fractions import Fraction as F
import pytest
from tercas import aa_component as aa,ue_family_reference as family
from tercas.application import calculate,rows
from tercas.report import word
from tercas.aa_component_ui import _read
from tercas.aa_saved_certificate import _saved_roots,_interval_horner


def direct():
    d=family.load_reference(1.5,4000.,5.)
    d.update(load_mode='direct',q_sls=.1,q_parallel_sls=.03,P_sls=100.,P_parallel_sls=-20.,x_sls=1700.)
    return d


@pytest.fixture(scope='module')
def base():return calculate(aa.activate(direct()))


def reseal(r):
    s=r[aa.FIELD];rec=s['records']['DIRECT_ELS'];rec['response_sha256']=aa.digest(rec['response'])
    r['ELS']=aa._raw(rec);s['snapshot_sha256']=aa.digest({k:v for k,v in s.items() if k!='snapshot_sha256'})


@pytest.mark.parametrize('kind',['missing_green','zero_teto','green_coeff','curvature','missing_root','bad_root_value','bad_wall','null_gross','null_bound','bad_material','bad_stiffener','global','combined','source'])
def test_locally_contradictory_rehashed_snapshots_refused(base,kind):
    r=copy.deepcopy(base);rec=r[aa.FIELD]['records']['DIRECT_ELS'];response=rec['response'];b=response['displacement_component_bounds'][0]
    if kind=='missing_green':b.pop('lower_displacement_polynomials')
    elif kind=='zero_teto':b.update(absolute_max_upper_mm=0.,absolute_max_upper_fraction=['0','1'])
    elif kind=='green_coeff':b['lower_displacement_polynomials'][0][2]=['1','1']
    elif kind=='curvature':b['lower_curvature_controls'][0][1]=['0','1']
    elif kind=='missing_root':
        assert b['extrema_root_enclosures'][0];b['extrema_root_enclosures'][0].pop()
    elif kind=='bad_root_value':
        assert b['extrema_root_enclosures'][0];b['extrema_root_enclosures'][0][0][2][0]=['0','1']
    elif kind=='bad_wall':response['gross_evidence']['walls'][0]['full_wall_sufficient']=False
    elif kind=='null_gross':response['gross_evidence']=None
    elif kind=='null_bound':response['displacement_component_bounds'][1]=None
    elif kind=='bad_material':response['gross_evidence']['maximum_absolute_normal_stress_upper_MPa']=251.
    elif kind=='bad_stiffener':
        wall=next(w for w in response['gross_evidence']['walls'] if 'flange' in w['wall'] and w.get('Ia_monotone_upper_mm4') is not None)
        wall['Ia_monotone_upper_mm4']=1e100
    elif kind=='global':r['whole_member_approved']=True
    elif kind=='combined':r['combined_ELS_approved']=True
    else:r['ue_family_reference_evidence']['model']['E_MPa']=1.
    reseal(r)
    with pytest.raises((ValueError,TypeError,KeyError,ArithmeticError)):aa.preserved_snapshot(r)
    assert _read(r)[1] is not None
    assert next(x for x in rows(r) if x['Verificação']==aa.ROW)['Índice'] is None
    assert word(r)


@pytest.mark.parametrize('exception',[RuntimeError,ImportError,OSError])
def test_runtime_or_integrity_failure_blocks_whole_emission_as_readable_error(monkeypatch,exception):
    def failure():raise exception('Injected unavailable AA runtime/source')
    monkeypatch.setattr(aa,'_bundle',failure)
    with pytest.raises(ValueError,match='cálculo não emitido'):calculate(aa.activate(direct()))


def pair(x):return [str(x.numerator),str(x.denominator)]
def saved(coeff,interval):return [0,[pair(x) for x in interval],[pair(x) for x in _interval_horner(coeff,interval)]]


def test_saved_root_count_no_new_search_and_boundary_enclosures():
    # d' = epsilon - t: one non-endpoint root with enclosure touching 0.
    e=F(1,2**200);c=[F(0),e,F(-1,2),F(0),F(0)]
    interval=(F(0),F(1,2**96));record=saved(c,interval)
    assert _saved_roots(c,[record],0,aa._pair)
    with pytest.raises(ValueError):_saved_roots(c,[],0,aa._pair)
    # A root close to 1 may have a valid saved interval touching 1.
    c=[F(0),1-e,F(-1,2),F(0),F(0)];interval=(1-F(1,2**96),F(1))
    assert _saved_roots(c,[saved(c,interval)],0,aa._pair)


def test_repeated_root_and_endpoint_factors_are_counted_exactly():
    # d' = (t-1/2)^2: one DISTINCT repeated interior root.
    c=[F(0),F(1,4),F(-1,2),F(1,3),F(0)]
    one=saved(c,(F(1,2),F(1,2)))
    assert _saved_roots(c,[one],0,aa._pair)
    with pytest.raises(ValueError):_saved_roots(c,[one,one],0,aa._pair)
    # d' = t*(t-1)*(t-1/2): endpoints are not interior witnesses.
    c=[F(0),F(0),F(1,4),F(-1,2),F(1,4)]
    assert _saved_roots(c,[saved(c,(F(1,2),F(1,2)))],0,aa._pair)
    with pytest.raises(ValueError):_saved_roots(c,[saved(c,(F(0),F(0)))],0,aa._pair)


def test_fake_interval_that_contains_no_critical_point_is_rejected():
    c=[F(0),F(1,2),F(-1,2),F(0),F(0)]
    with pytest.raises(ValueError):_saved_roots(c,[saved(c,(F(1,8),F(1,4)))],0,aa._pair)


def test_web_guard_contradiction_and_green_support_link_are_rejected():
    d=direct();d.update(q_sls=0.,q_parallel_sls=.305,P_sls=0.,P_parallel_sls=0.,x_sls=2000.)
    original=calculate(aa.activate(d));assert original[aa.FIELD]['bounded_cases']==1
    r=copy.deepcopy(original);rec=r[aa.FIELD]['records']['DIRECT_ELS']
    hull=rec['response']['hull_evidence'];row=next(x for x in hull['controls'] if not x['zero_identity'])
    row['guards']['walls'][0]['full_sufficient']=False;reseal(r)
    with pytest.raises(ValueError):aa.preserved_snapshot(r)
    r=copy.deepcopy(original);b=r[aa.FIELD]['records']['DIRECT_ELS']['response']['displacement_component_bounds'][0]
    b['lower_curvature_controls'][0][1]=['0','1'];reseal(r)
    with pytest.raises(ValueError):aa.preserved_snapshot(r)


def test_duplicate_singletons_cannot_replace_a_different_root():
    # d'=(t-1/4)*(t-3/4); duplicated 1/4 must not stand for missing 3/4.
    c=[F(0),F(3,16),F(-1,2),F(1,3),F(0)]
    one=saved(c,(F(1,4),F(1,4)));two=saved(c,(F(3,4),F(3,4)))
    assert _saved_roots(c,[one,two],0,aa._pair)
    with pytest.raises(ValueError):_saved_roots(c,[one,one],0,aa._pair)


def test_interval_endpoint_root_cannot_be_counted_again_as_singleton():
    c=[F(0),F(3,16),F(-1,2),F(1,3),F(0)]
    interval=saved(c,(F(1,8),F(1,4)));singleton=saved(c,(F(1,4),F(1,4)))
    with pytest.raises(ValueError):_saved_roots(c,[interval,singleton],0,aa._pair)
