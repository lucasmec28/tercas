from pathlib import Path
import sys,json,math,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import aisi_candidate as c
from vendor.section import load_profile
from vendor.fsm_core import matrices
rng=np.random.default_rng(4112026)
# Independent formula identity / inequality tests, no call to author's full_DSM.
worst=0
for i in range(20000):
 Y=10**rng.uniform(2,9); P=Y*rng.uniform(1,3); Cr=Y*10**rng.uniform(-3,4);Cl=Y*10**rng.uniform(-1.39,3);Cd=Y*10**rng.uniform(-1.39,3)
 a,b=rng.integers(0,2,2); x=min(Cr,P-P*P/(4*Cr)) if P<2*Cr else Cr
 bar=min(x,Y); y3=(8*P+Y)/9
 full=min(x, (P/Y)*bar*(1+.1*a*bar/Cl)/(1+.55*bar/Cl), y3, P*(1+.07*b*Y/Cd)/(1+.60*Y/Cd))
 floor=c.flexural_floor(Y,Cr,Cl,Cd)['Mn_floor_Nmm'];assert floor<=full*(1+1e-12)
 worst=max(worst,floor/full)
rows=json.loads((ROOT/'RESULTS.json').read_text())['records']; outputs=[];errors=[]
for r in rows:
 t=r['thickness_mm'];L=r['length_mm'];sec=load_profile(ROOT/'inputs'/f'ue100x50x17_t{t:.2f}.json');p=sec['properties'];data=json.loads((ROOT/'inputs'/f'ue100x50x17_t{t:.2f}.json').read_text());pts=np.array(data['nodes_xy_mm'])
 assert abs((pts[:,1].max()+pts[:,1].min())/2-p['centroid_xy_mm'][1])<1e-9
 geom=data['geometry_external_mm'];ri=geom['ri'];tt=geom['t'];assert ri==tt==t
 expected=[(geom['h']-2*(ri+t))/t,(geom['b']-2*(ri+t))/t,(geom['lip']-(ri+t))/t]
 gate=r['dimensional_gate'];assert np.allclose(expected,[gate['h_t'],gate['b_t'],gate['d_t']],rtol=0,atol=1e-12)
 k=math.sqrt(78000*p['J_mm4']/(203000*p['Cw_mm6']));q=abs(r['declared_uniform_force_N_mm'][1]);m=-q*r['CG_minus_SC_mm'][0]
 Bmid=m/k**2*(1-1/math.cosh(k*L/2));Mmid=q*L**2/8
 Ba=.9*250*p['Cw_mm6']/max(abs(np.array(sec['omega_nodes_mm2'])))
 F=r['flexure'];Y=F['My_Nmm'];Cr=math.pi/L*math.sqrt(203000*p['Iy_weak_mm4']*(78000*p['J_mm4']+math.pi**2*203000*p['Cw_mm6']/L**2));assert abs(Cr/F['Mcre_Nmm']-1)<1e-12
 floor=c.flexural_floor(Y,Cr,F['Mcrl_Nmm'],F['Mcrd_Nmm'])['Ma_floor_Nmm'];ratio=Mmid/floor+abs(Bmid)/Ba;assert abs(ratio/r['H4_ratio_upper']-1)<1e-12
 # Grid independently proves claimed location for this constant capacity uniform case.
 xx=np.linspace(0,L,401);bb=m/k**2*(1-np.cosh(k*(xx-L/2))/np.cosh(k*L/2));mm=q*xx*(L-xx)/2;eta=mm/floor+abs(bb)/Ba;assert abs(max(eta)/ratio-1)<1e-12
 # Exact mechanism split at support: TSv=GJ*phi', total=mL/2.
 pure_support_fraction=1-2*math.tanh(k*L/2)/(k*L)
 outputs.append(dict(t=t,L=L,factor=r['load_factor'],kL=k*L,commentary_pure_torsion_negligible=k*L<.5,SV_support_torque_fraction=pure_support_fraction))
# One independent material audit, stored intermediate matrices never altered.
z=np.load(ROOT/'modes/t2.25_strong_local.npz');K0,Q0=matrices(z['nodes'],float(z['t']),float(z['L']),z['stress'],200000.,.3);K1,Q1=matrices(z['nodes'],float(z['t']),float(z['L']),z['stress'],203000.,.3)
eK=np.linalg.norm(K1-1.015*K0)/np.linalg.norm(K1);eQ=np.linalg.norm(Q1-Q0);assert eK<2e-14 and eQ==0
for name,args in [('local_domain',(1,1,.001,1)),('dist_domain',(1,1,1,.001)),('beta',(1,1,1,1,2))]:
 try:c.flexural_floor(*args)
 except ValueError:errors.append(name)
 else:raise AssertionError(name)
report=dict(status='PASS conditional algebra and frozen numerical cases; not whole member approval',author_sha256=hashlib.sha256((ROOT/'aisi_candidate.py').read_bytes()).hexdigest(),random_floor_tests=20000,max_floor_to_exact_ratio=worst,records_checked=len(rows),material_K_relative_error=eK,material_Kg_error=eQ,rejected_invalid_domains=errors,kL_range=[min(x['kL'] for x in outputs),max(x['kL'] for x in outputs)],pure_negligible_cases=sum(x['commentary_pure_torsion_negligible'] for x in outputs),SV_support_fraction_range=[min(x['SV_support_torque_fraction'] for x in outputs),max(x['SV_support_torque_fraction'] for x in outputs)],mechanism_rows=outputs)
(ROOT/'independent_review/TEST_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='mechanism_rows'},indent=2))
