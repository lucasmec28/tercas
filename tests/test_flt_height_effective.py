"""Synthetic analytical checks, no eigen solver or private project inputs."""
import copy
import json
import math
from decimal import Decimal, localcontext
import pytest
from tercas import flt_height_effective as flt
from tercas import pierin_ue_registry as registry
from tercas import resistance_effective_lengths as lengths
from tercas import ue_catalog_reference as own
from en_ue_test_helpers import inputs


def data(index=26, ly=2050., lz=2050., fy=300.):
    d = inputs(index, L=4100., angle=5.71)
    d['properties']['fy_MPa'] = fy
    d = own.activate(d)
    return lengths.declare(d, Lx_mm=2050., Ly_mm=ly, Lz_mm=lz,
                           origin='Synthetic independent resistance lengths; no physical supports')


def uniform(q, h, name='roof', ex=25.):
    return dict(name=name, kind='uniform', q_down_N_mm=q,
                height_above_SC_mm=h, x_from_SC_mm=ex)


def point(P=100., h=62.5, x=2050., name='P'):
    return dict(name=name, kind='point', P_down_N=P, s_mm=x,
                height_above_SC_mm=h, x_from_SC_mm=25.)


def actions(d):
    # Same physical projected loads for every member: not a project fixture.
    a = math.radians(5.71)
    return [dict(uniform(.15*math.cos(a), 0., 'PP', 30.), q_parallel_N_mm=.15*math.sin(a)),
            dict(uniform(.9*math.cos(a), d['properties']['h']/2), q_parallel_N_mm=.9*math.sin(a))]


@pytest.mark.parametrize('index', registry.new_study_indices())
def test_all_66_contours_uniform_height_and_half_lengths(index):
    d = data(index); a = actions(d)
    before = copy.deepcopy((d,a))
    out = flt.qualify_family(d,a)
    assert out['elastic_reference_eligible'] and out['Me_Nmm']>0
    assert out['strong_symmetry']['qualified']
    assert out['C1']==.972 and out['C2']==.304
    assert out['kz']==out['kw']==.5
    assert out['physical_span_mm']==4100.
    assert out['maximum_reference_moment_Nmm']==pytest.approx(1.05*math.cos(math.radians(5.71))*4100.**2/8)
    assert out['distribution']['zg_mm']==pytest.approx(.9*d['properties']['h']/2/1.05)
    assert out['height_tangent_by_action'][0]['value']==0.
    assert out['primary_torque_by_action'][0]['value']!=0.
    assert out['individual_parallel_actions_present']
    assert not out['biaxial_stability_assessed']
    assert not out['whole_member_approved'] and not out['actual_load_capacity_qualified']
    assert not out['physical_supports_created'] and not out['demand_span_changed']
    assert not out['guaranteed_elastic_lower_bound']
    assert (d,a)==before
    assert flt.validate_saved(json.loads(json.dumps(out)),d,a)==out


def test_decimal_reference_independent_of_implementation():
    d=data(); out=flt.qualify_family(d,actions(d)); p=out['section_properties']
    with localcontext() as ctx:
        ctx.prec=65
        D=lambda v:Decimal(str(v))
        pi=Decimal('3.141592653589793238462643383279502884197169399375105820974944592')
        E=D(200000); G=D(77000); I=D(p['Iy_weak_mm4']); J=D(p['J_mm4']); Cw=D(p['Cw_mm6'])
        ly=D(2050); lz=D(2050); z=D(.304)*D(62.5)*D(.9)/D(1.05)
        base=(ly/lz)**2*Cw/I+ly**2*G*J/(pi**2*E*I)
        expected=D(.972)*pi**2*E*I/ly**2*((base+z*z).sqrt()-z)
    assert out['Me_Nmm']==pytest.approx(float(expected),rel=8e-15)


def test_independent_lengths_change_resistance_not_demand():
    a=data(ly=2050.,lz=4100.); b=data(ly=4100.,lz=2050.); c=data(ly=4100.,lz=4100.)
    ra,rb,rc=[flt.qualify_family(d,actions(d)) for d in (a,b,c)]
    assert ra['maximum_reference_moment_Nmm']==rb['maximum_reference_moment_Nmm']==rc['maximum_reference_moment_Nmm']
    assert ra['Me_Nmm']>rc['Me_Nmm'] and rb['Me_Nmm']>rc['Me_Nmm']
    assert ra['Me_Nmm']!=rb['Me_Nmm']
    # Ly does not substitute for Lz in the warping term.
    rz=flt.qualify_family(data(ly=2050.,lz=3000.),actions(a))
    assert ra['Me_Nmm']<rz['Me_Nmm']<flt.qualify_family(data(),actions(a))['Me_Nmm']


def test_closed_form_recovers_classical_independent_lengths_at_zero_height():
    p=dict(E_MPa=200000.,G_MPa=77000.,Iweak_mm4=170444.,J_mm4=655.,Cw_mm6=5.69e8,
           Ly_mm=3000.,Lz_mm=4200.)
    me=flt.closed_form(**p,C1=1.,C2=0.,zg_mm=0.)
    expected=math.pi/3000.*math.sqrt(200000.*170444.*(77000.*655.+math.pi**2*200000.*5.69e8/4200.**2))
    assert me==pytest.approx(expected,rel=2e-15)


@pytest.mark.parametrize('factor',[.1,10.,1e4])
def test_load_scaling(factor):
    d=data(); a=actions(d); r=flt.qualify_family(d,a)
    b=copy.deepcopy(a)
    for x in b:x['q_down_N_mm']*=factor
    s=flt.qualify_family(d,b)
    assert s['Me_Nmm']==pytest.approx(r['Me_Nmm'],rel=3e-15)
    assert s['lambda_reference']*factor==pytest.approx(r['lambda_reference'],rel=3e-15)


def test_uplift_sign_and_different_height_cancellation():
    d=data(); down=flt.qualify_family(d,[uniform(1.,62.5)])
    up=flt.qualify_family(d,[uniform(-1.,62.5)])
    at_sc=flt.qualify_family(d,[uniform(1.,0.)])
    assert down['Me_Nmm']<at_sc['Me_Nmm']<up['Me_Nmm']
    opposite=flt.qualify_family(d,[uniform(1.,62.5),uniform(-2.,0.,'opposite')])
    assert opposite['Me_Nmm']==pytest.approx(down['Me_Nmm'])
    assert opposite['distribution']['zg_mm']==62.5
    zero=flt.qualify_family(d,[uniform(1.,62.5),uniform(-1.,0.,'opposite')])
    assert zero['Me_Nmm'] is None and not zero['elastic_reference_eligible']
    assert zero['load_reduction']['q_height_sum_N']==62.5
    assert 'giro' in zero['reason']


def test_pp_not_collapsed_to_top_or_torque_erased():
    d=data(); a=actions(d); separate=flt.qualify_family(d,a)
    incorrect=flt.qualify_family(d,[uniform(sum(x['q_down_N_mm'] for x in a),62.5)])
    assert separate['Me_Nmm']>incorrect['Me_Nmm']
    assert separate['actions']==a
    assert separate['height_tangent_by_action'][0]['value']==0.
    assert separate['primary_torque_by_action'][0]['value']==pytest.approx(-30*.15*math.cos(math.radians(5.71)))


@pytest.mark.parametrize('kz,c1,c2',[(.5,1.070,.432),(1.,1.365,.553)])
def test_central_point_uses_its_own_coefficients(kz,c1,c2):
    d=data(ly=kz*4100)
    r=flt.qualify_family(d,[point()])
    assert r['elastic_reference_eligible'] and r['C1']==c1 and r['C2']==c2
    assert r['maximum_reference_moment_Nmm']==100.*4100/4
    assert r['distribution']['kind']=='midspan_point'


def test_collocated_points_weight_height_but_never_q_plus_p():
    d=data(); r=flt.qualify_family(d,[point(P=100.,h=60.),point(P=50.,h=0.,name='P2')])
    assert r['elastic_reference_eligible'] and r['distribution']['zg_mm']==40.
    mixture=flt.qualify_family(d,actions(d)+[point()])
    assert mixture['Me_Nmm'] is None and 'q+P' in mixture['reason']


def test_point_at_end_has_no_bending_or_height_effect_and_offcenter_not_admitted():
    d=data(); baseline=flt.qualify_family(d,actions(d))
    end=flt.qualify_family(d,actions(d)+[point(P=1e10,h=1e10,x=0.)])
    assert end['Me_Nmm']==baseline['Me_Nmm']
    for x in (1.,2000.,4099.):
        r=flt.qualify_family(d,[point(x=x)])
        assert r['Me_Nmm'] is None and 'meio' in r['reason']


@pytest.mark.parametrize('ly,lz',[(2049.,2050.),(2051.,2050.),(3000.,2050.),(4101.,4100.),(2050.,2049.),(2050.,4101.)])
def test_non_tabulated_kz_and_outside_kw_are_explicit(ly,lz):
    d=data(ly=ly,lz=lz); r=flt.qualify_family(d,actions(d))
    assert not r['elastic_reference_eligible'] and r['Me_Nmm'] is None
    assert 'Fatores' in r['reason']


def test_own_geometry_symmetry_is_proved_not_assumed_by_name():
    s=own.section_for(data())
    assert flt.symmetry_proof(s)['qualified']
    s['nodes_xy_mm'][0][1]+=1
    assert not flt.symmetry_proof(s)['qualified']
    s=own.section_for(data());s['properties']['shear_center_xy_mm'][1]+=.1
    assert not flt.symmetry_proof(s)['qualified']


@pytest.mark.parametrize('mutate',[
    lambda r:r.update(Me_Nmm=1e20),
    lambda r:r.update(C1=100.),
    lambda r:r.update(Ly_used_mm=4100.),
    lambda r:r['distribution'].update(zg_mm=0.),
    lambda r:r['actions'][0].update(height_above_SC_mm=62.5),
    lambda r:r['primary_torque_by_action'][0].update(value=0.),
    lambda r:r.update(whole_member_approved=True),
    lambda r:r['strong_symmetry'].update(strong_zj_residual_mm=1.),
])
def test_rehashed_edits_rejected_by_full_replay(mutate):
    d=data(); a=actions(d); r=flt.qualify_family(d,a);mutate(r)
    r['snapshot_sha256']=own.digest({k:v for k,v in r.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):flt.validate_saved(r,d,a)


def test_reader_never_calls_old_solver_or_changes_legacy_snapshot(monkeypatch):
    from tercas import ltb_load_height
    monkeypatch.setattr(ltb_load_height,'solve',lambda **kw:pytest.fail('eigen solve'))
    d=data();a=actions(d);old={'method':'historical_full_span','Me_Nmm':123.}
    before=copy.deepcopy(old)
    r=flt.qualify_family(d,a)
    assert flt.validate_saved(r,d,a)==r and old==before


def test_no_source_adoption_no_implicit_new_study():
    d=data();d.pop('ue_catalog_reference')
    with pytest.raises(ValueError):flt.qualify_family(d,actions(d))


def test_disabled_roof_load_cannot_invent_height():
    d=data();d['roof_top_load']['enabled']=False
    r=flt.qualify_family(d,actions(d))
    assert r['Me_Nmm'] is None and 'desabilitado' in r['reason']


def test_large_height_rationalization_remains_positive():
    p=dict(E_MPa=200000.,G_MPa=77000.,Iweak_mm4=170444.,J_mm4=655.,Cw_mm6=5.69e8,Ly_mm=2050.,Lz_mm=2050.)
    assert flt.closed_form(**p,C1=.972,C2=.304,zg_mm=1e12)>0.
    for key,value in [('Ly_mm',0.),('Lz_mm',float('inf')),('Iweak_mm4',True)]:
        with pytest.raises(ValueError):flt.closed_form(**dict(p,**{key:value}),C1=1.,C2=.4,zg_mm=60.)


def test_actual_torque_retains_parallel_and_normal_projection_separately():
    d=data();a=[dict(uniform(1.,60.,ex=25.),q_parallel_N_mm=-.25)]
    r=flt.qualify_family(d,a)
    assert r['normal_projection_primary_torque_by_action'][0]['value']==-25.
    assert r['primary_torque_by_action'][0]['value']==-10.
    assert r['primary_torque_report_includes_parallel_actions']
    a[0]['x_from_SC_mm']=None
    assert flt.qualify_family(d,a)['primary_torque_by_action'][0]['value'] is None
