"""Independent read-only matrix replay. Writes only alongside this script."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from vendor import fsm_core as core
records=[]
for sidefile in ['t1.50_web_local.npz','t1.50_lips_local.npz','t1.50_lips_distortional.npz','t3.35_web_local.npz','t3.35_lips_local.npz','t3.35_lips_distortional.npz']:
 p=ROOT/'modes'/sidefile;z=np.load(p)
 K,Q=core.matrices(z['nodes'],float(z['t']),float(z['L']),z['stress'],203000.,.3)
 V=z['modes'];e=z['eigenvalues']*203/200
 R=K@V-(Q@V)*e
 relative=np.linalg.norm(R,axis=0)/(np.linalg.norm(K@V,axis=0)+np.linalg.norm((Q@V)*e,axis=0))
 assert max(relative)<1e-6
 K0,Q0=core.matrices(z['nodes'],float(z['t']),float(z['L']),z['stress'],200000.,.3)
 err=np.linalg.norm(K-1.015*K0)/np.linalg.norm(K)
 assert err<2e-14;assert np.array_equal(Q,Q0)
 records.append(dict(file=sidefile,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),max_eigenpair_relative_residual=float(max(relative)),stiffness_scaling_relative_error=float(err)))
out=dict(passed=True,rows=records,scope='Six extreme-thickness specimens; every stored eigenpair in each file; same discrete model only.')
(Path(__file__).resolve().parent/'MATERIAL_INDEPENDENT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
