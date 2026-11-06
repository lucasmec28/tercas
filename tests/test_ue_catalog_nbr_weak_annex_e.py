"""Synthetic whole-span reference: scalar integration/identities, no eigensolve."""
import copy
import json
import math
from decimal import Decimal, localcontext

import pytest

from test_ue_catalog_nbr_weak_mle import data
from tercas import ue_catalog_nbr_weak_annex_e as ae
from tercas import ue_catalog_nbr_bending as base
from tercas import ue_catalog_nbr_weak_mle as mle
from tercas import ue_catalog_reference as own
from tercas.roof_top_load import choice


@pytest.fixture
def reference_data(data):
    data['L_mm'] = 5000.
    data['roof_top_load'] = choice()
    return data


def test_own_cubic_integrals_independent_gauss_and_sectorial_SC(monkeypatch):
    from tercas import catalog_torsion_section as source
    def no_solver(*args, **kwargs):
        raise AssertionError('A section/member solver must not run')
    monkeypatch.setattr(source, 'from_polyline', no_solver)
    nodes = source.nominal_channel_nodes(h_mm=125, bf_mm=50, lip_mm=17,
                                         t_mm=2, ri_mm=2, arc_segments=32)
    assert len(nodes) == 134 and own.digest(nodes) == base.PIN['nodes_sha256']
    # Two-point Gaussian integration is exact for the cubic integrands.
    gauss_x3, gauss_xy2, raw_x, raw_y, raw_area, rows = [], [], [], [], [], []
    raw = 0.
    for a, b in zip(nodes[:-1], nodes[1:]):
        x,y = a[0]-mle.CG, a[1]-61.5
        X,Y = b[0]-mle.CG, b[1]-61.5
        da = 2*math.dist(a,b)
        nxt = raw+x*Y-y*X
        for u in (.5-.5/math.sqrt(3), .5+.5/math.sqrt(3)):
            xx, yy, rr = x+u*(X-x), y+u*(Y-y), raw+u*(nxt-raw)
            gauss_x3.append(da/2*xx**3)
            gauss_xy2.append(da/2*xx*yy*yy)
            raw_x.append(da/2*rr*xx)
            raw_y.append(da/2*rr*yy)
            raw_area.append(da/2*rr)
        rows.append((x,y,X,Y,da,raw,nxt));raw=nxt
    sec=ae.section_constants()
    assert math.fsum(gauss_x3) == pytest.approx(sec['integral_x3_mm5'],rel=2e-14)
    assert math.fsum(gauss_xy2) == pytest.approx(sec['integral_xy2_mm5'],rel=2e-14)
    c0=-math.fsum(raw_area)/sec['A_mm2']
    c1=-math.fsum(raw_x)/sec['Iy_mm4']
    c2=-math.fsum(raw_y)/sec['Ix_mm4']
    assert mle.CG-c2 == pytest.approx(sec['SC_x_mm'],abs=5e-12)
    assert c1 == pytest.approx(0.,abs=1e-12)
    cw=[]
    for x,y,X,Y,da,r,R in rows:
        w=r+c0+c1*x+c2*y;W=R+c0+c1*X+c2*Y
        cw.append(da*(w*w+w*W+W*W)/3)
    assert math.fsum(cw) == pytest.approx(sec['Cw_mm6'],rel=2e-14)
    j=(math.fsum(gauss_x3)+math.fsum(gauss_xy2))/(2*sec['Iy_mm4'])+c2
    assert j == pytest.approx(67.53119802572517,rel=2e-14)
    assert sec['r0_mm'] == pytest.approx(65.12809322745377,rel=2e-14)


@pytest.mark.parametrize('length',[1000.,3000.,5000.,10000.])
def test_Me_signed_decimal_and_product_difference(reference_data,length):
    reference_data['L_mm']=length
    c=ae.qualify_reference(reference_data)
    sec=c['section_constants']
    with localcontext() as ctx:
        ctx.prec=55;D=Decimal
        pi=D('3.1415926535897932384626433832795028841971693993751')
        n=D(200000)*D(str(sec['Ix_mm4']))*(pi/D(str(length)))**2
        z=(D(77000)*D(str(sec['J_mm4']))+D(200000)*D(str(sec['Cw_mm6']))*(pi/D(str(length)))**2)/D(str(sec['r0_squared_mm2']))
        j=D(str(sec['j_mm']));r2=D(str(sec['r0_squared_mm2']))
        root=(j*j+r2*z/n).sqrt()
        plus,minus=float(n*(root+j)),float(n*(root-j))
    p,m=[c['by_sign'][s] for s in mle.SIGNS]
    assert p['Me_reference_Nmm']==pytest.approx(plus,rel=3e-14)
    assert m['Me_reference_Nmm']==pytest.approx(minus,rel=3e-14)
    assert plus*minus==pytest.approx(c['Nex_N']*c['Nez_N']*sec['r0_squared_mm2'],rel=3e-14)
    assert plus-minus==pytest.approx(2*c['Nex_N']*sec['j_mm'],rel=3e-14)
    assert p['Cs']==1 and p['compression_side']=='web'
    assert m['Cs']==-1 and m['compression_side']=='lips'


def test_manual_lengths_never_become_restraints(reference_data):
    before=ae.qualify_reference(reference_data)
    reference_data['weak_catalog']={'Lx_mm':1.}
    reference_data['segments']=[dict(start_mm=0,end_mm=5000,Ly_effective_mm=1,Lz_effective_mm=1)]
    reference_data['weak_axis']={'positive':dict(Cm=.2,Nex_N=1e99,Nez_N=1e99,j_mm=1.)}
    assert ae.qualify_reference(reference_data)==before
    assert before['domain']['Lx_used_mm']==before['domain']['Lz_used_mm']==5000
    assert before['domain']['Cm']==1 and before['domain']['manual_effective_lengths_used'] is False


def test_first_tension_yield_local_cap_is_mandatory(reference_data):
    c=ae.qualify_reference(reference_data)
    for sign,s in c['by_sign'].items():
        trial=mle.flt_effective_section(reference_data,sign,s['chi_FLT'])
        assert s['Wcef_at_chi_fy_mm3']==trial['Wcef_mm3']
        assert s['MRd_FLT_reference_component_Nmm']==pytest.approx(s['chi_FLT']*300*trial['Wcef_mm3']/1.1)
        assert s['local_FLT_reference_min_Nmm']==min(s['MRd_local_Nmm'],s['MRd_FLT_reference_component_Nmm'])
        assert s['D_pending'] and s['local_first_yield_cap_applied']
        assert 'MRd_Nmm' not in s
    web=c['by_sign']['positive']
    assert web['MRd_FLT_reference_component_Nmm']>web['MRd_local_Nmm']
    assert web['local_FLT_reference_min_Nmm']==web['MRd_local_Nmm']


def test_actual_parallel_position_classification_stays_separate(reference_data):
    from tercas.roof_biaxial import classify
    geom={'coherent_torsion_section':True}
    def act(name,q,x):return dict(name=name,kind='uniform',q_parallel_N_mm=q,x_from_SC_mm=x)
    assert classify([act('synthetic',1.,23.51698)],geom)['applicable']
    assert classify([act('synthetic',1.,0.)],geom)['applicable']
    assert not classify([act('synthetic',-1.,23.51698)],geom)['applicable']
    assert not classify([act('synthetic',1.,None)],geom)['applicable']
    assert not classify([act('favourable',2.,23.51698),act('adverse',-1.,23.51698)],geom)['applicable']
    c=ae.qualify_reference(reference_data)
    assert c['real_action_applicability']=='not_assessed'
    assert c['actual_load_Me_qualified'] is False and c['primary_torsion_assessed'] is False


def test_saved_reader_scalar_only_preserves_inputs(reference_data,monkeypatch):
    before=copy.deepcopy(reference_data)
    def fail(*a,**k):raise AssertionError('source/member solve forbidden')
    monkeypatch.setattr(own,'_source',fail)
    monkeypatch.setattr(own,'source_binding',fail)
    c=ae.qualify_reference(reference_data)
    assert ae.validate_saved(json.loads(json.dumps(c)),reference_data)==c
    assert reference_data==before
    for k in ('actual_load_Me_qualified','distortional_qualified','complete_bending_capacity_qualified',
              'interaction_9_9_qualified','primary_torsion_assessed','ELS_qualified',
              'global_properties_modified','whole_member_approved'):
        assert c[k] is False


@pytest.mark.parametrize('attack',['j','length','Cs','Me','minimum','scope','bool'])
def test_saved_rehashed_attacks_rejected(reference_data,attack):
    c=ae.qualify_reference(reference_data)
    if attack=='j':c['section_constants']['j_mm']+=1
    elif attack=='length':c['domain']['Lz_used_mm']=1
    elif attack=='Cs':c['by_sign']['positive']['Cs']=-1
    elif attack=='Me':c['by_sign']['negative']['Me_reference_Nmm']*=2
    elif attack=='minimum':c['by_sign']['positive']['local_FLT_reference_min_Nmm']*=2
    elif attack=='scope':c['actual_load_Me_qualified']=True
    else:c['whole_member_approved']=0
    c.pop('snapshot_sha256');c['snapshot_sha256']=own.digest(c)
    with pytest.raises(ValueError):ae.validate_saved(c,reference_data)


@pytest.mark.parametrize('length',[0.,-1.,True,'5000',float('inf'),float('nan'),1e-300,1e300])
def test_invalid_or_unrepresentable_physical_span(reference_data,length):
    reference_data['L_mm']=length
    with pytest.raises(ValueError):ae.qualify_reference(reference_data)


@pytest.mark.parametrize('change',['none','disabled','restrained_warping','intermediate'])
def test_explicit_physical_reference_domain_required(reference_data,change):
    if change=='none':reference_data.pop('roof_top_load')
    elif change=='disabled':reference_data['roof_top_load']['enabled']=False
    elif change=='restrained_warping':reference_data['roof_top_load']['end_restraint']='fixed_warping'
    else:reference_data['roof_top_load']['intermediate_restraints']='manual_Lz'
    with pytest.raises(ValueError):ae.qualify_reference(reference_data)


def test_saved_span_is_current_and_unmarked_is_not_adopted(reference_data):
    c=ae.qualify_reference(reference_data)
    reference_data['L_mm']=6000.
    with pytest.raises(ValueError):ae.validate_saved(c,reference_data)
    reference_data.pop(own.FIELD)
    assert ae.qualify_reference(reference_data) is None
