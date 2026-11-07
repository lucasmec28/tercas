"""Only fabricated fields/actions; no user projects or fixtures."""
import copy
import json
import math
import numpy as np
import pytest
from tercas import isolated_en_ue125_300 as en
from tercas.en_ue125_300_authority import read
from tercas.torsion_vlasov.vlasov import solve_member,evaluate
from tercas.torsion_vlasov.adapter import summarize_torsion_evidence


def make(scale=1.,length=4000.,pure=False):
    actions=[dict(name='q',kind='uniform',q_xy_N_mm=[scale*.025,scale*-.15],
        couple_N=scale*.7,application_xy_mm=[0.,124.],origin='synthetic'),
        dict(name='P',kind='point',force_xy_N=[scale*30.,scale*-60.],
        couple_Nmm=scale*400.,application_xy_mm=[24.,124.],s_mm=length*.425,origin='synthetic')]
    if pure:
        for a in actions:a['q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N']=[0.,0.]
    return solve_member(section=en.section_reference(),length_mm=length,E_MPa=200000.,G_MPa=77000.,
        actions=actions,supports={s:dict(twist='fixed',warping='free_assumed',origin='synthetic') for s in ('left','right')},
        combination_id='SYNTHETIC',limit_state='ELU',member_id='QA',action_accounting_origin='synthetic',elements_per_interval=8)


def calc(d):return en.calculate(d,normal_snapshot=read(),model_origin='Synthetic nominal intact')


def summary(d):return summarize_torsion_evidence(dict(schema='purlin_torsion_batch_evidence_v1',records=[dict(analysis=d)]))['records'][0]['analysis']


@pytest.fixture(scope='module')
def source():return make()


@pytest.fixture(scope='module')
def result(source):return calc(source)


def sample(d):
    c=read();s=d['section'];p=s['properties'];t=s['thickness_mm']
    xy=np.asarray(s['nodes_xy_mm'])-p['centroid_xy_mm'];delta=np.diff(xy,axis=0)
    n=np.column_stack([-delta[:,1],delta[:,0]])/np.linalg.norm(delta,axis=1)[:,None]
    om=np.asarray(s['omega_nodes_mm2']);stat=np.asarray(s['segment_static_coefficients'])
    maxima=dict(normal=0.,shear=0.,interaction=0.)
    for e in range(len(d['elements'])):
        for x in (0.,.137,.5,.883,1.):
            st=evaluate(d,e,x);mx=st['Mx_physical_Nmm'];my=st['My_physical_Nmm']
            cx=np.asarray(c['components']['Mx_positive' if mx>=0 else 'Mx_negative']['sigma_coefficients_c0_cx_cy'])
            cy=np.asarray(c['components']['My_positive' if my>=0 else 'My_negative']['sigma_coefficients_c0_cx_cy'])
            for u in (0.,.27,.5,.79,1.):
                pos=xy[:-1]+u*delta;omega=om[:-1]+u*np.diff(om)
                primitive=stat[:,:,0]+u*stat[:,:,1]+u*u*stat[:,:,2]
                flow=-(st['Vx_N']*primitive[:,0]/p['Iy_weak_mm4']+st['Vy_N']*primitive[:,1]/p['Ix_strong_mm4']+st['Tw_Nmm']*primitive[:,2]/p['Cw_mm6'])/t
                for face in (-1,1):
                    ext=pos+face*t/2*n
                    sigma=mx*(cx[0]+ext@cx[1:])+my*(cy[0]+ext@cy[1:])+st['B_Nmm2']*omega/p['Cw_mm6']
                    tau=flow-face*st['Tsv_Nmm']*t/p['J_mm4']
                    vals=dict(normal=np.max(abs(sigma))/300.,shear=np.max(abs(tau))/(300/math.sqrt(3)),interaction=np.max(np.sqrt(sigma*sigma+3*tau*tau))/330.)
                    for k,v in vals.items():maxima[k]=max(maxima[k],float(v))
    return maxima


def test_independent_concomitant_sampling_and_original_unchanged(source,result):
    before=copy.deepcopy(source);actual=sample(source)
    for k,v in actual.items():assert v<=result['stress']['criteria'][k]['index_upper_bound']
    assert source==before and result['applicability']['qualified']
    assert all(result[k] is False for k in en.FALSE_FLAGS)
    assert result['material']['fyb_MPa']==300 and result['source_analysis_material']=={'E_MPa':200000.,'G_MPa':77000.}
    assert result['mv']['component_sufficient'] and result['shear']['component_sufficient']


@pytest.mark.parametrize('scale',[-1.,2.,100.])
def test_signed_reversal_and_inconclusive(scale):
    d=make(scale);r=calc(d)
    for k,v in sample(d).items():assert v<=r['stress']['criteria'][k]['index_upper_bound']
    if scale==100:
        assert not r['stress']['section_stress_criteria_sufficiently_satisfied']
        assert all(r['stress']['criteria'][k]['observed_exceedance'] is False for k in ('shear','interaction'))
        n=r['stress']['criteria']['normal']
        if n['observed_exceedance']:assert n['physical_witness']['absolute_sigma_lower_MPa']>300


def test_zero_and_torsion_without_V():
    zero=calc(make(0.))
    assert all(c['index_upper_bound']==0 for c in zero['stress']['criteria'].values())
    assert zero['mv']['index_upper']==0
    d=make(pure=True);r=calc(d)
    assert r['shear']['index_upper']==0 and r['mv']['index_upper']==0
    assert r['stress']['criteria']['shear']['index_upper_bound']>0
    for k,v in sample(d).items():assert v<=r['stress']['criteria'][k]['index_upper_bound']


def test_real_zero_zones_and_curling(source):
    d=copy.deepcopy(source);d['length_mm']=3000.
    a=en.assess(d,read())
    assert a['axes']['Mx']['qualified'] and not a['axes']['My']['qualified']
    assert a['axes']['Mx']['zero_zones'][0]['threshold_upper_mm']==2450
    assert a['axes']['My']['zero_zones'][0]['threshold_upper_mm']==3075
    assert all(p['stress_upper_MPa']==300 for p in a['curling_panels'].values())
    d['loads']=[dict(kind='uniform',q_xy_N_mm=[1.,0.]),dict(kind='point',s_mm=1500.,force_xy_N=[-2000.,0.])]
    a=en.assess(d,read())
    assert len(a['axes']['My']['zero_zones'])==3
    assert not a['qualified']


@pytest.mark.parametrize('mutation',['E','G','N','contour','omega','primitive','material','ELS','gap'])
def test_domain_and_resealed_section_fail_closed(source,mutation):
    d=copy.deepcopy(source);normal=read()
    if mutation=='E':d['E_MPa']=210000.
    elif mutation=='G':d['G_MPa']=76923.
    elif mutation=='N':d['analysis_domain']['axial_force_in_this_model_N']=1
    elif mutation=='contour':d['section']['nodes_xy_mm'][0][0]+=.01
    elif mutation=='omega':d['section']['omega_nodes_mm2'][0]+=.01
    elif mutation=='primitive':d['section']['segment_static_coefficients'][0][0][0]+=.01
    elif mutation=='material':normal['material']['fyb_MPa']=250.
    elif mutation=='ELS':d['limit_state']='ELS'
    elif mutation=='gap':d['elements'][0]['a_mm']=1.
    if mutation in ('contour','omega','primitive'):
        d['section']['content_sha256']=en._sha({k:v for k,v in d['section'].items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.calculate(d,normal_snapshot=normal,model_origin='synthetic')


def test_saved_json_replay_no_solver_builder(source,result,monkeypatch):
    from tercas.torsion_vlasov import vlasov
    from tercas import catalog_torsion_section,en_ue125_300_builder,en_ue125_shear300
    def fail(*a,**kw):raise AssertionError('No rebuilding/solving on saved reads')
    monkeypatch.setattr(vlasov,'solve_member',fail);monkeypatch.setattr(catalog_torsion_section,'prepare',fail)
    monkeypatch.setattr(en_ue125_300_builder,'build',fail);monkeypatch.setattr(en_ue125_shear300,'_derive',fail)
    assert en.validate_saved(json.loads(json.dumps(result)),summary(source),normal_snapshot=read(),source_sha256=en._sha(source),model_origin='Synthetic nominal intact')


@pytest.mark.parametrize('mutation',['index','stress','source_torsion','source_load','source_material','normal','shear','flag'])
def test_rehashed_corruption_fails(source,result,mutation):
    r=copy.deepcopy(result);n=read()
    if mutation=='index':r['mv']['index_upper']=0
    elif mutation=='stress':r['stress']['criteria']['normal']['index_upper_bound']=0
    elif mutation=='source_torsion':r['source_demand']['elements'][0]['coefficients']['B_Nmm2'][0]+=1
    elif mutation=='source_load':r['source_demand']['loads'][0]['q_xy_N_mm'][0]+=.01
    elif mutation=='source_material':r['source_demand']['E_MPa']=210000
    elif mutation=='normal':n['components']['My_negative']['sigma_coefficients_c0_cx_cy'][0]=0;n['content_sha256']=en._sha({k:v for k,v in n.items() if k!='content_sha256'})
    elif mutation=='shear':r['shear_source_snapshot']['shear_capacity_lower_N']['strong']+=1
    elif mutation=='flag':r['whole_member_approved']=True
    r['content_sha256']=en._sha({k:v for k,v in r.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(r,summary(source),normal_snapshot=n,source_sha256=en._sha(source),model_origin='Synthetic nominal intact')


@pytest.mark.parametrize('mutation',['bool_node','bool_coefficient','torsion_rehash_all','nodal_rehash_all','control_bool'])
def test_canonical_types_and_rehashed_dense_field(source,result,mutation):
    r=copy.deepcopy(result);d=r['source_demand']
    if mutation=='bool_node':
        d['section']['nodes_xy_mm'][33][1]=False
        d['section']['content_sha256']=en._sha({k:v for k,v in d['section'].items() if k!='content_sha256'})
    elif mutation=='bool_coefficient':d['elements'][0]['coefficients']['B_Nmm2'][0]=False
    elif mutation=='torsion_rehash_all':d['elements'][0]['coefficients']['B_Nmm2'][0]+=1.
    elif mutation=='nodal_rehash_all':d['node_phi_rad'][1]+=.001
    else:r['stress']['criteria']['normal']['observed_exceedance']=0
    # Even a replaced outer source marker may not bless incoherent source math.
    r['source_analysis_sha256']=en._sha(d)
    r['content_sha256']=en._sha({k:v for k,v in r.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(r,summary(source),normal_snapshot=read(),source_sha256=en._sha(d),model_origin='Synthetic nominal intact')


def test_warm_cache_mutation_and_authority_fail_closed(source,result,monkeypatch):
    kw=dict(normal_snapshot=read(),source_sha256=en._sha(source),model_origin='Synthetic nominal intact')
    compact=summary(source)
    assert en.validate_saved(result,compact,**kw)
    forged=copy.deepcopy(result);forged['stress']['criteria']['normal']['observed_exceedance']=0
    forged['content_sha256']=en._sha({k:v for k,v in forged.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(forged,compact,**kw)
    forged=copy.deepcopy(result);forged['source_demand']['node_phi_rad']=tuple(forged['source_demand']['node_phi_rad'])
    with pytest.raises(ValueError,match='native JSON'):en.validate_saved(forged,compact,**kw)
    def fail(*a,**kw):raise ValueError('Authority no longer valid')
    with monkeypatch.context() as geometry_patch:
        geometry_patch.setattr(en,'section_reference',fail)
        with pytest.raises(ValueError,match='Authority'):en.validate_saved(result,compact,**kw)
    monkeypatch.setattr(en,'validate_normal',fail)
    with pytest.raises(ValueError,match='Authority'):en.validate_saved(result,compact,**kw)


def test_original_finite_point_numerical_domain(source):
    from tercas.en_ue125_300_source_replay import validate
    d=copy.deepcopy(source)
    point=next(x for x in d['loads'] if x['kind']=='point');point['s_mm']=1.
    with pytest.raises(ValueError,match='interval/resource'):validate(d)


@pytest.mark.parametrize('ra,b,tsv,tw',[
    ([0.,0.],1e7,0.,0.),([0.,0.],0.,1e4,0.),([0.,0.],0.,0.,1e4),
    ([100.,0.],0.,0.,0.),([0.,100.],0.,0.,0.),([-100.,-100.],-1e7,-1e4,1e4)])
def test_independent_operator_basis_and_both_faces(ra,b,tsv,tw):
    # Deliberately independent polynomial basis fields, not a claimed member
    # solution: exercise ONLY the algebraic stress operator and Bernstein bound.
    s=en.section_reference();p=s['properties'];normal=read()
    d=dict(section=s,loads=[],support_reactions={'left_force_xy_N':ra},elements=[
        dict(a_mm=10.,b_mm=20.,element_id='basis',coefficients={
            'B_Nmm2':[b],'Tsv_Nmm':[tsv],'Tw_Nmm':[tw]})])
    bounds=list(en._field_controls(d,normal))
    for selected,face,sigma_box,tau_box,_ in bounds:
        cx=normal['components'][selected['Mx']]['sigma_coefficients_c0_cx_cy']
        cy=normal['components'][selected['My']]['sigma_coefficients_c0_cx_cy']
        for j in (0,17,50,66,83,116,132):
            p0,p1=s['nodes_xy_mm'][j:j+2];dx=p1[0]-p0[0];dy=p1[1]-p0[1];ell=math.hypot(dx,dy)
            for u in (0.,.37,1.):
                x=p0[0]+u*dx-face*dy/ell-p['centroid_xy_mm'][0]
                y=p0[1]+u*dy+face*dx/ell-p['centroid_xy_mm'][1]
                omega=s['omega_nodes_mm2'][j]+u*(s['omega_nodes_mm2'][j+1]-s['omega_nodes_mm2'][j])
                st=s['segment_static_coefficients'][j]
                q=[v[0]+u*v[1]+u*u*v[2] for v in st]
                for z in (10.,13.7,20.):
                    sigma=(-ra[1]*z)*(cx[0]+cx[1]*x+cx[2]*y)+(ra[0]*z)*(cy[0]+cy[1]*x+cy[2]*y)+b*omega/p['Cw_mm6']
                    tau=-(-ra[0]*q[0]/p['Iy_weak_mm4']-ra[1]*q[1]/p['Ix_strong_mm4']+tw*q[2]/p['Cw_mm6'])/2-face*tsv*2/p['J_mm4']
                    assert float(np.min(sigma_box.lo[0,j]))<=sigma<=float(np.max(sigma_box.hi[0,j]))
                    assert float(np.min(tau_box.lo[0,j]))<=tau<=float(np.max(tau_box.hi[0,j]))
