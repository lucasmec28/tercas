"""Read-only arithmetic audit of saved Hermite coefficients. Never solve K u=f.

Reconstruct K*u-f from the saved displacement vector, the pinned section and
original loads. Apply the original solver's 1e-6 numerical checks unchanged.
This proves snapshot consistency, not first-order physical adequacy or FE error.
"""
import copy
import math
import numpy as np
from numpy.polynomial import polynomial as poly
from .en_ue125_300_authority import _sha
from .torsion_vlasov.vlasov import matrix,resolve_actions,evaluate,_qualify_numerics
from .torsion_vlasov.bounded_polynomial import real_roots_open_unit_interval


def _same(a,b,label):
    if _sha(a)!=_sha(b):raise ValueError('Original Vlasov arithmetic mismatch: '+label)


def validate(demand):
    a=demand;p=a['section']['properties'];L=a['length_mm'];loads=a['loads']
    _same(resolve_actions(a['section'],L,loads),loads,'load torques')
    physical=sorted({0.,L}|{x['s_mm'] for x in loads if x['kind']=='point' and 0<x['s_mm']<L})
    if len(loads)>100 or min(b-a for a,b in zip(physical,physical[1:]))<L/100:
        raise ValueError('Original physical-load interval/resource qualification failed')
    stations=a['mesh_stations_mm'];n=len(stations);elements=a['elements']
    if n>2049:raise ValueError('Original mesh resource qualification failed')
    _same(stations,[elements[0]['a_mm']]+[e['b_mm'] for e in elements],'mesh')
    if n!=len(elements)+1 or len(a['node_phi_rad'])!=n or len(a['node_psi_per_mm'])!=n:
        raise ValueError('Original nodal field dimensions differ')
    values=a['node_phi_rad']+a['node_psi_per_mm']
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('Finite real nodal field required')
    u=np.empty(2*n);u[::2]=a['node_phi_rad'];u[1::2]=a['node_psi_per_mm']
    GJ=a['G_MPa']*p['J_mm4'];ECw=a['E_MPa']*p['Cw_mm6']
    m=math.fsum(x['torque_SC_N'] for x in loads if x['kind']=='uniform')
    K=np.zeros((2*n,2*n));f=np.zeros(2*n)
    for i,e in enumerate(elements):
        ell=e['b_mm']-e['a_mm'];k=matrix(ell,GJ,ECw)
        fe=m*np.array([ell/2,ell*ell/12,ell/2,-ell*ell/12]);ids=np.arange(2*i,2*i+4)
        K[np.ix_(ids,ids)]+=k;f[ids]+=fe;d=u[ids];r=k@d-fe
        _same(r.tolist(),e['end_actions'],'element end actions')
        phi=np.array([d[0],ell*d[1],-3*d[0]-2*ell*d[1]+3*d[2]-ell*d[3],2*d[0]+ell*d[1]-2*d[2]+ell*d[3]])
        psi=poly.polyder(phi)/ell;tsv=GJ*psi;t=np.array([-r[0],-m*ell])
        b=poly.polysub(np.array([r[1],-r[0]*ell,-m*ell*ell/2]),GJ*poly.polysub(phi,[phi[0]]))
        fields={'phi_rad':phi,'psi_per_mm':psi,'B_Nmm2':b,'T_Nmm':t,'Tsv_Nmm':tsv,
            'Tw_Nmm':poly.polysub(t,tsv),'B_constitutive_Nmm2':-ECw*poly.polyder(phi,2)/ell**2,
            'T_constitutive_Nmm':poly.polysub(tsv,ECw*poly.polyder(phi,3)/ell**3)}
        _same({k:v.tolist() for k,v in fields.items()},e['coefficients'],'recovered polynomials')
    for load in loads:
        if load['kind']=='point':f[2*stations.index(load['s_mm'])]+=load['torque_SC_Nmm']
    fixed=[0,2*n-2]
    for side,index in [('left',1),('right',2*n-1)]:
        support=a['support_hypotheses'][side]
        if support['twist']!='fixed' or support['warping'] not in ('free_assumed','restrained_assumed'):
            raise ValueError('Original support hypotheses unavailable')
        if support['warping']=='restrained_assumed':fixed.append(index)
    if any(u[i]!=0 for i in fixed):raise ValueError('Fixed nodal displacement changed')
    free=np.array([i for i in range(2*n) if i not in fixed]);scale=1/np.sqrt(np.diag(K[np.ix_(free,free)]))
    reaction=K@u-f;energy=.5*float(u@K@u);work=.5*float(u@f)
    expected={'energy_Nmm':energy,'half_external_work_Nmm':work,
        'relative_energy_error':abs(energy-work)/max(abs(energy),abs(work),1e-30),
        'scaled_free_residual':float(np.linalg.norm(scale*reaction[free]))/max(float(np.linalg.norm(scale*f[free])),1e-30)}
    for k,v in expected.items():_same(v,a['numerics'][k],k)
    ra=a['support_reactions'];ex,ey=np.array(p['centroid_xy_mm'])-np.array(p['shear_center_xy_mm'])
    for side,idx in [('left',0),('right',-2)]:
        force=ra[side+'_force_xy_N']
        values={side+'_total_moment_about_SC_Nmm':float(reaction[idx]),
            side+'_generalized_torque_at_CG_Nmm':float(reaction[idx]-ex*force[1]+ey*force[0]),
            side+'_generalized_warping_Nmm2':float(reaction[idx+1])}
        for k,v in values.items():_same(v,ra[k],k)
    total=m*L+math.fsum(x['torque_SC_Nmm'] for x in loads if x['kind']=='point')
    _same(total,ra['total_external_torque_SC_Nmm'],'external torque')
    _same(float(reaction[0]+reaction[-2])+total,ra['torque_equilibrium_residual_Nmm'],'torque residual')
    proof=copy.deepcopy(a);_qualify_numerics(proof)
    _same(proof['numerics'],a['numerics'],'original numerical qualification')
    # Recreate all original scalar critical stations, not a new stress envelope.
    states=[]
    for i,e in enumerate(elements):
        loc={0.,1.}
        for c in e['coefficients'].values():loc.update(real_roots_open_unit_interval(poly.polyder(c)))
        ends=[evaluate(a,i,u0) for u0 in (0.,1.)]
        for k in ('Vx_N','Vy_N'):
            loc.update(real_roots_open_unit_interval([ends[0][k],ends[1][k]-ends[0][k]]))
        states.extend(evaluate(a,i,u0) for u0 in sorted(loc))
    # The adapter adds this scope note after recovering the source states.
    def numeric_states(rows):
        return [{k:v for k,v in s.items() if k!='analysis_domain'} for s in rows]
    support=a.get('support_limit_states',[])
    _same(numeric_states(a['critical_states'][:len(support)]),numeric_states(support),'before-P critical prefix')
    actual=a['critical_states'][len(support):]
    _same(numeric_states(states),numeric_states(actual),'critical states')
    maximum=max(states,key=lambda s:abs(s['phi_rad']))
    _same(numeric_states([maximum]),numeric_states([a['max_abs_phi']]),'rotation witness')
    _same(abs(maximum['phi_rad'])>a['numerics']['rotation_warning_rad'],a['small_rotation_warning'],'rotation warning')
    return True
