"""Isolated AISI2024 H4 research comparator, never a whole-member release.

Strong bending, six own Ue100 sections, holes absent. F2/F3/F4 conservative
algebraic floors, G8.1 first-yield option, no factor1.25 benefit. Numerical
elastic inputs remain subject to their original finite-strip qualification.
"""
from pathlib import Path
import copy,json,math,hashlib
import numpy as np
from .vendor.section import load_profile
ROOT=Path(__file__).resolve().parent
E=203000.;G=78000.;NU=.3;FY=250.;PHI=.90


def positive(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError(name+' must be positive finite')
    return float(value)


def flexural_floor(My,Mcre,Mcrl,Mcrd,beta=1.):
    My=positive(My,'My');Mcre=positive(Mcre,'Mcre');Mcrl=positive(Mcrl,'Mcrl');Mcrd=positive(Mcrd,'Mcrd')
    if beta!=1.:raise ValueError('Only symmetric strong bending, beta=1, qualified here')
    # sqrt(My/Mcrl)<=5 bounds REAL sqrt(min(Mne,My)/Mcrl), not only floor.
    lambda_l_sufficient=math.sqrt(My/Mcrl);lambda_d=math.sqrt(My/Mcrd)
    if lambda_l_sufficient>5 or lambda_d>5:raise ValueError('AISI DSM slenderness domain not established')
    ne=My*(1-.25*My/Mcre) if Mcre>.5*My else Mcre
    nl=ne/(1+.55*beta*ne/Mcrl)
    nd=My/(1+.60*beta*My/Mcrd)
    nominal=min(ne,nl,nd)
    return dict(My_Nmm=My,Mcre_Nmm=Mcre,Mcrl_Nmm=Mcrl,Mcrd_Nmm=Mcrd,
        Mne_floor_Nmm=ne,Mnl_floor_Nmm=nl,Mnd_floor_Nmm=nd,Mn_floor_Nmm=nominal,
        Ma_floor_Nmm=PHI*nominal,phi_b=PHI,beta=beta,
        lambda_local_real_sufficient_upper=lambda_l_sufficient,lambda_distortional=lambda_d,
        governing_floor=[key for key,x in [('F2',ne),('F3',nl),('F4',nd)] if x==nominal],
        floor_scope='Algebraic lower bound of AISI2024 F2.2/F3.2/F4 at fixed eligible elastic inputs, Mp>=My and alpha_s>=0. Not the literal exact AISI strength or universal physical lower bound.')


def full_DSM(My,Mp,Mcre,Mcrl,Mcrd,alpha_l=1.,alpha_d=1.,beta=1.):
    """Literal no-hole formulas for testing floor; not member applicability gate."""
    if Mp<My or not 0<=alpha_l<=1 or not 0<=alpha_d<=1:raise ValueError('invalid proof parameters')
    ne=Mp*(1-.25*Mp/Mcre) if Mcre>.5*Mp else Mcre
    bar=min(ne,My);my3=Mp-(Mp-My)/9
    nl=min((Mp/My)*bar*(1+.10*alpha_l*bar/Mcrl)/(1+.55*beta*bar/Mcrl),my3)
    nd=min(Mp*(1+.07*alpha_d*My/Mcrd)/(1+.60*beta*My/Mcrd),my3)
    return dict(Mne=ne,Mnl=nl,Mnd=nd,Mn=min(ne,nl,nd),My3=my3)


def uniform_torsion(s,L,m,J,Cw):
    S=G*J;D=E*Cw;k=math.sqrt(S/D);c=math.cosh(k*(s-L/2))/math.cosh(k*L/2)
    return dict(phi_rad=m/S*(s*(L-s)/2+(c-1)/k**2),B_Nmm2=m/k**2*(1-c))


def dimensional_gate(t):
    b=50-4*t;h=100-4*t;d=17-2*t
    checks=dict(web_bending_h_t=h/t<=300,edge_stiffened_b_t=b/t<=160,
        unstiffened_d_t=d/t<=60,R_t=1<=20,do_bo=17/50<=.7,
        intermediate_stiffeners_absent=True,fy_max=FY<=655)
    assert all(checks.values())
    return dict(standard='AISI2024 B4.1 TableB4.1-1 DSM column',h_t=h/t,b_t=b/t,d_t=d/t,
        R_t=1.,do_bo=17/50,Fy_MPa=FY,checks=checks,passed=True,
        scope='Dimension/material-range gates only; not certification of actual product, A3 ductility, holes or delivered thickness')


def assess(row,L,load_factor=1.):
    L=positive(L,'L');factor=positive(load_factor,'factor')
    if not 3000<=L<=6000:raise ValueError('Span outside original reference domain')
    t=row['thickness_mm'];sec=load_profile(ROOT/'inputs'/f'ue100x50x17_t{t:.2f}.json');p=sec['properties']
    if row['nodes_sha256']!=sec['nodes_sha256']:raise ValueError('geometry identity mismatch')
    if row['material']!={'E_MPa':200000.,'nu':.3,'G_MPa':200000/2.6}:raise ValueError('unexpected source material')
    W=row['exterior_moduli']['Wx_first_yield_mm3'];My=FY*W
    # AISI App2 symmetric-axis expression, Cb=1; SAME reference geometry.
    Pey=math.pi**2*E*p['Iy_weak_mm4']/L**2
    torsional=G*p['J_mm4']+math.pi**2*E*p['Cw_mm6']/L**2
    Mcre=math.sqrt(Pey*torsional)
    ratio=E/row['material']['E_MPa']
    Mcrl=ratio*row['modal_criticals']['strong_local']['value_Nmm'];Mcrd=ratio*row['modal_criticals']['strong_distortional']['value_Nmm']
    cap=flexural_floor(My,Mcre,Mcrl,Mcrd)
    # By is the literal G8.1 option. It is NOT asserted a physical lower bound.
    omega_max=max(map(abs,sec['omega_nodes_mm2']));By=FY*p['Cw_mm6']/omega_max;Ba=PHI*By
    cg=p['centroid_xy_mm'];sc=p['shear_center_xy_mm'];ex=cg[0]-sc[0];ey=cg[1]-sc[1]
    if abs(ey)>1e-8:raise ValueError('Nonzero vertical load height not covered')
    mass=p['A_mm2']*.00785;q=factor*mass*9.80665/1000;m=-q*ex
    mid=uniform_torsion(L/2,L,m,p['J_mm4'],p['Cw_mm6']);Mx=q*L**2/8
    terms=dict(Mx=Mx/cap['Ma_floor_Nmm'],My=0.,B=abs(mid['B_Nmm2'])/Ba);eta=sum(terms.values())
    # In this uniform case both |M| and |B| have their maximum at L/2.
    # Thus the same-section sum, not an arbitrary sum of remote extrema, is exact.
    return dict(profile_id=row['profile_id'],thickness_mm=t,length_mm=L,material=dict(E_MPa=E,G_MPa=G,nu=NU,Fy_MPa=FY),
        dimensional_gate=dimensional_gate(t),flexure=cap,bimoment=dict(By_Nmm2=By,Ba_Nmm2=Ba,omega_max_mm2=omega_max,option='AISI2024 G8.1-1/2, no inelastic Bp option'),
        declared_uniform_force_N_mm=[0.,-q],application_xy_mm=cg,CG_minus_SC_mm=[ex,ey],
        load_factor=factor,load_case_kind='PP isolated reference at coefficient1, or a scaled mathematical control; not an AISI design combination',
        required_midspan=dict(Mx_magnitude_Nmm=Mx,My_Nmm=0.,B_Nmm2=mid['B_Nmm2'],phi_rad=mid['phi_rad']),
        H4_terms_using_flexural_floor=terms,H4_ratio_upper=eta,H4_threshold=1.,
        H4_algebraic_sufficient_condition=eta<=1,
        H4_sufficiency_is_conditional_on_remaining_applicability=True,
        critical_location_mm=L/2,Cb=1.,support='Ideal forks, warping free, flexure simply supported, no sheeting or intermediate brace',
        load_height_term_zero_in_initial_configuration=True,
        analysis_scope='Linear Vlasov; no physical threshold for small rotation is assigned. G8.2 shear, C1 applicability, serviceability and load introduction remain open.',
        pending=['AISI C1 applicability of demands for intended actual loads','Representativeness/qualification of elastic critical inputs for intended member','Torsion shear and relevant interactions, G8.2 reserved','Actual material/product requirements A3 and B7','Serviceability and local introduction of loads'],
        NBR_design_check=False,whole_member_approved=False,physical_design_approved=False)


def run():
    for pin in json.loads((ROOT/'SOURCE_PINS.json').read_text()):assert hashlib.sha256((ROOT/pin['copy']).read_bytes()).hexdigest()==pin['sha256']
    scaling=json.loads((ROOT/'MATERIAL_SCALING.json').read_text());assert scaling['status'].startswith('PASS')
    rows=json.loads((ROOT/'inputs/elastic_inputs.json').read_text())['profiles'];out=[assess(row,L,factor) for row in rows for L in [3000.,4000.,5000.,6000.] for factor in [1.,.01]]
    result=dict(schema='AISI2024_strong_bending_bimoment_conservative_research_v1',profiles=6,cases=len(out),
        method='AISI2024 F2.2/F3.2/F4 algebraic flexural lower bounds + literal G8.1 By option + H4 threshold1',
        source_editions_mixed=False,NBR_capacities_used=False,section_effective_calculation_needed=False,
        steel_constants_source='AISI2024 Appendix2 section2.3.1',records=out,whole_member_approved=False)
    (ROOT/'RESULTS.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    base=next(x for x in out if x['thickness_mm']==1.5 and x['length_mm']==4000 and x['load_factor']==1)
    summary=dict(cases=len(out),PP_reference_H4_range=[min(x['H4_ratio_upper'] for x in out if x['load_factor']==1),max(x['H4_ratio_upper'] for x in out if x['load_factor']==1)],
        baseline_t150_L4000=base,whole_member_approved=False)
    (ROOT/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
