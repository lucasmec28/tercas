"""Scalar regressions and exact witnesses; no eigensolver or physical validation."""
import copy
import inspect
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction as Q

import pytest

from tercas import nbr_ue_strong_distortional_floor as floor
from tercas import nbr_ue_family_base as base


INDICES = base.registry.new_study_indices()


def material(fy=300.):
    return dict(base.DEFAULT_MATERIAL, fy_MPa=fy)


def decimal(value):
    value = Q(value)
    return Decimal(value.numerator)/Decimal(value.denominator)


@pytest.mark.parametrize('index', INDICES)
@pytest.mark.parametrize('fy', [250., 300., 345., 350.])
def test_all_66_contours_and_four_materials_have_positive_independent_floor(index, fy):
    result = floor.assess(index, material=material(fy))
    assert len(INDICES) == 66
    assert result['eligible'] and result['elastic_approximation']
    assert result['approximate_model_lower_bound']
    for key in ('Fcrd_lower_bound_MPa', 'Mdist_lower_bound_Nmm', 'MRd_lower_bound_Nmm'):
        assert math.isfinite(result[key]) and result[key] > 0
    assert result['source_binding']['material'] == material(fy)
    assert result['proof']['all_positive_halfwaves']
    assert result['proof']['coefficients_strictly_positive']
    assert not any(result[k] for k in (
        'physical_resistance_bound', 'exact_modal_eigenvalue',
        'finite_member_eigenvalue_qualified', 'member_length_required',
        'effective_lengths_used', 'physical_supports_created', 'demand_span_changed',
        'moment_gradient_credit_used', 'panel_restraint_credit_used',
        'pierin_criticals_transferred', 'weak_axis_qualified', 'biaxial_qualified',
        'primary_torsion_assessed', 'actual_load_capacity_qualified',
        'whole_member_approved', 'failure_proven'))
    coeff = {k:Q(v) for k,v in result['proof']['coefficients_exact'].items()}
    a, b, c, C, d = (coeff[k] for k in ('a','b','c','C','d'))
    with localcontext() as ctx:
        ctx.prec = 90
        reference = (decimal(b)+2*decimal(a*c).sqrt())/decimal(C+d)
        got = Decimal.from_float(result['Fcrd_lower_bound_MPa'])
        assert got <= reference
        assert got/reference > Decimal('0.999999999999999')
        W = decimal(result['geometry']['Sfc_exact_fraction'])
        assert Decimal.from_float(result['Mdist_lower_bound_Nmm']) <= got*W
        md = Decimal.from_float(result['Mdist_lower_bound_Nmm'])
        lam = (W*decimal(fy)/md).sqrt()
        rho = min(Decimal(1), (lam-Decimal('.22'))/lam**2) if lam > Decimal('.673') else Decimal(1)
        resistance = W*decimal(fy)*rho/decimal(material(fy)['gamma'])
        assert Decimal.from_float(result['MRd_lower_bound_Nmm']) <= resistance
    assert Q(result['MRd_lower_bound_Nmm']) <= Q(result['resistance_proof']['exact_MRd_floor_fraction'])


@pytest.mark.parametrize('index', INDICES)
def test_bound_below_full_formula_over_many_halfwaves_with_exact_arithmetic(index):
    result = floor.assess(index)
    c = {k:Q(v) for k,v in result['proof']['coefficients_exact'].items()}
    h = Q(result['geometry']['flange_lip_exact']['h_mm'])
    lower = Q(result['Fcrd_lower_bound_MPa'])
    # Spot witnesses supplement the algebraic proof, not a sampled minimum claim.
    for exponent in range(-12, 13):
        q = Q(2)**exponent/h
        s = (q*h)**2
        R = (s*s+8*s+300)/(s*s+28*s+420)
        value = (c['a']*q*q+c['b']+c['c']/(q*q))/(c['C']+c['d']*R)
        assert 0 < R < 1
        assert lower < value


def test_existing_exact_scope_witness_and_current_formula_have_same_model():
    from tercas import ue_catalog_nbr_distortional as legacy
    from tercas import ue_catalog_nbr_bending as old_binding
    new = floor.assess(26)
    old = legacy._elastic()
    c, properties = floor._coefficients(old_binding.GEOMETRY, material())
    for key in ('Af_mm2','Jf_mm4','Ixf_mm4','Iyf_mm4','Ixyf_mm4','Cwf_mm6','xof_mm','xhf_mm','yof_mm'):
        assert float(properties[key]) == pytest.approx(old['flange_lip'][key], rel=1e-14)
    q = math.pi/old['Lcrd_mm']
    s = (q*old['ho_mm'])**2
    R = (s*s+8*s+300)/(s*s+28*s+420)
    value = (float(c['a'])*q*q+float(c['b'])+float(c['c'])/(q*q))/(float(c['C'])+float(c['d'])*R)
    assert value == pytest.approx(old['Fcrd_MPa'], rel=1e-14)
    assert new['Fcrd_lower_bound_MPa'] == pytest.approx(718.4641551446908)
    assert new['Mdist_lower_bound_Nmm'] < old['Mdist_Nmm']
    assert new['MRd_lower_bound_Nmm'] == pytest.approx(5154709.919603469)
    assert new['geometry']['global_Ix_mm4'] == old['global_Ix_mm4']
    assert new['source_binding']['nodes_sha256'] == old_binding.PIN['nodes_sha256']


def test_existing_Lcr_is_not_promoted_to_full_ratio_minimum():
    result = floor.assess(26)
    c = {k:Q(v) for k,v in result['proof']['coefficients_exact'].items()}
    # At the numerator minimum N'=0, but R' need not vanish:
    # R'=(20*s²+240*s-5040)/(...)², nonzero at this actual s.
    q2 = math.sqrt(float(c['c']/c['a']))
    h = Q(result['geometry']['flange_lip_exact']['h_mm'])
    s = q2*float(h*h)
    assert 20*s*s+240*s-5040 != 0
    assert not result['proof']['exact_minimum_claimed']
    assert result['proof']['existing_Lcr_minimizes'].startswith('Only')


@pytest.mark.parametrize('index', INDICES[::13])
@pytest.mark.parametrize('m', [material(),dict(material(),E_MPa=210000.,G_MPa=81000.,nu=.27)])
def test_independent_original_stiffness_equations_at_multiple_q(index,m):
    row = base.registry.select_new_study(index,include_routes=False)
    p = dict(row['dimensions_mm'],ri_mm=row['published_properties']['ri_mm'],Ix_cm4=1.)
    old = base.elastic_distortion(p,m)
    f = old['flange_lip']
    h,t,E,G,nu = p['h'],p['t'],m['E_MPa'],m['G_MPa'],m['nu']
    coefficients,_ = floor._coefficients(p,m)
    a,b,c,C,d = [float(coefficients[k]) for k in ('a','b','c','C','d')]
    H = f['Cwf_mm6']+f['Ixf_mm4']*(f['xof_mm']-f['xhf_mm'])**2*(1-f['Ixyf_mm4']**2/(f['Ixf_mm4']*f['Iyf_mm4']))
    for multiplier in (.001,.01,.1,1.,10.,100.,1000.):
        q = multiplier/h
        u = q*h
        kfe = q**4*E*H+q*q*G*f['Jf_mm4']
        kwe = E*t**3/(12*(1-nu*nu))*(3/h)*(1+2*u*u/15+u**4/720)
        kfg = q*q*(f['Ixf_mm4']+f['Iyf_mm4']+f['Af_mm2']*(f['xhf_mm']**2+f['yof_mm']**2-2*f['yof_mm']*(f['xof_mm']-f['xhf_mm'])*f['Ixyf_mm4']/f['Iyf_mm4']))
        kwg = q*q*t*h**3/240*(1110+810*(1-2)+8*u*u+u**4)/(420+28*u*u+u**4)
        original = (kfe+kwe)/(kfg+kwg)
        R = (u**4+8*u*u+300)/(u**4+28*u*u+420)
        rewritten = (a*q*q+b+c/(q*q))/(C+d*R)
        assert rewritten == pytest.approx(original,rel=2e-14)


def test_short_span_gap_can_use_floor_without_changing_legacy_or_inventing_Lm():
    old = base.assess(26, L_mm=10.)
    assert not old['strong']['distortional']['eligible']
    result = floor.assess(26)
    assert result['eligible']
    assert not result['member_length_required']
    assert set(inspect.signature(floor.assess).parameters) == {'index','material','Msd_Nmm'}
    assert base.assess(26, L_mm=10.) == old
    for key in ('L_mm','Lm_mm','Ly_mm','Lz_mm','lengths'):
        with pytest.raises(TypeError):
            floor.assess(26, **{key:10.})


def test_material_inputs_preserved_and_fy_does_not_change_elastic_floor():
    first = floor.assess(26, material=material(250.))
    for fy in (300.,345.,350.):
        other = floor.assess(26, material=material(fy))
        for key in ('Fcrd_lower_bound_MPa','Mdist_lower_bound_Nmm','geometry','proof'):
            assert other[key] == first[key]
    different_E = floor.assess(26, material=dict(material(), E_MPa=210000.))
    different_G = floor.assess(26, material=dict(material(), G_MPa=60000.))
    different_nu = floor.assess(26, material=dict(material(), nu=.27))
    assert different_E['Fcrd_lower_bound_MPa'] != first['Fcrd_lower_bound_MPa']
    assert different_G['Fcrd_lower_bound_MPa'] != first['Fcrd_lower_bound_MPa']
    assert different_nu['Fcrd_lower_bound_MPa'] != first['Fcrd_lower_bound_MPa']


@pytest.mark.parametrize('lambda2', [Q('.673')**2-Q(1,10**30),Q('.673')**2,
    Q('.673')**2+Q(1,10**30),Q('.44')**2,Q(1),Q(100),Q(10)**100])
def test_nbr_resistance_monotone_capped_and_directed_near_transitions(lambda2):
    W, fy, gamma = Q(18900), Q(300), Q('1.1')
    md = W*fy/lambda2
    values = []
    for factor in (Q(999999,1000000),Q(1),Q(1000001,1000000),Q(2),Q(10)):
        value, proof = floor._resistance_floor(W,fy,gamma,md*factor)
        assert 0 < value <= W*fy/gamma
        assert proof['all_Mdist_at_or_above_floor']
        assert proof['gross_cap_used']
        values.append(value)
    assert values == sorted(values)


def test_sufficient_check_has_exact_boundary_and_never_failure():
    capacity = floor.assess(26)['MRd_lower_bound_Nmm']
    for demand in (0.,capacity,-capacity,math.nextafter(capacity,0.)):
        check = floor.assess(26,Msd_Nmm=demand)['sufficient_check']
        assert check['component_sufficient']
        assert check['utilization_upper_bound'] <= 1
        assert not check['failure_proven']
    for demand in (math.nextafter(capacity,math.inf),2*capacity,-2*capacity):
        check = floor.assess(26,Msd_Nmm=demand)['sufficient_check']
        assert not check['component_sufficient']
        assert check['utilization_upper_bound'] > 1
        assert check['status'] == 'inconclusive_floor_exceeded'
        assert not check['failure_proven']


@pytest.mark.parametrize('mutation', ['capacity','coefficient','source','nodes','flag','numeric_boolean','demand'])
def test_saved_replay_rejects_rehashed_edits(mutation):
    evidence = floor.assess(26,Msd_Nmm=1.)
    assert floor.validate_saved(json.loads(json.dumps(evidence)),index=26,Msd_Nmm=1.) == evidence
    bad = copy.deepcopy(evidence)
    if mutation == 'capacity': bad['MRd_lower_bound_Nmm'] *= 2
    elif mutation == 'coefficient': bad['proof']['coefficients_exact']['a'] = '1'
    elif mutation == 'source': bad['source_documents'][1]['sha256'] = 'edited'
    elif mutation == 'nodes': bad['source_binding']['nodes_sha256'] = 'edited'
    elif mutation == 'flag': bad['physical_resistance_bound'] = True
    elif mutation == 'numeric_boolean': bad['whole_member_approved'] = 0
    elif mutation == 'demand': bad['sufficient_check']['Msd_Nmm'] = 2.
    bad['snapshot_sha256'] = floor.digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError): floor.validate_saved(bad,index=26,Msd_Nmm=1.)


@pytest.mark.parametrize('value', [True,False,float('nan'),float('inf'),'1'])
def test_invalid_demand_rejected(value):
    with pytest.raises(ValueError): floor.assess(26,Msd_Nmm=value)


def test_invalid_material_geometry_and_documentary_rows_rejected():
    for key in material():
        for value in (True,float('nan'),float('inf')):
            with pytest.raises(ValueError): floor.assess(26,material=dict(material(),**{key:value}))
    for invalid in (True,-1,base.registry.inventory()['incomplete'][0]['catalog_index']):
        with pytest.raises(ValueError): floor.assess(invalid)
    with pytest.raises(ValueError): floor.assess(26,material={'fy_MPa':300.})
    for key,value in (('h',0),('t',100),('lip',0)):
        p = dict(h=125,bf=50,lip=17,t=2)
        p[key] = value
        with pytest.raises(ValueError): floor._coefficients(p,material())


@pytest.mark.parametrize('value', [Q(0),Q(1,3),Q(2),Q(10)**300,Q(10)**-300])
def test_exact_sqrt_and_output_directions(value):
    lo,hi = floor._sqrt_bounds(value)
    assert lo*lo <= value <= hi*hi
    assert Q(floor._directed(value)) <= value <= Q(floor._directed(value,True))


def test_api_does_not_mutate_material_and_evidence_is_json_safe():
    m = material()
    original = copy.deepcopy(m)
    result = floor.assess(26,material=m,Msd_Nmm=-1000.)
    assert m == original
    assert json.loads(json.dumps(result,allow_nan=False)) == result
    restored = floor.validate_saved(result,index=26,material=m,Msd_Nmm=-1000.)
    restored['proof']['all_positive_halfwaves'] = False
    assert result['proof']['all_positive_halfwaves']
