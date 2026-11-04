"""Certified bounds of the recovered Vlasov thin-wall stress field, not design.

Certification is only of the continuous polynomial field represented here:
normal stress on the midsurface plus Saint-Venant face shear. It does not bound
FE discretization error, true exterior normal stress, local effects or strength.
"""
import hashlib
import heapq
import json
import math
from dataclasses import dataclass

import numpy as np

from .intervals import Interval as I,stack,power_to_bernstein,split_bernstein,evaluate_bernstein,multiply_bernstein,elevate_bernstein
from .section import finite,verify_section
from .vlasov import evaluate

FIELDS=('von_mises','normal_tension','normal_compression','shear_absolute')


def _polynomial_1d(values,degree):
    values=list(values)+[I(0.)]*(degree+1-len(values))
    return stack(values)


def _member_polynomials(result):
    """Enclose physical flexure reconstruction from the exact stored numbers.

The recovered torsion coefficient arrays are themselves the source field.
The subtraction/multiplication used for the flexural fields is also enclosed.
"""
    q=[I(0.),I(0.)]
    for action in result['loads']:
        if action['kind']=='uniform':q=[q[j]+action['q_xy_N_mm'][j] for j in (0,1)]
    RA=[I(x) for x in result['support_reactions']['left_force_xy_N']]
    pts=[a for a in result['loads'] if a['kind']=='point'];rows=[];identities=[]
    for index,e in enumerate(result['elements']):
        a=I(e['a_mm']);ell=I(e['b_mm'])-I(e['a_mm'])
        v=[-RA[j]-q[j]*a for j in (0,1)]
        mx=-RA[1]*a-q[1]*a*a/2.;my=RA[0]*a+q[0]*a*a/2.
        for point in pts:
            if point['s_mm']<=e['a_mm']:
                v=[v[j]-point['force_xy_N'][j] for j in (0,1)]
                distance=a-point['s_mm']
                mx=mx-point['force_xy_N'][1]*distance;my=my+point['force_xy_N'][0]*distance
        c=e['coefficients']
        rows.append(dict(N=_polynomial_1d([I(0.)],3),
            Mx=_polynomial_1d([mx,v[1]*ell,-q[1]*ell*ell/2.],3),
            My=_polynomial_1d([my,-v[0]*ell,q[0]*ell*ell/2.],3),
            Vx=_polynomial_1d([v[0],-q[0]*ell],2),Vy=_polynomial_1d([v[1],-q[1]*ell],2),
            B=_polynomial_1d([I(x) for x in c['B_Nmm2']],3),
            Tsv=_polynomial_1d([I(x) for x in c['Tsv_Nmm']],2),
            Tw=_polynomial_1d([I(x) for x in c['Tw_Nmm']],2)))
        identities.append(dict(kind='element',element_index=index,element_id=e['element_id'],a_mm=e['a_mm'],b_mm=e['b_mm']))
    for state in result.get('support_limit_states',[]):
        if state.get('element_index') is not None or 'before P' not in state.get('position_limit',''):
            raise ValueError('Unrecognized concentrated support-limit state')
        row={key:_polynomial_1d([I(state[name])],degree) for key,name,degree in
             [('N','N_N',3),('Mx','Mx_physical_Nmm',3),('My','My_physical_Nmm',3),('B','B_Nmm2',3),
              ('Vx','Vx_N',2),('Vy','Vy_N',2),('Tsv','Tsv_Nmm',2),('Tw','Tw_Nmm',2)]}
        rows.append(row);identities.append(dict(kind='support_limit',state=state,element_id=state['element_id']))
    return {k:stack([r[k] for r in rows]) for k in rows[0]},identities


def build_stress_patches(result):
    """Vectorized outward intervals, from input arithmetic through Bernstein.

Return flattened rectangles with two face signs per (member piece, segment).
No section/station/fibre extrema are combined as if they were concomitant.
"""
    if result.get('schema')!='single_vlasov_member_demand_v1':raise ValueError('Complete Vlasov member field required')
    verify_section(result['section'])
    if not result.get('numerics',{}).get('qualification_passed'):
        raise ValueError('Numerically qualified source solution required')
    if result.get('analysis_domain',{}).get('axial_force_in_this_model_N')!=0:
        raise ValueError('Current member source contract is N=0')
    pol,identities=_member_polynomials(result);section=result['section'];p=section['properties'];t=section['thickness_mm']
    if len(identities)*(len(section['nodes_xy_mm'])-1)*2>100000:
        raise ValueError('Stress-envelope research resource limit: at most 100000 initial rectangles')
    nodes=I(section['nodes_xy_mm']);cg=I(p['centroid_xy_mm']);xy=nodes-cg
    coords=stack([xy[:-1],xy[1:]-xy[:-1]],axis=-1)
    omega=I(section['omega_nodes_mm2']);om=stack([omega[:-1],omega[1:]-omega[:-1]],axis=-1)
    # (piece, segment, longitudinal coefficient, contour coefficient)
    def outer(a,b):return a[:,None,:,None]*b[None,:,None,:]
    sigma=outer(pol['N']/p['A_mm2'],I(np.column_stack([np.ones(len(om.lo)),np.zeros(len(om.lo))])))
    sigma=sigma+outer(pol['Mx']/p['Ix_strong_mm4'],coords[:,1,:])-outer(pol['My']/p['Iy_weak_mm4'],coords[:,0,:])+outer(pol['B']/p['Cw_mm6'],om)
    stat=I(section['segment_static_coefficients'])
    flow=-(outer(pol['Vx']/p['Iy_weak_mm4'],stat[:,0,:])+outer(pol['Vy']/p['Ix_strong_mm4'],stat[:,1,:])+outer(pol['Tw']/p['Cw_mm6'],stat[:,2,:]))/t
    sv=pol['Tsv']*t/p['J_mm4']
    sv=outer(sv,I(np.column_stack([np.ones(len(om.lo)),np.zeros((len(om.lo),2))])))
    tau=stack([flow-sv,flow+sv],axis=2)
    sigma=stack([sigma,sigma],axis=2)
    sigma=power_to_bernstein(sigma);tau=power_to_bernstein(tau)
    shape=sigma.lo.shape[:3]
    sigma=I(sigma.lo.reshape((-1,4,2)),sigma.hi.reshape((-1,4,2)))
    tau=I(tau.lo.reshape((-1,3,3)),tau.hi.reshape((-1,3,3)))
    squared_sigma=elevate_bernstein(multiply_bernstein(sigma,sigma),-1,4)
    squared_tau=elevate_bernstein(multiply_bernstein(tau,tau),-2,6)
    vm_squared=squared_sigma+squared_tau*3.
    return dict(sigma=sigma,tau=tau,vm_squared=vm_squared,shape=shape,identities=identities,
                patch_count=math.prod(shape),source_field='equilibrium-recovered B/T and exact statically determinate concomitant flexure')


def _objective_interval(mode,sigma,tau):
    if mode=='von_mises':
        squared=sigma.square()+tau.square()*3.
        # Intersect with the known nonnegative range of this sum of squares.
        return I(np.maximum(0.,squared.lo),np.maximum(0.,squared.hi)).sqrt()
    if mode=='normal_tension':return sigma
    if mode=='normal_compression':return -sigma
    if mode=='shear_absolute':return tau.abs()
    raise ValueError('Unknown objective')


def _upper(mode,sigma,tau,vm_squared=None):
    if mode=='von_mises' and vm_squared is not None:
        return np.nextafter(np.sqrt(np.maximum(0.,np.max(vm_squared.hi,axis=(-2,-1)))),np.inf)
    s=I(np.min(sigma.lo,axis=(-2,-1)),np.max(sigma.hi,axis=(-2,-1)))
    t=I(np.min(tau.lo,axis=(-2,-1)),np.max(tau.hi,axis=(-2,-1)))
    return _objective_interval(mode,s,t).hi


@dataclass
class Patch:
    root:int
    sigma:I
    tau:I
    u0:float=0.
    u1:float=1.
    v0:float=0.
    v1:float=1.
    depth:int=0
    vm_squared:object=None


def _point(patch,u,v):
    return evaluate_bernstein(patch.sigma,u,v),evaluate_bernstein(patch.tau,u,v)


def _refine_axis(patch,mode):
    # Variation of Bernstein coefficients already reflects the restricted domain.
    def variation(a,axis):
        difference=np.diff(a.lo,axis=axis)
        return (float(np.max(np.abs(difference))) if difference.size else 0.)+float(np.max(a.hi-a.lo))
    if mode in ('normal_tension','normal_compression'):field=patch.sigma
    elif mode=='shear_absolute':field=patch.tau
    else:field=patch.vm_squared
    if field is not None:s=variation(field,-2);r=variation(field,-1)
    else:
        s=max(variation(patch.sigma,-2),math.sqrt(3)*variation(patch.tau,-2))
        r=max(variation(patch.sigma,-1),math.sqrt(3)*variation(patch.tau,-1))
    return -2 if s>=r else -1


def _split(patch,mode):
    axis=_refine_axis(patch,mode);s=split_bernstein(patch.sigma,axis);t=split_bernstein(patch.tau,axis)
    if axis==-2:
        middle=(patch.u0+patch.u1)/2
        bounds=[(patch.u0,middle,patch.v0,patch.v1),(middle,patch.u1,patch.v0,patch.v1)]
    else:
        middle=(patch.v0+patch.v1)/2
        bounds=[(patch.u0,patch.u1,patch.v0,middle),(patch.u0,patch.u1,middle,patch.v1)]
    vm=[None,None] if patch.vm_squared is None else split_bernstein(patch.vm_squared,axis)
    return [Patch(patch.root,s[i],t[i],*bounds[i],patch.depth+1,vm[i]) for i in (0,1)]


def maximize_field(patches,mode,*,relative_tolerance=1e-6,absolute_tolerance_MPa=1e-6,max_subdivisions=20000,max_depth=50):
    """Bounds remain valid on resource exhaustion; convergence is never implied."""
    if mode not in FIELDS:raise ValueError('Unknown stress objective')
    relative_tolerance=finite(relative_tolerance,'relative numerical tolerance',True)
    absolute_tolerance_MPa=finite(absolute_tolerance_MPa,'absolute numerical tolerance',True)
    if not 1e-12<=relative_tolerance<=1e-2:raise ValueError('Relative numerical tolerance outside supported range')
    if type(max_subdivisions) is not int or not 0<=max_subdivisions<=100000:raise ValueError('Invalid refinement budget')
    if type(max_depth) is not int or not 1<=max_depth<=50:raise ValueError('Invalid subdivision depth')
    tolerance=lambda lower,upper:max(absolute_tolerance_MPa,relative_tolerance*max(abs(lower),abs(upper)))
    s=patches['sigma'];t=patches['tau'];vm=patches.get('vm_squared') if mode=='von_mises' else None
    upper=_upper(mode,s,t,vm)
    best=-math.inf;witness=None
    samples=patches.get('initial_samples')
    if samples is None:samples=[(u,v,evaluate_bernstein(s,u,v),evaluate_bernstein(t,u,v)) for u in (0.,.5,1.) for v in (0.,.5,1.)]
    for u,v,si,ti in samples:
        lower=_objective_interval(mode,si,ti).lo;root=int(np.argmax(lower));value=float(lower[root])
        if value>best:best=value;witness=dict(root=root,u=u,v=v,sigma_interval=[float(si.lo[root]),float(si.hi[root])],tau_interval=[float(ti.lo[root]),float(ti.hi[root])])
    heap=[];serial=0;discarded=-math.inf
    for root,bound in enumerate(upper.tolist()):
        if bound-best<=tolerance(best,bound):discarded=max(discarded,bound)
        else:heapq.heappush(heap,(-bound,serial,Patch(root,s[root],t[root],vm_squared=None if vm is None else vm[root])));serial+=1
    subdivisions=0;reason='tolerance';blocked=-math.inf;max_seen_depth=0
    while heap:
        bound=-heap[0][0]
        if max(bound,discarded,blocked)-best<=tolerance(best,max(bound,discarded,blocked)):break
        if subdivisions>=max_subdivisions:reason='subdivision_budget';break
        _,_,patch=heapq.heappop(heap)
        if patch.depth>=max_depth:
            blocked=max(blocked,bound);reason='depth_budget';continue
        for child in _split(patch,mode):
            max_seen_depth=max(max_seen_depth,child.depth)
            for u in (0.,.5,1.):
                for v in (0.,.5,1.):
                    si,ti=_point(child,u,v);value=float(_objective_interval(mode,si,ti).lo)
                    if value>best:
                        best=value;witness=dict(root=child.root,u=child.u0+(child.u1-child.u0)*u,
                            v=child.v0+(child.v1-child.v0)*v,
                            sigma_interval=[float(si.lo),float(si.hi)],tau_interval=[float(ti.lo),float(ti.hi)])
            ub=float(_upper(mode,child.sigma,child.tau,child.vm_squared))
            if ub-best<=tolerance(best,ub):discarded=max(discarded,ub)
            else:heapq.heappush(heap,(-ub,serial,child));serial+=1
        subdivisions+=1
    final_upper=max(best,discarded,blocked,-heap[0][0] if heap else -math.inf)
    gap=final_upper-best;converged=gap<=tolerance(best,final_upper)
    return dict(objective=mode,lower_MPa=best,upper_MPa=final_upper,absolute_gap_MPa=gap,
        converged=converged,termination='tolerance' if converged else reason,
        requested_relative_tolerance=relative_tolerance,requested_absolute_tolerance_MPa=absolute_tolerance_MPa,
        subdivisions=subdivisions,maximum_subdivision_depth=max_seen_depth,initial_rectangles=patches['patch_count'],
        witness=witness,certificate_scope='Continuous recovered polynomial thin-wall stress field only; not exact continuum or FE discretization error')


def _witness_state(result,patches,record):
    w=record['witness'];piece,segment,face=np.unravel_index(w['root'],patches['shape']);identity=patches['identities'][piece]
    if identity['kind']=='element':state=evaluate(result,identity['element_index'],w['u'])
    else:state=identity['state']
    keys=('combination_id','limit_state','member_id','element_id','element_index','x_mm','s_mm','u','side','position_limit',
          'N_N','Mx_physical_Nmm','My_physical_Nmm','Mforte_R01_Nmm','Mfraco_R01_Nmm','Vx_N','Vy_N',
          'T_Nmm','T_CG_Nmm','Tsv_Nmm','Tw_Nmm','B_Nmm2','phi_rad','psi_per_mm')
    state={k:state[k] for k in keys if k in state}
    sec=result['section'];a=np.asarray(sec['nodes_xy_mm'][segment]);b=np.asarray(sec['nodes_xy_mm'][segment+1]);r=w['v']
    vm=_objective_interval('von_mises',I(*w['sigma_interval']),I(*w['tau_interval']))
    return dict(longitudinal_state=state,source_piece=int(piece),polynomial_u=w['u'],
        section_segment_index=int(segment),section_u=r,section_xy_mm=(a+r*(b-a)).tolist(),
        omega_mm2=sec['omega_nodes_mm2'][segment]+r*(sec['omega_nodes_mm2'][segment+1]-sec['omega_nodes_mm2'][segment]),
        saint_venant_face_sign=(-1 if face==0 else 1),sigma_midline_MPa_interval=w['sigma_interval'],
        tau_face_MPa_interval=w['tau_interval'],von_mises_MPa_interval=[float(vm.lo),float(vm.hi)],
        coordinate_note='Parameters identify the mathematical point; exported physical coordinates are binary64 rounded',
        concomitant=True)


def member_yield_envelope(result,*,fy_MPa,material_origin,relative_tolerance=1e-6,absolute_tolerance_MPa=1e-6,
                          max_subdivisions=20000,max_depth=50,objectives=FIELDS):
    """Nominal material first-yield only, without a resistance factor or verdict.

Lambda scales ALL actions proportionally with the same lines/supports. The
field remains first-order; a lambda is not a validated nonlinear load factor.
"""
    fy=finite(fy_MPa,'nominal yield stress',True)
    if not isinstance(material_origin,str) or not material_origin.strip():raise ValueError('Explicit material origin required')
    relative_tolerance=finite(relative_tolerance,'relative tolerance',True)
    absolute_tolerance_MPa=finite(absolute_tolerance_MPa,'absolute tolerance',True)
    if relative_tolerance>1e-2 or relative_tolerance<1e-12:raise ValueError('Relative numerical tolerance outside supported range')
    if type(max_subdivisions) is not int or max_subdivisions<0 or max_subdivisions>100000:raise ValueError('Invalid refinement budget')
    if type(max_depth) is not int or not 1<=max_depth<=50:raise ValueError('Invalid subdivision depth')
    if not objectives or len(set(objectives))!=len(objectives) or set(objectives)-set(FIELDS):raise ValueError('Explicit unique objective set required')
    if 'von_mises' not in objectives:raise ValueError('von Mises objective required for nominal material reference')
    patches=build_stress_patches(result);maxima={}
    patches['initial_samples']=[(u,v,evaluate_bernstein(patches['sigma'],u,v),evaluate_bernstein(patches['tau'],u,v))
                                for u in (0.,.5,1.) for v in (0.,.5,1.)]
    for objective in objectives:
        r=maximize_field(patches,objective,relative_tolerance=relative_tolerance,absolute_tolerance_MPa=absolute_tolerance_MPa,
                         max_subdivisions=max_subdivisions,max_depth=max_depth)
        r['witness']=_witness_state(result,patches,r);maxima[objective]=r
    vm=maxima['von_mises'];lower=max(0.,vm['lower_MPa']);upper=max(0.,vm['upper_MPa'])
    # Exact no-action/no-field source has no finite material first-yield factor.
    zero=(all(not any(a['q_xy_N_mm']) and a['couple_N']==0 if a['kind']=='uniform'
              else not any(a['force_xy_N']) and a['couple_Nmm']==0 for a in result['loads'])
          and all(not any(c) for e in result['elements'] for c in e['coefficients'].values()))
    if zero:
        factor=dict(lower=None,upper=None,finite=False,kind='exact_zero_field',reason='Exact zero source field: no finite proportional first-yield factor')
        state='zero_source_field'
    else:
        l=float((I(fy)/upper).lo) if upper>0 else None
        h=float((I(fy)/lower).hi) if lower>0 else None
        factor=dict(lower=l,upper=h,finite=l is not None and h is not None,
            kind='bounded_interval' if h is not None else 'upper_unbounded_within_numerical_bounds',
            reason='Proportional scaling of all source actions, including PP; not a design resistance' if h is not None
                   else 'Certified maximum-stress lower bound is zero; no finite upper load-factor bound was established')
        state=('below_nominal_material_yield_in_this_field' if upper<=fy else
               'nominal_material_elastic_limit_exceeded_in_this_field' if lower>fy else
               'indeterminate_within_numerical_bounds')
    phi=abs(result['max_abs_phi']['phi_rad'])
    twist=None if factor['lower'] is None else dict(lower=float((I(factor['lower'])*phi).lo),
        upper=None if factor['upper'] is None else float((I(factor['upper'])*phi).hi),
        scope='Algebraic scaling of source maximum twist only; not a geometrically nonlinear prediction or rotation limit')
    digest=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(schema='vlasov_nominal_material_envelope_v1',combination_id=result['combination_id'],
        limit_state=result['limit_state'],member_id=result['member_id'],source_field_sha256=digest,
        source_method=result['method'],section_profile_id=result['section']['profile_id'],
        section_content_sha256=result['section']['content_sha256'],fy_MPa=fy,material_origin=material_origin,
        material_assumption='Isotropic symmetric nominal tension/compression yield; no hardening or cold-work enhancement',
        yield_measure='sqrt(sigma_midline^2 + 3*tau_face^2), isotropic J2 nominal material reference',
        stress_tensor_basis='Longitudinal normal stress and longitudinal-contour shear only; other components absent in the beam approximation',
        stress_envelopes=maxima,all_requested_field_bounds_converged=all(r['converged'] for r in maxima.values()),
        nominal_material_state=state,proportional_load_to_nominal_material_yield=factor,
        source_max_abs_phi_rad=phi,source_small_rotation_warning=result['small_rotation_warning'],
        algebraic_max_abs_phi_at_nominal_yield_rad=twist,
        resistance_factor_applied=False,normative_resistance_qualified=False,resistance_qualified=False,physical_design_approved=False,
        whole_member_approved=False,coverage_complete=False,
        scope='Material first-yield reference of the recovered first-order thin-wall field, not a design resistance or first-failure load',
        excluded=['Normal stress at true finite-thickness exterior fibres','FE discretization-error bound',
          'Geometric/nonlinear validity and follower-load effects','Local/distortional/global instability',
          'Inelastic reserve, effective stiffness and complete serviceability','Local load introduction and stress concentrations'],
        source_field_definition=patches['source_field'])
