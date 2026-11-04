"""Independent gross linear 7DOF assembly and exact static condensation.

N, mm, rad. No strength, effective rigidity, second order or tie unilateral law.
Reads frozen synthetic fields; does not import or modify any candidate solver.
"""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from numpy.polynomial import polynomial as P

HERE=Path(__file__).resolve().parent
DOFS=('ux','uy','uz','rx','ry','rz','psi')


def symmetric_solve(k,b):
    d=1/np.sqrt(np.diag(k))
    return d[:,None]*np.linalg.solve(d[:,None]*k*d[None,:],d[:,None]*b) if b.ndim==2 else d*np.linalg.solve(d[:,None]*k*d[None,:],d*b)


def shape(x,L,deriv=0):
    c=np.array([[1,0,-3,2],[0,L,-2*L,L],[0,0,3,-2],[0,0,-L,L]])
    return np.array([P.polyval(x,P.polyder(v,deriv))/L**deriv for v in c])


def element(L,s,load):
    # Independent Gauss integration, not the closed-form stiffness of the source.
    K=np.zeros((14,14));f=np.zeros(14)
    Q=np.eye(14)
    for j in (0,7):
        Q[j+1,j+3]=-s['sc_z_mm'];Q[j+2,j+3]=s['sc_y_mm']
    h_ids=[3,6,10,13];v_ids=[1,5,8,12];w_ids=[2,4,9,11]
    qy=load['q_y_N_mm'];qz=load['q_z_N_mm']
    mCG=load.get('distributed_torque_CG_N',load['load_y_from_CG_mm']*qz-load['load_z_from_CG_mm']*qy)
    m=mCG-s['sc_y_mm']*qz+s['sc_z_mm']*qy
    for xi,wi in zip(*np.polynomial.legendre.leggauss(5)):
        t=(xi+1)/2;w=wi*L/2
        rows=[]
        a=np.zeros(14);a[[0,7]]=[-1/L,1/L];rows.append((a,s['E_MPa']*s['A_mm2']))
        a=np.zeros(14);a[v_ids]=shape(t,L,2);rows.append((a,s['E_MPa']*s['I_weak_mm4']))
        a=np.zeros(14);a[w_ids]=shape(t,L,2)*[1,-1,1,-1];rows.append((a,s['E_MPa']*s['I_strong_mm4']))
        a=np.zeros(14);a[h_ids]=shape(t,L,1);rows.append((a,s['G_MPa']*s['J_mm4']))
        a=np.zeros(14);a[h_ids]=shape(t,L,2);rows.append((a,s['E_MPa']*s['Cw_mm6']))
        for a,coef in rows:K+=w*coef*np.outer(a,a)
        f[v_ids]+=w*qy*shape(t,L)
        f[w_ids]+=w*qz*shape(t,L)*[1,-1,1,-1]
        f[h_ids]+=w*m*shape(t,L)
    return Q.T@K@Q,Q.T@f


def point_map(c):
    # Construct each unit motion from the vector cross product and sectorial u_x.
    r=np.array(c['arm_mm']);a=np.zeros((3,7));a[:,:3]=np.eye(3)
    for j in range(3):a[:,3+j]=np.cross(np.eye(3)[j],r)
    a[0,6]=-c['omega_mm2']
    return a


def shape_physical(d0,s0,d1,s1,L,q,EI):
    # Solve the integration constants of EI d''''=q from endpoint kinematics.
    c=np.zeros(5);c[0]=d0;c[1]=s0;c[4]=q/(24*EI)
    c[2:4]=np.linalg.solve(np.array([[L**2,L**3],[2*L,3*L**2]]),np.array([d1-d0-s0*L-c[4]*L**4,s1-s0-4*c[4]*L**3]))
    return c

