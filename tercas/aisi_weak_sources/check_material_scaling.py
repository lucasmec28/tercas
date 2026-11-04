"""New material checks for 18 weak eigenpairs; strong audit is not repeated."""
from pathlib import Path
import json,math,hashlib
import numpy as np
from scipy.linalg import eigh
from vendor import fsm_core as core
ROOT=Path(__file__).resolve().parent
ratio=203000/200000;rows=[]
for file in sorted((ROOT/'modes').glob('*.npz')):
 z=np.load(file);nodes=z['nodes'];s=z['stress'];t=float(z['t']);L=float(z['L']);nu=float(z['nu'])
 assert nu==.3 and float(z['E'])==200000
 K0,Q0=core.matrices(nodes,t,L,s,200000.,nu);K1,Q1=core.matrices(nodes,t,L,s,203000.,nu)
 eK=float(np.linalg.norm(K1-ratio*K0)/np.linalg.norm(K1));eQ=float(np.linalg.norm(Q1-Q0)/np.linalg.norm(Q1))
 assert eK<2e-14 and eQ==0
 lambdas=ratio*z['eigenvalues'];modes=z['modes'];a=K1@modes;b=(Q1@modes)*lambdas
 residual=float(max(np.linalg.norm(a-b,axis=0)/(np.linalg.norm(a,axis=0)+np.linalg.norm(b,axis=0))))
 assert residual<1e-6
 # Confirm actual weak stress direction, not just archived filename.
 side='web' if 'web_local' in file.name else 'lips'
 expected,props=core.stresses(nodes,t,My=1e6 if side=='web' else -1e6)
 stress_error=float(np.max(abs(s-expected)));assert stress_error<1e-8
 direct=None
 if file.name in ('t1.50_web_local.npz','t3.35_lips_distortional.npz'):
  d=1/np.sqrt(np.diag(K1));n=len(d);mu=eigh(d[:,None]*Q1*d,d[:,None]*K1*d,subset_by_index=[n-8,n-1],eigvals_only=True,driver='gvx')
  direct=float(max(abs((1/mu[::-1])/lambdas-1)));assert direct<1e-6
 rows.append(dict(file=file.name,source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),compressed_side=side,half_wave_mm=L,K_scaling_relative_error=eK,Q_scaling_relative_error=eQ,
  scaled_eigenpair_residual=residual,direct_relative_error=direct,stress_max_abs_difference_MPa=stress_error,
  scaled_lowest_Mcr_Nmm=float(lambdas[0]*1e6)))
# For the certified all-spectrum polynomial, every material coefficient is
# linear in E at fixed nu. Therefore K1-rQ*lambda=r(K0-Q*lambda), preserving
# positive definiteness for every wavelength; it is not a fresh continuum proof.
out=dict(passed=True,E_original_MPa=200000,E_AISI_MPa=203000,ratio=ratio,nu=.3,rows=rows,
 all_spectrum_bound_scaling='K1-r*lambda*Kg=r*(K0-lambda*Kg); positive definiteness and every wavelength interval are preserved at fixed nu and stress.',
 all_spectrum_proof_recomputed=False,prior_certificates_reused_with_identity_checks=True,
 scope='Same frozen discrete FSM. G78000 is separately used for global flexural-torsional formulas; plate G is implied by E/(2(1+nu)). No resistance scaling.')
(ROOT/'MATERIAL_SCALING.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(passed=True,weak_modes=len(rows),max_K_error=max(r['K_scaling_relative_error'] for r in rows),max_residual=max(r['scaled_eigenpair_residual'] for r in rows)),indent=2))
