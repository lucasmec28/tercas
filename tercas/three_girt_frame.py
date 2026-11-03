"""Conditional 3D elastic frame/truss model of the pictured three-girt system.

Units N, mm. X longitudinal, Y up, Z normal to facade. At each centroid node:
[ux,uy,uz,rx,ry,rz], rotations right-handed. Girts remain continuous; only end
translations/twist explicitly selected below are restrained. Rods are axial
bilateral T/C, first order. This is a Saint-Venant diagnostic, NOT a qualified
open-section warping, stability, ELS or NBR resistance calculation.
"""
import copy
import math
import numpy as np
from .bounded_polynomial import real_roots_open_unit_interval

DOFS=('ux','uy','uz','rx','ry','rz')
LEVELS=('upper','middle','lower')


def topology(attachment_count,include_green=True):
    """Declared extension of the two-line sketch; diagonals attach to edge lines.

    Zero lines gives three unconnected simply supported girders. One line has
    two upper-end diagonals meeting the same middle-girt station. More than two
    lines adds verticals at each station, NOT guessed extra diagonal patterns.
    """
    if isinstance(attachment_count,bool) or not isinstance(attachment_count,int) or not 0<=attachment_count<=20:
        raise ValueError('Use 0 to 20 internal attachment lines in this implementation')
    n=attachment_count;c=n+2
    if not n:return []
    links=[('blue_diag_left',0,c+1,'blue'),('blue_diag_right',c-1,c+n,'blue')]
    for j in range(1,n+1):
        label=('left' if j==1 else 'right') if n==2 else str(j)
        links.append(('blue_vertical_'+label,c+j,2*c+j,'blue'))
    if include_green:
        for j in range(1,n+1):
            label=('left' if j==1 else 'right') if n==2 else str(j)
            links.append(('green_'+label,j,c+j,'green'))
    return links


def _finite(v,name,positive=False):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (positive and v<=0):
        raise ValueError(name+': finite '+('positive ' if positive else '')+'number required')
    return float(v)


def _beam_matrix(L,E,G,A,Iy,Iz,J):
    """Closed-form 12DOF EB/Saint-Venant stiffness, not the independent oracle."""
    K=np.zeros((12,12))
    for ids,coef in [([0,6],E*A/L),([3,9],G*J/L)]:
        K[np.ix_(ids,ids)]+=coef*np.array([[1.,-1.],[-1.,1.]])
    H=np.array([[12.,6*L,-12.,6*L],[6*L,4*L*L,-6*L,2*L*L],
                [-12.,-6*L,12.,-6*L],[6*L,2*L*L,-6*L,4*L*L]])
    for ids,I,signs in [([1,5,7,11],Iz,[1,1,1,1]),([2,4,8,10],Iy,[1,-1,1,-1])]:
        K[np.ix_(ids,ids)]+=E*I/L**3*H*np.outer(signs,signs)
    return K


def _hybrid_transform(sc_y,sc_z):
    # SC-CG=(0,sc_y,sc_z). Axial coordinate remains ux_CG, not ux_SC.
    T=np.eye(12)
    for j in (0,6):
        T[j+1,j+3]=-sc_z  # v_SC=v_CG-sc_z*rx
        T[j+2,j+3]= sc_y  # w_SC=w_CG+sc_y*rx
    return T


def _load_vector(L,qy,qz,tx_sc):
    f=np.zeros(12)
    f[[1,7]]=qy*L/2;f[[5,11]]=[qy*L*L/12,-qy*L*L/12]
    f[[2,8]]=qz*L/2;f[[4,10]]=[-qz*L*L/12,qz*L*L/12]
    f[[3,9]]=tx_sc*L/2
    return f


def _arm(r):
    x,y,z=r
    return np.array([[1.,0.,0.,0.,z,-y],[0.,1.,0.,-z,0.,x],[0.,0.,1.,y,-x,0.]])


def _roots_inside(coeff):
    return real_roots_open_unit_interval(coeff)


def _derivative(c,order=1):
    return np.polynomial.polynomial.polyder(c,order)


def _evaluate(c,t):return float(np.polynomial.polynomial.polyval(t,c))


def _hermite_exact(d0,s0,d1,s1,L,q,EI):
    # Normalized t in [0,1]; exact quartic load bubble has zero d/d' at ends.
    c=np.array([d0,L*s0,3*(d1-d0)-L*(2*s0+s1),2*(d0-d1)+L*(s0+s1),0.])
    c+=q*L**4/(24*EI)*np.array([0.,0.,1.,-2.,1.])
    return c


def element_response(element,x_mm):
    """All concomitant signed fields at one section of one stored beam element.

    Shears use the left-reaction convention: Mz'=Vy, My'=-Vz.
    N is tensile-positive; T_SC=GJ*rx'. T_CG=T_SC+sc_z*Vy-sc_y*Vz.
    """
    L=element['length_mm'];t=(x_mm-element['x_start_mm'])/L
    if not -1e-12<=t<=1+1e-12:raise ValueError('Section outside selected element')
    p=element['polynomials'];v=p['uy_SC'];w=p['uz_SC'];phi=p['rx'];s=element['section']
    y=_evaluate(v,t);z=_evaluate(w,t);rx=_evaluate(phi,t)
    Vy=s['E_MPa']*s['I_weak_mm4']*_evaluate(_derivative(v,3),t)/L**3
    Vz=s['E_MPa']*s['I_strong_mm4']*_evaluate(_derivative(w,3),t)/L**3
    T=s['G_MPa']*s['J_mm4']*_evaluate(_derivative(phi),t)/L
    return dict(x_mm=float(x_mm),girt=element['girt'],element=element['id'],
                N_N=element['axial_tension_N'],Vy_N=Vy,Vz_N=Vz,
                My_strong_Nmm=-s['E_MPa']*s['I_strong_mm4']*_evaluate(_derivative(w,2),t)/L**2,
                Mz_weak_Nmm=s['E_MPa']*s['I_weak_mm4']*_evaluate(_derivative(v,2),t)/L**2,
                T_SC_Nmm=T,T_CG_Nmm=T+s['sc_z_mm']*Vy-s['sc_y_mm']*Vz,
                ux_CG_mm=_evaluate(p['ux_CG'],t),uy_CG_mm=y+s['sc_z_mm']*rx,
                uz_CG_mm=z-s['sc_y_mm']*rx,uy_SC_mm=y,uz_SC_mm=z,
                rx_rad=rx,ry_rad=-_evaluate(_derivative(w),t)/L,rz_rad=_evaluate(_derivative(v),t)/L)


def solve_three_girts(*,L_mm,upper_gap_mm,lower_gap_mm,attachment_x_mm,section,
                      blue,green,loads,axial_restraint,connection_offsets=None,
                      include_green=True,brace_self_weight=False,brace_weight_factor=1.):
    """Three parallel continuous girders plus the declared axial-bar topology.

    section: A_mm2,I_strong_mm4,I_weak_mm4,J_mm4,E_MPa,G_MPa,sc_y_mm,sc_z_mm,
    origin. SC offsets are CG->SC, explicitly supplied, NEVER inferred here.
    blue/green: A_mm2,E_MPa,mass_kg_m,origin. Green axial action is an assumption.
    loads: list [upper,middle,lower], each with q_y_N_mm,q_z_N_mm,
    load_y_from_CG_mm,load_z_from_CG_mm. Optional distributed_torque_CG_N
    gives the TOTAL resultant distributed torque about CG, replacing that from
    the line coordinates (useful for forces at different points). Units Nmm/mm.
    No factors or self weight are inferred.
    Axial restraint: 'both_ends', 'left_only', or 'none' (mechanism diagnostic).
    Every end fixes uy,uz,rx; ry/rz remain free. No spring or tension-only law.
    connection_offsets optionally maps each bar ID to two [ex,ey,ez] arms from
    connected girt CGs. No sectorial warping displacement is represented. brace_weight_factor multiplies
    the characteristic bar selfweight explicitly (e.g. PP coefficient of each combination).
    """
    L=_finite(L_mm,'L',True);up=_finite(upper_gap_mm,'upper gap',True);low=_finite(lower_gap_mm,'lower gap',True)
    if not isinstance(attachment_x_mm,(list,tuple)) or len(attachment_x_mm)>20:raise ValueError('Use 0 to 20 attachment x coordinates')
    interior=[_finite(x,'attachment x') for x in attachment_x_mm]
    stations=[0.]+interior+[L]
    if any(b<=a for a,b in zip(stations,stations[1:])):raise ValueError('Require strictly ordered interior x coordinates; no dimensions inferred from image')
    columns=len(stations)
    weight_factor=_finite(brace_weight_factor,'brace weight factor')
    if weight_factor<0:raise ValueError('Brace selfweight factor cannot be negative')
    if axial_restraint not in ('both_ends','left_only','none'):raise ValueError('Declare axial end translations')
    if not isinstance(include_green,bool) or not isinstance(brace_self_weight,bool):raise ValueError('Model switches must be boolean')
    s=copy.deepcopy(section)
    for key in ('A_mm2','I_strong_mm4','I_weak_mm4','J_mm4','E_MPa','G_MPa'):s[key]=_finite(s.get(key),key,True)
    for key in ('sc_y_mm','sc_z_mm'):s[key]=_finite(s.get(key),key)
    if not isinstance(s.get('origin'),str) or not s['origin'].strip():raise ValueError('Section/SC data origin required')
    materials={}
    for name,raw in [('blue',blue),('green',green)]:
        if name=='green' and not include_green:continue
        m=copy.deepcopy(raw)
        for key in ('A_mm2','E_MPa'):m[key]=_finite(m.get(key),name+' '+key,True)
        m['mass_kg_m']=_finite(m.get('mass_kg_m',0.),name+' mass')
        if m['mass_kg_m']<0:raise ValueError('Mass cannot be negative')
        if not isinstance(m.get('origin'),str) or not m['origin'].strip():raise ValueError('Bar data origin required')
        materials[name]=m
    if not isinstance(loads,(list,tuple)) or len(loads)!=3:raise ValueError('Three explicit girt load vectors required')
    loads=copy.deepcopy(loads)
    for load in loads:
        for key in ('q_y_N_mm','q_z_N_mm','load_y_from_CG_mm','load_z_from_CG_mm'):
            load[key]=_finite(load.get(key),key)
        if 'distributed_torque_CG_N' in load:load['distributed_torque_CG_N']=_finite(load['distributed_torque_CG_N'],'distributed torque CG')
    levels=[up,0.,-low]
    xyz=np.array([[x,y,0.] for y in levels for x in stations]);ndof=6*len(xyz)
    K=np.zeros((ndof,ndof));f=np.zeros(ndof);beams=[];bars=[]
    transform=_hybrid_transform(s['sc_y_mm'],s['sc_z_mm'])
    for row,name in enumerate(LEVELS):
        load=loads[row];qy=load['q_y_N_mm'];qz=load['q_z_N_mm']
        torque_cg=load.get('distributed_torque_CG_N',load['load_y_from_CG_mm']*qz-load['load_z_from_CG_mm']*qy)
        tx=torque_cg-s['sc_y_mm']*qz+s['sc_z_mm']*qy
        for col in range(columns-1):
            a=columns*row+col;b=a+1;ell=stations[col+1]-stations[col]
            ids=np.r_[np.arange(6*a,6*a+6),np.arange(6*b,6*b+6)]
            kb=_beam_matrix(ell,s['E_MPa'],s['G_MPa'],s['A_mm2'],s['I_strong_mm4'],s['I_weak_mm4'],s['J_mm4'])
            fb=_load_vector(ell,qy,qz,tx);kg=transform.T@kb@transform;fg=transform.T@fb
            K[np.ix_(ids,ids)]+=kg;f[ids]+=fg
            beams.append(dict(id=name+'_'+str(col+1),girt=name,a=a,b=b,ids=ids,k_basic=kb,f_basic=fb,
                              length_mm=ell,x_start_mm=stations[col],x_end_mm=stations[col+1],qy=qy,qz=qz,tx_sc=tx))
    links=topology(len(interior),include_green)
    offsets={} if connection_offsets is None else copy.deepcopy(connection_offsets)
    if not isinstance(offsets,dict) or set(offsets)-{name for name,_,_,_ in links}:raise ValueError('Unknown connection-offset bar ID')
    for name,a,b,kind in links:
        arms=offsets.get(name,[[0.,0.,0.],[0.,0.,0.]])
        if not isinstance(arms,(list,tuple)) or len(arms)!=2 or any(not isinstance(r,(list,tuple)) or len(r)!=3 for r in arms):raise ValueError('Two 3D arms required per bar')
        ra,rb=(np.array([_finite(v,'connection arm') for v in r]) for r in arms)
        delta=xyz[b]+rb-xyz[a]-ra;ell=float(np.linalg.norm(delta))
        if ell<=0:raise ValueError('Zero bar length')
        n=delta/ell;B=np.r_[-n@_arm(ra),n@_arm(rb)];m=materials[kind]
        ids=np.r_[np.arange(6*a,6*a+6),np.arange(6*b,6*b+6)]
        k=m['E_MPa']*m['A_mm2']/ell*np.outer(B,B);K[np.ix_(ids,ids)]+=k
        weight=m['mass_kg_m']*ell/1000*9.80665*weight_factor if brace_self_weight else 0.
        if weight:
            force=np.array([0.,-weight/2,0.]);f[6*a:6*a+6]+=_arm(ra).T@force;f[6*b:6*b+6]+=_arm(rb).T@force
        bars.append(dict(id=name,kind=kind,a=a,b=b,ids=ids,B=B,length_mm=ell,direction=n,arms=[ra,rb],material=m,self_weight_N=weight))
    fixed=[]
    for row in range(3):
        for col in (0,columns-1):
            node=columns*row+col;fixed += [6*node+i for i in (1,2,3)]
            if axial_restraint=='both_ends' or (axial_restraint=='left_only' and col==0):fixed.append(6*node)
    fixed=sorted(set(fixed));free=np.setdiff1d(np.arange(ndof),fixed);Kff=K[np.ix_(free,free)]
    base=dict(model='three_girts_3d_Saint_Venant_diagnostic_v1',status='not_solved',
              axes='X longitudinal; Y up; Z normal; right-handed rotations',
              inputs=dict(L_mm=L,upper_gap_mm=up,lower_gap_mm=low,attachment_x_mm=interior,section=s,blue=blue,green=green,
                          loads=loads,axial_restraint=axial_restraint,connection_offsets=offsets,include_green=include_green,brace_self_weight=brace_self_weight,brace_weight_factor=weight_factor),
              physical_conditions_verified=False,warping_qualified=False,resistance_qualified=False,whole_member_approved=False,
              boundary_conditions=dict(fixed_dofs=[dict(node=i//6,dof=DOFS[i%6]) for i in fixed],
                                       bending_end_rotations='free',interior_girt_rotations='continuous',warping='NOT represented; end twist fixity does not specify warping'),
              limitations=['Saint-Venant GJ only: no ECw, bimoment or warping axial stress/restriction.',
                           'Rod axial T/C and first-order hypotheses do not verify buckling or real rod/connection stiffness.',
                           'Girt N is retained; the existing N=0 biaxial resistance route is not applicable automatically.',
                           'Girt centroid/SC offsets and attachment arms are declared, not measured or certified.',
                           'Gross elastic displacement only; no effective-inertia ELS approval or relative-panel criterion.',
                           'No second-order/geometric stiffness; transverse effects of pre-existing axial force are absent.'])
    if np.any(np.diag(Kff)<=0):
        base['reason']='Unstiffened free DOF; no artificial restraint added';return base
    scale=1/np.sqrt(np.diag(Kff));Ks=Kff*scale[:,None]*scale[None,:]
    eig,vec=np.linalg.eigh(Ks);ratio=float(eig[0]/eig[-1])
    base['stability_diagnostic']=dict(scaled_eigen_min=float(eig[0]),scaled_eigen_max=float(eig[-1]),ratio=ratio,
                                     threshold=1e-11,scope='rank/conditioning of linear elastic matrix, NOT buckling resistance')
    if ratio<=1e-11:
        v=scale*vec[:,0];order=np.argsort(np.abs(v))[-8:][::-1]
        base['reason']='Mechanism or numerically ill-conditioned declared model; no pseudo-inverse or extra restraint used'
        base['stability_diagnostic']['dominant_free_mode_dofs']=[dict(node=int(free[i]//6),dof=DOFS[free[i]%6],amplitude=float(v[i])) for i in order]
        return base
    u=np.zeros(ndof);u[free]=scale*np.linalg.solve(Ks,scale*f[free]);r=K@u-f
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(r)):raise ArithmeticError('Nonfinite model response')
    forces=(r+f).reshape(-1,6);balance_force=np.sum(forces[:,:3],axis=0)
    balance_moment=np.sum(forces[:,3:]+np.cross(xyz,forces[:,:3]),axis=0)
    free_force=max((abs(r[i]) for i in free if i%6<3),default=0.)
    free_moment=max((abs(r[i]) for i in free if i%6>=3),default=0.)
    Fscale=max(1.,float(np.sum(np.abs(f.reshape(-1,6)[:,:3]))))
    Mscale=max(Fscale*max(L,up+low),1.,float(np.sum(np.abs(f.reshape(-1,6)[:,3:]))))
    residuals=dict(free_force_max_N=float(free_force),free_moment_max_Nmm=float(free_moment),
                   global_force_N=balance_force.tolist(),global_moment_Nmm=balance_moment.tolist())
    base['residuals']=residuals
    if max(free_force,float(np.max(np.abs(balance_force))))>1e-7*Fscale or max(free_moment,float(np.max(np.abs(balance_moment))))>1e-7*Mscale:
        base['reason']='Equilibrium residual exceeds diagnostic gate; no response released';return base
    output_beams=[];all_states=[]
    for e in beams:
        ell=e['length_mm'];ub=transform@u[e['ids']]
        v=_hermite_exact(ub[1],ub[5],ub[7],ub[11],ell,e['qy'],s['E_MPa']*s['I_weak_mm4'])
        w=_hermite_exact(ub[2],-ub[4],ub[8],-ub[10],ell,e['qz'],s['E_MPa']*s['I_strong_mm4'])
        phi=np.array([ub[3],ub[9]-ub[3]+e['tx_sc']*ell**2/(2*s['G_MPa']*s['J_mm4']),-e['tx_sc']*ell**2/(2*s['G_MPa']*s['J_mm4']),0.,0.])
        item={k:e[k] for k in ('id','girt','a','b','length_mm','x_start_mm','x_end_mm')}
        item.update(section=copy.deepcopy(s),axial_tension_N=float(s['E_MPa']*s['A_mm2']*(ub[6]-ub[0])/ell),
                    polynomials={'ux_CG':[float(ub[0]),float(ub[6]-ub[0])],'uy_SC':v.tolist(),'uz_SC':w.tolist(),'rx':phi.tolist()},
                    end_actions_CG=(transform.T@(e['k_basic']@ub-e['f_basic'])).tolist())
        ts={0.,1.}
        # Exact extrema of each displayed displacement/rotation/force component.
        for c in (v+s['sc_z_mm']*phi,w-s['sc_y_mm']*phi,phi,_derivative(v,2),_derivative(w,2),_derivative(v,3),_derivative(w,3),_derivative(phi)):
            ts.update(_roots_inside(_derivative(c)))
        values=[]
        for t in sorted(ts):
            x=e['x_start_mm'] if t==0 else e['x_end_mm'] if t==1 else e['x_start_mm']+t*ell
            z=element_response(item,x);z['side']='right' if t==0 else 'left' if t==1 else 'interior';values.append(z)
        item['critical_sections']=values;output_beams.append(item);all_states+=values
    output_bars=[]
    for b in bars:
        N=float(b['material']['E_MPa']*b['material']['A_mm2']/b['length_mm']*(b['B']@u[b['ids']]))
        output_bars.append({**{k:b[k] for k in ('id','kind','a','b','length_mm','material','self_weight_N')},
                            'direction':b['direction'].tolist(),'connection_arms_mm':[v.tolist() for v in b['arms']],
                            'axial_tension_N':N,'axial_state':'tension' if N>1e-8 else 'compression' if N<-1e-8 else 'zero',
                            'actions_on_girt_nodes':(-N*b['B']).reshape(2,6).tolist(),'resistance_checked':False})
    summaries={}
    for name in LEVELS:
        states=[z for z in all_states if z['girt']==name];summaries[name]={}
        for key in ('N_N','Vy_N','Vz_N','My_strong_Nmm','Mz_weak_Nmm','T_SC_Nmm','T_CG_Nmm','uy_CG_mm','uz_CG_mm','rx_rad'):
            summaries[name][key]={'min':min(states,key=lambda z:z[key]),'max':max(states,key=lambda z:z[key]),'max_abs':max(states,key=lambda z:abs(z[key]))}
    base.update(status='conditional_elastic_diagnostic',nodes=[dict(id=i,xyz_CG_mm=xyz[i].tolist(),displacements=dict(zip(DOFS,u[6*i:6*i+6].tolist())),
                    applied_nodal_loads=f[6*i:6*i+6].tolist(),support_reactions=r[6*i:6*i+6].tolist()) for i in range(len(xyz))],
                beams=output_beams,bars=output_bars,girt_envelopes=summaries,
                primary_torsion_present=any(abs(z['T_SC_Nmm'])>1e-8*Mscale for z in all_states))
    return base
