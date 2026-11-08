"""Three-girt bilateral first-order network with exact or Hermite torsion.
Same physical section, point couplings, load lines and end supports as snapshots.
Exact mode needs only physical force stations; no invented stiffness/support.
"""
import copy,json,math,warnings
from pathlib import Path
import numpy as np
from numpy.polynomial import polynomial as poly
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import spsolve,MatrixRankWarning
from .element import element,point_map,DOFS
from .element import shape_physical
from .exact_torsion import matrices as exact_matrices,state as exact_state
HERE=Path(__file__).resolve().parent


def beam_matrix(L,s,load,mode):
    if mode=='hermite':return element(L,s,load)
    if mode!='exact':raise ValueError('mode must be exact or hermite')
    qy=load['q_y_N_mm'];qz=load['q_z_N_mm'];mCG=load.get('distributed_torque_CG_N',load['load_y_from_CG_mm']*qz-load['load_z_from_CG_mm']*qy)
    m=mCG-s['sc_y_mm']*qz+s['sc_z_mm']*qy
    # Keep EB/EA and their CG/SC transformation, then replace BOTH torsional
    # stiffness and consistent torque load with exact static quantities.
    s0=dict(s,J_mm4=0.,Cw_mm6=0.);l0=dict(load,distributed_torque_CG_N=s['sc_y_mm']*qz-s['sc_z_mm']*qy)
    K,f=element(L,s0,l0);kt,ft=exact_matrices(L,s['G_MPa']*s['J_mm4'],s['E_MPa']*s['Cw_mm6'],m)
    ids=[3,6,10,13];K[np.ix_(ids,ids)]+=kt;f[ids]+=ft
    return K,f


def solve(model,mode='exact',subdivisions=1):
    from ..load_application_policy import active as ct_active
    inp=model['inputs'];ct=ct_active(inp);s=inp['section'];L=inp['L_mm'];physical=[0.]+inp['attachment_x_mm']+[L]
    xs=[]
    for a,b in zip(physical,physical[1:]):xs.extend(np.linspace(a,b,subdivisions+1)[:-1])
    xs.append(L);xs=np.array(xs);columns=len(xs);xyz=np.array([[x,y,0.] for y in (inp['upper_gap_mm'],0.,-inp['lower_gap_mm']) for x in xs]);nd=7*len(xyz)
    ii=[];jj=[];values=[];f=np.zeros(nd);physical_nodal=np.zeros(nd);beams=[];bars=[]
    def add(ids,k):
        ii.extend(np.repeat(ids,len(ids)).tolist());jj.extend(np.tile(ids,len(ids)).tolist());values.extend(k.ravel().tolist())
    for row,name in enumerate(('upper','middle','lower')):
        load=inp['loads'][row]
        for j,(a,b) in enumerate(zip(xs,xs[1:])):
            na=row*columns+j;nb=na+1;ids=np.r_[np.arange(7*na,7*na+7),np.arange(7*nb,7*nb+7)]
            k,g=beam_matrix(b-a,s,load,mode);add(ids,k);f[ids]+=g
            beams.append(dict(girt=name,a=na,b=nb,x_start_mm=float(a),x_end_mm=float(b),length_mm=float(b-a),ids=ids,k=k,f=g,load=load))
    oldcolumns=model['mesh_columns']
    def remap(old):
        row=old//oldcolumns;x=model['nodes'][old]['xyz_CG_mm'][0];matches=np.flatnonzero(xs==x)
        if len(matches)!=1:raise ValueError('Original physical connection station absent; not rounded')
        return row*columns+int(matches[0])
    for old in model['bars']:
        na,nb=remap(old['a']),remap(old['b']);ca,cb=old['connections'];A,B=point_map(ca),point_map(cb)
        delta=xyz[nb]+cb['arm_mm']-xyz[na]-ca['arm_mm'];ell=float(np.linalg.norm(delta));n=delta/ell
        beta=np.r_[-n@A,n@B];ids=np.r_[np.arange(7*na,7*na+7),np.arange(7*nb,7*nb+7)];mat=old['material'];k=mat['E_MPa']*mat['A_mm2']/ell
        add(ids,k*np.outer(beta,beta));weight=mat['mass_kg_m']*ell/1000*9.80665*inp['brace_weight_factor'] if inp['brace_self_weight'] else 0.
        wF=np.array([0.,-weight/2,0.])
        # Load eccentricity is independent of the actual connection kinematics.
        # Transverse weight has no axial component and hence no sectorial work.
        W=point_map(dict(arm_mm=[0.,s['sc_y_mm'],s['sc_z_mm']],omega_mm2=0.)) if ct else None
        w=np.r_[(W if ct else A).T@wF,(W if ct else B).T@wF]
        f[ids]+=w;physical_nodal[ids]+=w
        bars.append(dict(id=old['id'],a=na,b=nb,ids=ids,k=k,beta=beta,connections=copy.deepcopy(old['connections']),direction=n,self_weight_N=weight))
    for load in inp['nodal_loads']:
        na=remap(load['node']);f[7*na:7*na+7]+=load['values'];physical_nodal[7*na:7*na+7]+=load['values']
    K=coo_matrix((values,(ii,jj)),shape=(nd,nd)).tocsr();fixed=[]
    for row in range(3):
        for col in (0,columns-1):
            fixed.extend(7*(row*columns+col)+j for j in (0,1,2,3))
            if inp['warping_end_condition']=='restrained_assumed':fixed.append(7*(row*columns+col)+6)
    fixed=np.array(sorted(fixed));free=np.setdiff1d(np.arange(nd),fixed);Kff=K[free][:,free]
    if np.any(Kff.diagonal()<=0) or not np.isfinite(Kff.data).all():raise ValueError('Nonpositive/nonfinite stiffness; no extra restraint added')
    scale=1/np.sqrt(Kff.diagonal());Ks=diags(scale)@Kff@diags(scale)
    eig=np.linalg.eigvalsh(Ks.toarray())
    ratio=float(eig[0]/eig[-1])
    if ratio<=1e-11:raise ValueError('Mechanism or ill-conditioned current model; no pseudoinverse or artificial restraint')
    with warnings.catch_warnings():
        warnings.simplefilter('error',MatrixRankWarning);u=np.zeros(nd);u[free]=scale*spsolve(Ks,scale*f[free])
    reaction=K@u-f
    for b in bars:b['force_N']=float(b['k']*(b['beta']@u[b['ids']]));b['physical_girt_actions']=(-b['force_N']*b['beta']).reshape(2,7)
    result=dict(mode=mode,subdivisions=subdivisions,section=s,inputs=inp,columns=columns,xs=xs,xyz=xyz,K=K,f=f,physical_nodal=physical_nodal,
        u=u,reactions=reaction,fixed=fixed,free=free,beams=beams,bars=bars)
    result['linear_matrix_diagnostic']=dict(scaled_eigen_ratio=ratio,threshold=1e-11,scope='linear rank/conditioning, NOT buckling')
    return result


def response(run,beam,x):
    s=run['section'];L=beam['length_mm'];local=x-beam['x_start_mm'];t=local/L;u=run['u'][beam['ids']].copy();load=beam['load']
    for j in (0,7):u[j+1]-=s['sc_z_mm']*u[j+3];u[j+2]+=s['sc_y_mm']*u[j+3]
    v=shape_physical(u[1],u[5],u[8],u[12],L,load['q_y_N_mm'],s['E_MPa']*s['I_weak_mm4'])
    w=shape_physical(u[2],-u[4],u[9],-u[11],L,load['q_z_N_mm'],s['E_MPa']*s['I_strong_mm4'])
    def value(c,k=0):return float(poly.polyval(local,poly.polyder(c,k)))
    qy=load['q_y_N_mm'];qz=load['q_z_N_mm'];mCG=load.get('distributed_torque_CG_N',load['load_y_from_CG_mm']*qz-load['load_z_from_CG_mm']*qy);m=mCG-s['sc_y_mm']*qz+s['sc_z_mm']*qy
    S=s['G_MPa']*s['J_mm4'];D=s['E_MPa']*s['Cw_mm6'];nodal=u[[3,6,10,13]]
    if run['mode']=='exact':a=exact_state(L,S,D,m,nodal,t)
    else:
        ph=shape_physical(nodal[0],nodal[1],nodal[2],nodal[3],L,0.,1.)
        a=dict(phi=value(ph),psi=value(ph,1),d2=value(ph,2),d3=value(ph,3),d4=value(ph,4))
        a.update(B=-D*a['d2'],T=S*a['psi']-D*a['d3'],Tsv=S*a['psi'],Tw=-D*a['d3'],differential_residual=D*a['d4']-S*a['d2']-m)
    pcg=beam['k']@run['u'][beam['ids']]-beam['f'];Q=np.eye(14)
    for j in (0,7):Q[j+1,j+3]=-s['sc_z_mm'];Q[j+2,j+3]=s['sc_y_mm']
    p=np.linalg.solve(Q.T,pcg)
    Teq=-p[3]-m*local;Beq=p[6]-p[3]*local-m*local**2/2-S*(a['phi']-nodal[0])
    Vy=s['E_MPa']*s['I_weak_mm4']*value(v,3);Vz=s['E_MPa']*s['I_strong_mm4']*value(w,3)
    return dict(x_mm=float(x),girt=beam['girt'],N_N=s['E_MPa']*s['A_mm2']*(u[7]-u[0])/L,
        My_strong_Nmm=-s['E_MPa']*s['I_strong_mm4']*value(w,2),Mz_weak_Nmm=s['E_MPa']*s['I_weak_mm4']*value(v,2),Vy_N=Vy,Vz_N=Vz,
        phi_rad=a['phi'],psi_per_mm=a['psi'],B_constitutive_Nmm2=a['B'],B_equilibrium_Nmm2=Beq,
        T_constitutive_SC_Nmm=a['T'],T_equilibrium_SC_Nmm=Teq,T_equilibrium_CG_Nmm=Teq+s['sc_z_mm']*Vy-s['sc_y_mm']*Vz,
        T_SV_Nmm=a['Tsv'],T_w_Nmm=a['Tw'],uy_CG_mm=value(v)+s['sc_z_mm']*a['phi'],uz_CG_mm=value(w)-s['sc_y_mm']*a['phi'],
        rx_rad=a['phi'],ry_rad=-value(w,1),rz_rad=value(v,1),ux_CG_mm=float(u[0]+(u[7]-u[0])*t),
        torsion_ODE_residual=a['differential_residual'],end_actions_basic=p.tolist())


def at(run,girt,x,side='right'):
    candidates=[b for b in run['beams'] if b['girt']==girt and b['x_start_mm']<=x<=b['x_end_mm']]
    beam=candidates[0] if side=='left' else candidates[-1]
    return response(run,beam,x)


def continuum_energy(run):
    s=run['section'];internal=0.;external=float(run['physical_nodal']@run['u']);xis,weights=np.polynomial.legendre.leggauss(12)
    for e in run['beams']:
        for t,w in zip((xis+1)/2,weights*e['length_mm']/2):
            a=response(run,e,e['x_start_mm']+t*e['length_mm']);load=e['load'];qy=load['q_y_N_mm'];qz=load['q_z_N_mm'];mCG=load.get('distributed_torque_CG_N',load['load_y_from_CG_mm']*qz-load['load_z_from_CG_mm']*qy)
            internal+=w*(a['N_N']**2/(s['E_MPa']*s['A_mm2'])+a['My_strong_Nmm']**2/(s['E_MPa']*s['I_strong_mm4'])+a['Mz_weak_Nmm']**2/(s['E_MPa']*s['I_weak_mm4'])+a['T_SV_Nmm']**2/(s['G_MPa']*s['J_mm4'])+a['B_constitutive_Nmm2']**2/(s['E_MPa']*s['Cw_mm6']))
            external+=w*(qy*a['uy_CG_mm']+qz*a['uz_CG_mm']+mCG*a['phi_rad'])
    for b in run['bars']:internal+=b['force_N']**2/b['k']
    return dict(twice_continuum_energy_Nmm=internal,physical_external_work_Nmm=external,relative_error=abs(internal-external)/max(1.,abs(external)))
