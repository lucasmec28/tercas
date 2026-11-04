"""One first-order Vlasov route for a single prismatic fork-supported member.

Not a 6DOF+correction hybrid. The complete Hermite GJ+ECw block is assembled.
No roof-sheet restraint, no guessed load line, no guessed warping restraint.
Transverse flexure resultants are statically determinate and concomitant.
This is elastic demand analysis, not LTB, local/distortional strength or ELS.
"""
import copy
import math
import warnings

import numpy as np
from numpy.polynomial import polynomial as poly
from scipy.linalg import solve, LinAlgWarning, LinAlgError

from .bounded_polynomial import real_roots_open_unit_interval
from .section import finite, verify_section

METHOD = 'single_vlasov_CBCA_Annex_A_v1'


class NumericalQualificationError(ValueError):
    """An elastic demand must not be reported from an unqualified solve."""
    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def matrix(L, GJ, ECw):
    """Same closed Hermite energy matrix as qualified 7DOF, not two models."""
    a = np.array([[36.,3*L,-36.,3*L],[3*L,4*L*L,-3*L,-L*L],
                  [-36.,-3*L,36.,-3*L],[3*L,-L*L,-3*L,4*L*L]])
    b = np.array([[12.,6*L,-12.,6*L],[6*L,4*L*L,-6*L,2*L*L],
                  [-12.,-6*L,12.,-6*L],[6*L,2*L*L,-6*L,4*L*L]])
    return GJ*a/(30*L)+ECw*b/L**3


def _origin(v, name):
    if not isinstance(v,str) or not v.strip():
        raise ValueError(name+': explicit origin/idealization required')
    return v


def _xy(v, name):
    if not isinstance(v,(tuple,list)) or len(v)!=2:
        raise ValueError(name+': two explicit coordinates/components required')
    return [finite(x,name) for x in v]


def resolve_actions(section, L, actions):
    """Reduce each transverse action to its own torque about SC, never CG."""
    if not isinstance(actions,list) or not actions:
        raise ValueError('Explicit action records required, including zero actions when applicable')
    out=[];ids=set();cg=section['properties']['centroid_xy_mm'];sc=section['properties']['shear_center_xy_mm']
    for a0 in actions:
        if not isinstance(a0,dict):raise ValueError('Action record required')
        a=copy.deepcopy(a0);name=_origin(a.get('name'),'action name')
        if name in ids:raise ValueError('Duplicate action identity')
        ids.add(name);_origin(a.get('origin'),'action origin')
        xy=_xy(a.get('application_xy_mm'),'application line in frozen section axes')
        if a.get('kind')=='uniform':
            q=_xy(a.get('q_xy_N_mm'),'uniform force');couple=finite(a.get('couple_N'),'uniform couple')
            tcg=(xy[0]-cg[0])*q[1]-(xy[1]-cg[1])*q[0]+couple
            tsc=(xy[0]-sc[0])*q[1]-(xy[1]-sc[1])*q[0]+couple
            a.update(q_xy_N_mm=q,couple_N=couple,torque_CG_N=tcg,torque_SC_N=tsc)
        elif a.get('kind')=='point':
            q=_xy(a.get('force_xy_N'),'point force');couple=finite(a.get('couple_Nmm'),'point couple')
            x=finite(a.get('s_mm'),'point station')
            if not 0<=x<=L:raise ValueError('Point station outside member')
            tcg=(xy[0]-cg[0])*q[1]-(xy[1]-cg[1])*q[0]+couple
            tsc=(xy[0]-sc[0])*q[1]-(xy[1]-sc[1])*q[0]+couple
            a.update(force_xy_N=q,couple_Nmm=couple,s_mm=x,torque_CG_Nmm=tcg,torque_SC_Nmm=tsc)
        else:raise ValueError('Only uniform and explicit-position transverse point actions are supported')
        a['application_xy_mm']=xy;out.append(a)
    return out


def solve_member(*, section, length_mm, E_MPa, G_MPa, actions, supports,
                 combination_id, limit_state, member_id, action_accounting_origin,
                 elements_per_interval=32, rotation_warning_rad=.05):
    """All end choices required. Neither of the two choices is certified as real.

supports={left/right:{twist:'fixed',warping:'free_assumed'|'restrained_assumed',origin:str}}.
Point actions split the mesh but do not create intermediate supports/releases.
Axial point loads, eccentric longitudinal braces, distributed bimoments and
load-following/second-order effects are intentionally outside this API.
"""
    L=finite(length_mm,'length',True);E=finite(E_MPa,'E',True);G=finite(G_MPa,'G',True)
    if type(elements_per_interval) is not int or not 2<=elements_per_interval<=128:
        raise ValueError('2 to 128 elements per load interval required')
    if not isinstance(supports,dict) or set(supports)!=set(('left','right')):
        raise ValueError('Both support records required')
    supports=copy.deepcopy(supports)
    for end in ('left','right'):
        r=supports[end]
        if r.get('twist')!='fixed' or r.get('warping') not in ('free_assumed','restrained_assumed'):
            raise ValueError('Explicit twist and independent warping hypotheses required')
        _origin(r.get('origin'),'support origin')
    for name,v in [('combination',combination_id),('member',member_id),('action accounting',action_accounting_origin)]:
        _origin(v,name)
    if limit_state not in ('ELU','ELS','REFERENCE'):
        raise ValueError('Limit-state family required; no inference from action name')
    warn=finite(rotation_warning_rad,'rotation warning',True)
    source=copy.deepcopy(section)
    # The source is a constructed section object, not an editable scalar catalogue record.
    verify_section(source)
    p=source['properties'];GJ=G*finite(p['J_mm4'],'J',True);ECw=E*finite(p['Cw_mm6'],'Cw',True)
    loads=resolve_actions(source,L,actions)
    if len(loads)>100:raise ValueError('Research action resource budget exceeded')
    uniform=[a for a in loads if a['kind']=='uniform'];points=[a for a in loads if a['kind']=='point']
    m=math.fsum(a['torque_SC_N'] for a in uniform)
    q=np.array([math.fsum(a['q_xy_N_mm'][j] for a in uniform) for j in (0,1)])
    physical=sorted(set([0.,L]+[a['s_mm'] for a in points if 0<a['s_mm']<L]))
    minimum_interval=min(b-a for a,b in zip(physical[:-1],physical[1:]))
    if minimum_interval < L/100:
        raise NumericalQualificationError(
            'Finite point actions require physical load intervals >= L/100 in this qualified mesh domain; '
            'do not replace a finite point by the analytical support limit',
            {'minimum_load_interval_mm':minimum_interval,'required_minimum_mm':L/100,
             'domain_gate_is_normative_limit':False})
    stations=[]
    for a,b in zip(physical[:-1],physical[1:]):
        stations.extend(np.linspace(a,b,elements_per_interval+1)[:-1].tolist())
    stations.append(L)
    if len(stations)>2049:raise ValueError('Research mesh resource budget exceeded')
    n=len(stations);K=np.zeros((2*n,2*n));f=np.zeros(2*n);elements=[]
    for i,(a,b) in enumerate(zip(stations[:-1],stations[1:])):
        ell=b-a;k=matrix(ell,GJ,ECw);fe=m*np.array([ell/2,ell*ell/12,ell/2,-ell*ell/12]);ids=np.arange(2*i,2*i+4)
        K[np.ix_(ids,ids)]+=k;f[ids]+=fe
        elements.append(dict(element_id=f'{member_id}:e{i+1}',a_mm=a,b_mm=b,k=k,fe=fe,ids=ids))
    for a in points:
        i=stations.index(a['s_mm']);f[2*i]+=a['torque_SC_Nmm']
    fixed=[0,2*n-2]
    if supports['left']['warping']=='restrained_assumed':fixed.append(1)
    if supports['right']['warping']=='restrained_assumed':fixed.append(2*n-1)
    free=np.array([i for i in range(2*n) if i not in fixed]);u=np.zeros(2*n)
    kff=K[np.ix_(free,free)];scale=1/np.sqrt(np.diag(kff));ks=kff*scale[:,None]*scale[None,:]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',LinAlgWarning)
            u[free]=scale*solve(ks,scale*f[free],assume_a='pos')
    except (LinAlgError,LinAlgWarning) as exc:
        raise NumericalQualificationError('Unqualified elastic linear solve: '+str(exc)) from exc
    if not np.isfinite(u).all():raise ValueError('Nonfinite elastic solution')
    reaction=K@u-f;energy=.5*float(u@K@u);work=.5*float(u@f)
    RA=-q*L/2;RB=-q*L/2
    for a in points:
        force=np.array(a['force_xy_N']);RA-=force*(L-a['s_mm'])/L;RB-=force*a['s_mm']/L
    ex,ey=np.array(p['centroid_xy_mm'])-np.array(p['shear_center_xy_mm'])
    output=[]
    for e in elements:
        ids=e.pop('ids');d=u[ids];r=e.pop('k')@d-e.pop('fe');ell=e['b_mm']-e['a_mm']
        phi=np.array([d[0],ell*d[1],-3*d[0]-2*ell*d[1]+3*d[2]-ell*d[3],
                      2*d[0]+ell*d[1]-2*d[2]+ell*d[3]])
        psi=poly.polyder(phi)/ell;tsv=GJ*psi;t=np.array([-r[0],-m*ell])
        b=poly.polysub(np.array([r[1],-r[0]*ell,-m*ell*ell/2]),GJ*poly.polysub(phi,[phi[0]]))
        fields={'phi_rad':phi,'psi_per_mm':psi,'B_Nmm2':b,'T_Nmm':t,'Tsv_Nmm':tsv,
                'Tw_Nmm':poly.polysub(t,tsv),'B_constitutive_Nmm2':-ECw*poly.polyder(phi,2)/ell**2,
                'T_constitutive_Nmm':poly.polysub(tsv,ECw*poly.polyder(phi,3)/ell**3)}
        e.update(coefficients={k:v.tolist() for k,v in fields.items()},end_actions=r.tolist())
        output.append(e)
    result={'schema':'single_vlasov_member_demand_v1','method':METHOD,'section':source,
        'length_mm':L,'E_MPa':E,'G_MPa':G,'loads':loads,'support_hypotheses':supports,
        'combination_id':combination_id,'limit_state':limit_state,'member_id':member_id,
        'action_accounting_origin':action_accounting_origin,'mesh_stations_mm':stations,
        'node_phi_rad':u[::2].tolist(),'node_psi_per_mm':u[1::2].tolist(),'elements':output,
        'support_reactions':{'left_force_xy_N':RA.tolist(),'right_force_xy_N':RB.tolist(),
            'left_total_moment_about_SC_Nmm':float(reaction[0]),'right_total_moment_about_SC_Nmm':float(reaction[-2]),
            'left_generalized_torque_at_CG_Nmm':float(reaction[0]-ex*RA[1]+ey*RA[0]),
            'right_generalized_torque_at_CG_Nmm':float(reaction[-2]-ex*RB[1]+ey*RB[0]),
            'left_generalized_warping_Nmm2':float(reaction[1]),'right_generalized_warping_Nmm2':float(reaction[-1])},
        'numerics':{'energy_Nmm':energy,'half_external_work_Nmm':work,
            'relative_energy_error':abs(energy-work)/max(abs(energy),abs(work),1e-30),
            'scaled_free_residual':float(np.linalg.norm(scale*reaction[free]))/max(float(np.linalg.norm(scale*f[free])),1e-30),
            'rotation_warning_rad':warn,'rotation_warning_is_normative_limit':False},
        'analysis_domain':{'method':METHOD,'prismatic_single_span':True,'intermediate_braces':False,
            'order':1,'small_rotation_kinematics':True,'gross_line_section':True,
            'sheet_contact':False,'sheet_restraint':False,'axial_force_in_this_model_N':0.,
            'effective_stiffness':False,'buckling':False,'physical_hypotheses_verified':False,
            'declared_hypotheses_scope':'Calculation of explicitly declared load lines and independent end restraints; not proof of their physical realization',
            'connection_design':'Excluded; local introduction into the profile is a separate member check',
            'finite_load_intervals_minimum_fraction_of_span':.01,
            'mesh_domain_limit_is_normative':False},
        'demand_coverage_complete_for_declared_model':True,'coverage_complete':False,
        'missing':['first-order applicability',
                   'combined strength under N,M,V,T,B','effective stiffness/serviceability',
                   'local load introduction into the profile'],
        'physical_design_approved':False,'resistance_qualified':False,'whole_member_approved':False}
    states=[]
    for i,e in enumerate(output):
        loc={0.,1.}
        for v in e['coefficients'].values():
            loc.update(real_roots_open_unit_interval(poly.polyder(v)))
        ends=[evaluate(result,i,u0) for u0 in (0.,1.)]
        for key in ('Vx_N','Vy_N'):
            loc.update(real_roots_open_unit_interval([ends[0][key],ends[1][key]-ends[0][key]]))
        for t0 in sorted(loc):
            states.append(evaluate(result,i,t0))
    result['critical_states']=states
    result['critical_state_scope']='Individual field extrema and both element sides; not a certificate of maximum combined stress or resistance interaction'
    result['max_abs_phi']=max(states,key=lambda s:abs(s['phi_rad']))
    result['small_rotation_warning']=abs(result['max_abs_phi']['phi_rad'])>warn
    result['support_reactions']['total_external_torque_SC_Nmm']=m*L+math.fsum(a['torque_SC_Nmm'] for a in points)
    result['support_reactions']['torque_equilibrium_residual_Nmm']=float(reaction[0]+reaction[-2])+result['support_reactions']['total_external_torque_SC_Nmm']
    _qualify_numerics(result)
    return result


def _qualify_numerics(result):
    """Reject loss of equilibrium even when the scaled linear residual is small.

This is a numerical gate, not a physical first-order or resistance criterion.
Separate checks preserve the sign of point-torque jumps and B continuity.
"""
    loads=result['loads'];L=result['length_mm'];n=len(result['elements'])
    torque_scale=math.fsum(abs(a['torque_SC_N'])*L if a['kind']=='uniform'
                          else abs(a['torque_SC_Nmm']) for a in loads)
    torque_scale=max(torque_scale,1e-30);bimoment_scale=torque_scale*L
    torques=[];bimoments=[]
    for i in range(n-1):
        left=evaluate(result,i,1.);right=evaluate(result,i+1,0.)
        jump=math.fsum(a['torque_SC_Nmm'] for a in loads
                      if a['kind']=='point' and a['s_mm']==right['s_mm'])
        torques.append(abs(right['T_Nmm']-left['T_Nmm']+jump)/torque_scale)
        bimoments.append(abs(right['B_Nmm2']-left['B_Nmm2'])/bimoment_scale)
    free_b=[]
    for end,i,u in [('left',0,0.),('right',n-1,1.)]:
        if result['support_hypotheses'][end]['warping']=='free_assumed':
            free_b.append(abs(evaluate(result,i,u)['B_Nmm2'])/bimoment_scale)
    diagnostics={
        'relative_torque_equilibrium_error':abs(result['support_reactions']['torque_equilibrium_residual_Nmm'])/torque_scale,
        'maximum_relative_internal_torque_jump_error':max(torques,default=0.),
        'maximum_relative_bimoment_continuity_error':max(bimoments,default=0.),
        'maximum_relative_free_end_bimoment_error':max(free_b,default=0.),
        'relative_energy_error':result['numerics']['relative_energy_error'],
        'scaled_free_residual':result['numerics']['scaled_free_residual']}
    tolerance=1e-6
    result['numerics'].update(diagnostics,qualification_tolerance=tolerance,
        qualification_tolerance_is_normative=False,qualification_passed=True,
        qualification_scope='Equilibrium, continuity and linear-solve consistency; not an a priori discretization-error bound',
        discretization_error_bound_certified=False,
        torque_normalization_Nmm=torque_scale,bimoment_normalization_Nmm2=bimoment_scale)
    failed={k:v for k,v in diagnostics.items() if not math.isfinite(v) or v>tolerance}
    if failed:
        raise NumericalQualificationError('Elastic numerical qualification failed: '+', '.join(failed),diagnostics)


def evaluate(result, element_index, u):
    """Physical coordinate and side belong to this element, including rounding."""
    if type(element_index) is not int or not 0<=element_index<len(result['elements']):
        raise ValueError('Valid element index required')
    u=finite(u,'element parameter')
    if not 0<=u<=1:raise ValueError('Element parameter outside [0,1]')
    e=result['elements'][element_index];ell=e['b_mm']-e['a_mm'];s=e['a_mm']+u*ell
    # Match the actual exported coordinate; retain both adjoining elements/sides.
    if s==e['a_mm']:u=0.;side='right'
    elif s==e['b_mm']:u=1.;side='left'
    else:side='interior'
    fields={k:float(poly.polyval(u,c)) for k,c in e['coefficients'].items()}
    q=np.array([math.fsum(a['q_xy_N_mm'][j] for a in result['loads'] if a['kind']=='uniform') for j in (0,1)])
    RA=np.array(result['support_reactions']['left_force_xy_N']);V=-RA-q*s
    Mx=-RA[1]*s-q[1]*s*s/2;My=RA[0]*s+q[0]*s*s/2
    for a in result['loads']:
        if a['kind']!='point':continue
        point=a['s_mm'];P=np.array(a['force_xy_N'])
        active=s>point or (s==point and side!='left')
        if active:V-=P
        Mx-=P[1]*max(s-point,0.);My+=P[0]*max(s-point,0.)
    sc=result['section']['properties']['shear_center_xy_mm'];cg=result['section']['properties']['centroid_xy_mm']
    # T_CG = T_SC - (CG-SC) x V, since T_SC = T_CG +(CG-SC) x V.
    tcg=fields['T_Nmm']-(cg[0]-sc[0])*V[1]+(cg[1]-sc[1])*V[0]
    fields.update(N_N=0.,Mx_physical_Nmm=float(Mx),My_physical_Nmm=float(My),
        Mforte_R01_Nmm=float(-Mx),Mfraco_R01_Nmm=float(-My),
        Vx_N=float(V[0]),Vy_N=float(V[1]),T_CG_Nmm=float(tcg))
    return dict(combination_id=result['combination_id'],limit_state=result['limit_state'],
        member_id=result['member_id'],element_id=e['element_id'],element_index=element_index,
        x_mm=s,s_mm=s,u=u,side=side,**fields,
        sign_convention='N/sigma tension positive; physical Mx=int(y sigma),My=-int(x sigma); R01 capacity moments are negatives',
        analysis_domain=copy.deepcopy(result['analysis_domain']),coverage_complete=False,
        missing=copy.deepcopy(result['missing']),source={'method':METHOD,'profile_id':result['section']['profile_id'],
            'nodes_sha256':result['section']['nodes_sha256']})
