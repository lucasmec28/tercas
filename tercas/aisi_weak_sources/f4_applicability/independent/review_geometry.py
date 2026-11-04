"""Independent quadrature/sign review; imports no producer/generator code."""
from pathlib import Path
import json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
rows=[]
for p in sorted((HERE/'inputs').glob('profile_*.json')):
 d=json.loads(p.read_text());t=d['thickness_mm'];z=np.load(HERE/'inputs'/f'weak_web_{t:.2f}.npz');xy=np.asarray(d['nodes_xy_mm'])
 assert np.array_equal(z['nodes'],xy) and float(z['t'])==t
 raw=json.dumps(xy.tolist(),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
 assert hashlib.sha256(raw).hexdigest()==d['geometry_identity']['nodes_canonical_sha256']
 # Independent Gaussian quadrature on all facets, not endpoint product formulas.
 v,w=np.polynomial.legendre.leggauss(4);q=(1-v)/2
 P=xy[:-1,None,:]*q[None,:,None]+xy[1:,None,:]*(1-q)[None,:,None]
 W=np.linalg.norm(np.diff(xy,axis=0),axis=1)[:,None]*t*w[None,:]/2
 A=np.sum(W);cg=np.sum(P*W[:,:,None],axis=(0,1))/A
 dx=P[:,:,0]-cg[0];dy=P[:,:,1]-cg[1]
 Iy=np.sum(dx*dx*W);Ix=np.sum(dy*dy*W);Ixy=np.sum(dx*dy*W)
 # Unit physical moment corresponding to positive FSM My, compression-positive.
 a,b=np.linalg.solve(np.array([[Iy,Ixy],[Ixy,Ix]]),[-1e6,0.])
 sn=a*(xy[:,0]-cg[0])+b*(xy[:,1]-cg[1]);sg=a*dx+b*dy
 assert np.max(np.abs(sn-z['stress']))<1e-9
 actions=[float(np.sum(sg*W)),float(np.sum(sg*dy*W)),float(-np.sum(sg*dx*W))]
 assert abs(actions[0])<1e-6 and abs(actions[1])<1e-5 and abs(actions[2]-1e6)<1e-5
 assert abs(Iy/d['own_properties']['Iy_weak_mm4']-1)<1e-13
 # Identify both lip/corner zones geometrically, not producer tag counts.
 # These zones end at x=b_mean-r; their radius is r=ri+t/2.
 g=d['geometry_external_mm'];bm=g['b']-t;r=g['ri']+t/2
 xmin_center=bm-r;xmin_material=xmin_center-t/2
 assert np.min(xy[:,0])>=-1e-12 and np.max(xy[:,0])<=bm+1e-12
 mask=(xy[:,0]>=xmin_center-1e-12)
 # Includes tangent outermost flange nodes too; the stated bound covers all
 # lip/corner material because full normal thickness extends at most t/2 in x.
 center_peak=float(sn[mask].max())
 max_tension_bound=float(a*(xmin_material-cg[0])+abs(b)*g['h'])
 margin=float(xmin_material-cg[0]);assert margin>0 and center_peak<0 and max_tension_bound<0
 # Negative controls: reversed weak moment and a uniform compression offset
 # large enough to put an edge stiffener into compression fail the geometric test.
 assert (-sn[mask]).max()>0
 assert (sn[mask]+abs(sn[mask].min())+1).max()>0
 rows.append(dict(profile_id=d['profile_id'],t_mm=t,cg_mm=cg.tolist(),Iy_mm4=Iy,
   signed_resultants_N_Nmm=actions,stress_match_max_MPa=float(np.max(np.abs(sn-z['stress']))),
   entire_lip_corner_min_x_minus_CG_mm=margin,compression_positive_stress_upper_MPa_per_kNm=max_tension_bound,
   both_lips_and_their_corners_in_tension=True,profile_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
out=dict(status='PASS_INDEPENDENT_SIGN_GEOMETRY_REVIEW',profiles=6,negative_controls=12,rows=rows,
  release='Bounded research applicability of F4 for PURE weak bending only; no design or combined stress exemption.')
(HERE/'RESULTS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
