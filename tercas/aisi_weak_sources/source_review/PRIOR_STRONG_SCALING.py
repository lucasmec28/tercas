"""Homogeneity audit for the SAME elastic FSM problem at AISI nominal E.

No interpolation in thickness or borrowing a design capacity from another code.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy.linalg import eigh
from vendor import fsm_core as core
ROOT=Path(__file__).resolve().parent
ratio=203000./200000.;rows=[]
for file in sorted((ROOT/'modes').glob('*.npz')):
 z=np.load(file);p=z['nodes'];s=z['stress'];t=float(z['t']);L=float(z['L']);nu=float(z['nu']);assert nu==.3 and float(z['E'])==200000.
 K0,Q0=core.matrices(p,t,L,s,200000.,nu);K1,Q1=core.matrices(p,t,L,s,203000.,nu)
 eK=np.linalg.norm(K1-ratio*K0)/np.linalg.norm(K1);eQ=np.linalg.norm(Q1-Q0)/np.linalg.norm(Q1)
 assert eK<2e-14 and eQ==0
 lam=z['eigenvalues']*ratio;v=z['modes'];a=K1@v;b=(Q1@v)*lam
 residual=float(max(np.linalg.norm(a-b,axis=0)/(np.linalg.norm(a,axis=0)+np.linalg.norm(b,axis=0))))
 assert residual<1e-6
 direct=None
 if file.name in ['t1.50_strong_local.npz','t3.35_strong_distortional.npz']:
  d=1/np.sqrt(np.diag(K1));n=len(d);mu=eigh(d[:,None]*Q1*d,d[:,None]*K1*d,subset_by_index=[n-8,n-1],eigvals_only=True,driver='gvx');f=1/mu[::-1]
  direct=float(max(abs(f/lam-1)));assert direct<1e-6
 rows.append(dict(file=file.name,half_wave_mm=L,K_scaling_relative_error=float(eK),geometric_matrix_relative_error=float(eQ),scaled_eigenpair_residual=residual,direct_eigensolve_max_relative_error=direct,original_eigenvalues=z['eigenvalues'].tolist(),AISI_E_eigenvalues=lam.tolist()))
result=dict(status='PASS same discrete eigenproblem only',E_original_MPa=200000.,E_AISI_MPa=203000.,nu=.3,ratio=ratio,
 theorem='K(E,nu)=E*K(1,nu), Kg independent of E at fixed reference moment; all eigenvalues scale with E, eigenvectors and valley stations unchanged',
 scope='Same 209-node conventional FSM, stress field and fixed nu. Not a new continuum buckling proof or material test. AISI G=78000 is used separately in global/Vlasov formulas; plate FSM uses E and nu.',rows=rows)
(ROOT/'MATERIAL_SCALING.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
