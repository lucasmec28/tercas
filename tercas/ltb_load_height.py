"""Isolated classical Vlasov LBA, NOT wired to production resistances.

Single prismatic member, fork ends, free warping, rigid section with strong-axis
symmetry, conservative dead transverse loads, no intermediate restraints.
Displacements prior to buckling, primary-torsion geometric stress, local and
distortional modes are NOT represented. Horizontal eccentricity is reported as
first-order torque rather than made zero. See METHOD_AND_INTEGRATION.txt.

Conventions: beam s, cross-section x right/y up. Signed q/P positive DOWN.
h=y_load-y_SC is positive above SC. Hence gravity at top has q*h>0 and removes
torsional tangent stiffness; suction reverses that contribution.

Energy: 2Pi=int(EIy*u''²+GJ*phi'²+ECw*phi''²)ds
 +lambda*(2int(M*u''*phi)ds-int(sum(q*h)*phi²)ds-sum(P*h*phi(a)²)).
Eq2 Sahraei/Pezeshky/Mohareb CSCE2017, changed vertical sign convention.
Sin(n*pi*s/L) basis satisfies fork/free-warping boundary conditions.
"""
from __future__ import annotations
import math
import numbers
import numpy as np
from scipy.linalg import eigh

SOURCE_ENERGY='https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf'
SOURCE_CHANNEL='https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf'


def finite(x, name, positive=False):
    if isinstance(x,(bool,np.bool_)) or not isinstance(x,numbers.Real):
        raise ValueError(name+': finite real required')
    x=float(x)
    if not math.isfinite(x) or (positive and x<=0):raise ValueError(name+': out of domain')
    return x


def action_terms(actions,L):
    """Each action retains own height. Never infer h from net q or moment sign."""
    if not isinstance(actions,list):raise ValueError('actions must be a list')
    records=[];seen=set()
    for a in actions:
        if not isinstance(a,dict):raise ValueError('action must be a mapping')
        name=a.get('name')
        if not isinstance(name,str) or not name.strip() or name in seen:
            raise ValueError('unique nonempty action name required')
        seen.add(name)
        h=finite(a.get('height_above_SC_mm'),'height')
        # Horizontal offset is irrelevant to THIS linear eigenoperator. Unknown
        # is explicitly retained, never replaced by a fictional zero torque.
        ex=None if a.get('x_from_SC_mm') is None else finite(a.get('x_from_SC_mm'),'horizontal eccentricity')
        if a.get('kind')=='uniform':
            force=finite(a.get('q_down_N_mm'),'q');station=None
        elif a.get('kind')=='point':
            force=finite(a.get('P_down_N'),'P');station=finite(a.get('s_mm'),'station')
            if not 0<=station<=L:raise ValueError('point outside member')
        else:raise ValueError('only full-span uniform and point actions')
        records.append(dict(a,force=force,station=station,
            height_tangent_term=force*h,primary_torque=None if ex is None else -ex*force))
    return records


def moment_values(x,L,loads,end_moment):
    x=np.asarray(x,float);M=np.full_like(x,end_moment)
    for a in loads:
        f=a['force'];s=a['station']
        M+=f*x*(L-x)/2 if s is None else f*np.minimum((L-s)*x/L,s*(L-x)/L)
    return M


def maximum_moment(L,loads,end_moment):
    cuts=sorted({0.,L}|{a['station'] for a in loads if a['station'] is not None})
    q=math.fsum(a['force'] for a in loads if a['station'] is None)
    ra=q*L/2+math.fsum(a['force']*(L-a['station'])/L for a in loads if a['station'] is not None)
    candidates=set(cuts)
    if q:
        for a,b in zip(cuts[:-1],cuts[1:]):
            v=ra-math.fsum(p['force'] for p in loads if p['station'] is not None and p['station']<=a)
            root=v/q
            if a<root<b:candidates.add(root)
    return max(abs(moment_values(sorted(candidates),L,loads,end_moment)))


def solve(*,L_mm,E_MPa,G_MPa,Iweak_mm4,J_mm4,Cw_mm6,actions,
          modes=32,constant_end_moment_Nmm=0.):
    """Research LBA of the explicitly defined model, not a resistance approval.

The constant-end-moment parameter exists for an analytical validation case.
The numerical mode count is a research discretization, not a code limit.
"""
    L,E,G,I,J,Cw=[finite(v,k,True) for k,v in zip(
        ('L','E','G','Iweak','J','Cw'),(L_mm,E_MPa,G_MPa,Iweak_mm4,J_mm4,Cw_mm6))]
    if type(modes) is not int or not 1<=modes<=128:raise ValueError('modes 1..128 required')
    moment=finite(constant_end_moment_Nmm,'end moment');loads=action_terms(actions,L)
    k=np.arange(1,modes+1)*math.pi/L
    diag=np.r_[E*I*k**4*L/2,(E*Cw*k**4+G*J*k*k)*L/2]
    KG=np.zeros((2*modes,2*modes));C=np.zeros((modes,modes))
    # Split at every physical load; do not create an artificial restraint there.
    cuts=sorted({0.,L}|{a['station'] for a in loads if a['station'] is not None})
    gx,gw=np.polynomial.legendre.leggauss(2*modes+8)
    qh=math.fsum(a['height_tangent_term'] for a in loads if a['station'] is None)
    for left,right in zip(cuts[:-1],cuts[1:]):
        x=(left+right)/2+(right-left)*gx/2;w=gw*(right-left)/2
        S=np.sin(k[:,None]*x);M=moment_values(x,L,loads,moment)
        C+=((-k*k)[:,None]*S*(M*w))@S.T
        KG[modes:,modes:]-=(S*(qh*w))@S.T
    KG[:modes,modes:]=C;KG[modes:,:modes]=C.T
    for a in loads:
        if a['station'] is not None and 0<a['station']<L:
            shape=np.sin(k*a['station'])
            KG[modes:,modes:]-=a['height_tangent_term']*np.outer(shape,shape)
    scale=1/np.sqrt(diag)
    A=-KG*scale[:,None]*scale[None,:]
    values,vectors=eigh(A,subset_by_index=[2*modes-1,2*modes-1])
    mu=float(values[-1]);Mmax=float(maximum_moment(L,loads,moment))
    base=dict(method='classical_Vlasov_sine_Ritz_LBA_research_v1',modes=modes,
        primary_torque_by_action=[dict(name=a['name'],kind=a['kind'],value=a['primary_torque'],
            units='N' if a['station'] is None else 'Nmm') for a in loads],
        height_tangent_by_action=[dict(name=a['name'],value=a['height_tangent_term']) for a in loads],
        maximum_reference_moment_Nmm=Mmax,
        primary_torsion_resistance_included=False,primary_torsion_predeformation_included=False,
        local_distortional_modes_included=False,geometry_hypotheses_verified=False,
        whole_member_approved=False,production_resistance_authorized=False,
        boundary_conditions='fork ends; free warping; no intermediate restraints',
        sources=[SOURCE_ENERGY,SOURCE_CHANNEL])
    if mu<=0:return dict(base,status='no_positive_eigenvalue',lambda_cr=None,Me_Nmm=None)
    factor=1/mu;v=vectors[:,-1]
    residual=np.linalg.norm(A@v-mu*v)/max(np.linalg.norm(A)*np.linalg.norm(v),1e-300)
    return dict(base,status=('research_elastic_critical_computed' if Mmax else
                            'rotational_eigenvalue_without_reference_bending'),lambda_cr=factor,
        Me_Nmm=factor*Mmax if Mmax else None,scaled_eigen_residual=float(residual),
        ritz_eigenvalue_is_safe_lower_bound=False)


def refined(**kwargs):
    """Numerical comparison, not a rigorous lower bound or physical validation."""
    if 'modes' in kwargs:raise ValueError('refined owns the numerical mode sequence')
    history=[];previous=None
    for n in (16,32,64,128):
        r=solve(**kwargs,modes=n)
        entry=dict(modes=n,lambda_cr=r['lambda_cr'],Me_Nmm=r['Me_Nmm'])
        if r['Me_Nmm'] is None:
            return dict(r,refinement_history=history+[entry],numerically_converged=False)
        change=None if previous is None else abs(r['lambda_cr']/previous-1)
        entry['relative_change']=change;history.append(entry)
        if change is not None and change<1e-5 and r['scaled_eigen_residual']<1e-12:
            return dict(r,refinement_history=history,numerically_converged=True,
                        convergence_tolerance=1e-5,convergence_is_error_bound=False)
        previous=r['lambda_cr']
    return dict(r,status='numerical_refinement_inconclusive',Me_Nmm=None,
                refinement_history=history,numerically_converged=False,
                reason='Research resolution budget exhausted; not a normative domain restriction')


def closed_form(*,L_mm,E_MPa,G_MPa,Iweak_mm4,J_mm4,Cw_mm6,C1,C2,zg_mm):
    """Vermeylen2023 Eq1 for k_z=k_w=1; coefficients must match load case.

No production caller may supply arbitrary C1/C2 to bypass a load-case check.
This isolated helper only reproduces published benchmarks.
"""
    L,E,G,I,J,Cw,c1=[finite(v,k,True) for k,v in zip(
        ('L','E','G','I','J','Cw','C1'),(L_mm,E_MPa,G_MPa,Iweak_mm4,J_mm4,Cw_mm6,C1))]
    z=finite(C2,'C2')*finite(zg_mm,'zg')
    a=Cw/I+L*L*G*J/(math.pi**2*E*I)
    r=math.hypot(math.sqrt(a),z)
    term=a/(r+z) if z>=0 else r-z
    return c1*math.pi**2*E*I/L**2*term
