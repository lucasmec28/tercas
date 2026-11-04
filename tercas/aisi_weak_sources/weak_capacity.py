"""AISI2024 weak-axis reference floors. Research, not whole-member approval.

No NBR resistance is imported. Named compression side is the primary API;
legacy FSM and tensile-positive Vlasov moment signs are explicitly different.
"""
from pathlib import Path
import hashlib,json,math
from fractions import Fraction
ROOT=Path(__file__).resolve().parent
E,G,NU,FY,PHI=203000.,78000.,.3,250.,.90
THICKNESSES=(1.5,2.,2.25,2.65,3.,3.35)
SIDES=('web','lips')


def number(x,name,positive=False):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or (positive and x<=0):
        raise ValueError(name+' must be a finite '+('positive ' if positive else '')+'real')
    return float(x)


def verify_sources():
    for pin in json.loads((ROOT/'SOURCE_PINS.json').read_text()):
        if hashlib.sha256((ROOT/pin['copy']).read_bytes()).hexdigest()!=pin['sha256']:
            raise ValueError('Source identity changed: '+pin['copy'])
    proof=json.loads((ROOT/'MATERIAL_SCALING.json').read_text())
    if not proof['passed'] or len(proof['rows'])!=18:raise ValueError('Weak material qualification missing')
    for record in proof['rows']:
        if hashlib.sha256((ROOT/'modes'/record['file']).read_bytes()).hexdigest()!=record['source_sha256']:
            raise ValueError('Material qualification source mismatch')


def compression_side_from_vlasov_my(My):
    """Only sigma_tension=-My*(x-CGx)/Iy, own x increasing web->lips.

    Positive My puts the web in tension and lips in compression. Zero has no
    weak compression side and does not request any capacity.
    """
    m=number(My,'My')
    return 'lips' if m>0 else 'web' if m<0 else None


def compression_side_from_fsm_my(My):
    """Only sigma_compression=-My*(x-CGx)/Iy in the frozen FSM."""
    m=number(My,'My')
    return 'web' if m>0 else 'lips' if m<0 else None


def first_yield_and_beta(row,side):
    if side not in SIDES:raise ValueError('Physical compressed side must be web or lips')
    p=row['properties'];w=row['exterior_moduli'];cx=p['centroid_xy_mm'][0]
    xmin,xmax=w['extents_mm']['x'];d=xmax-xmin
    yw=cx-xmin;yl=xmax-cx
    if not 0<yw<d or not 0<yl<d:raise ValueError('Centroid outside section')
    Wfirst=p['Iy_weak_mm4']/max(yw,yl);yc=yw if side=='web' else yl
    if not math.isclose(Wfirst,w['Wy_first_yield_mm3'],rel_tol=2e-12):raise ValueError('First-yield modulus mismatch')
    return dict(My_Nmm=FY*Wfirst,Sf_first_yield_mm3=Wfirst,Sfc_mm3=p['Iy_weak_mm4']/yc,
        depth_perpendicular_to_bending_axis_mm=d,yc_mm=yc,beta_raw=2*yc/d,beta=max(.4,2*yc/d),
        first_yield_fiber='lips' if yl>=yw else 'web',
        first_yield_state='compression' if (yl>=yw)==(side=='lips') else 'tension')


def global_weak(row,L,side):
    """App2 2.3.1.2.2-1, Cb=1, Kx=Kt=1, unbraced length L.

    This is a pure weak-axis reference with fork ends and free warping. It is
    not a critical multiplier for a real biaxial/torsion/load-height problem.
    """
    L=number(L,'L',True)
    if side not in SIDES:raise ValueError('Physical compressed side must be web or lips')
    p=row['properties'];cx=p['centroid_xy_mm'][0];sc=p['shear_center_xy_mm'][0]
    # AISI x0 is SC minus CG. The historical registry's x0 is its negative.
    x0=sc-cx;j=p['beta_mm5']/(2*p['Iy_weak_mm4'])-x0
    if not math.isclose(j,p['j_mm'],rel_tol=2e-12):raise ValueError('j convention mismatch')
    side_x=(-1 if side=='web' else 1)
    if x0==0:raise ValueError('This own-channel branch requires an offset shear center')
    Cs=1 if side_x*x0>0 else -1
    Pex=math.pi**2*E*p['Ix_strong_mm4']/L**2
    D=G*p['J_mm4']+math.pi**2*E*p['Cw_mm6']/L**2
    root=math.sqrt(j*j+D/Pex)
    # Rationalized negative branch prevents catastrophic subtraction.
    Mcre=Pex*(root+abs(j)) if Cs==1 else D/(root+abs(j))
    return dict(Mcre_Nmm=Mcre,Pex_N=Pex,Pt_N=D/p['r0_mm']**2,
        torsion_warping_stiffness_Nmm2=D,j_AISI_mm=j,abs_j_mm=abs(j),x0_AISI_mm=x0,
        x0_registry_mm=p['x0_mm'],Cs=Cs,Cb=1.,clause='AISI2024 A2 2.3.1.2.2-1',
        coordinates='Own x increases from web to lips; Cs follows physical shear-center side, not moment-sign label')


def local_global_floor(My,Mcre,Mcrl,beta):
    """F2/F3 partial result only; does not dismiss F4."""
    My=number(My,'My',True);Mcre=number(Mcre,'Mcre',True);Mcrl=number(Mcrl,'Mcrl',True);beta=number(beta,'beta',True)
    if beta<.4 or beta>=2:raise ValueError('beta outside nondegenerate cross-section domain')
    upper=math.sqrt(My/Mcrl)
    if upper>5:raise ValueError('AISI local DSM slenderness domain not established')
    P=My*(1-.25*My/Mcre) if Mcre>.5*My else Mcre
    local=P/(1+.55*beta*P/Mcrl)
    return dict(Mne_floor_Nmm=P,Mnl_floor_Nmm=local,Ma_F2_F3_only_Nmm=PHI*min(P,local),
        lambda_local_true_sufficient_upper=upper,F4_not_resolved_by_this_partial_result=True)


def flexural_floor(My,Mcre,Mcrl,Mcrd,beta):
    """Algebraic floor at eligible critical values, not literal AISI equation.

    Also usable as a conditional discrete diagnostic when Mcrd is a proven
    lower bound for ALL admissible modes. This scalar function grants no
    modal, boundary, continuum or member eligibility.
    """
    My=number(My,'My',True);Mcre=number(Mcre,'Mcre',True)
    Mcrl=number(Mcrl,'Mcrl',True);Mcrd=number(Mcrd,'Mcrd',True)
    beta=number(beta,'beta',True)
    if beta<.4 or beta>=2:raise ValueError('beta outside nondegenerate cross-section domain')
    ll=math.sqrt(My/Mcrl);ld=math.sqrt(My/Mcrd)
    if ll>5 or ld>5:raise ValueError('AISI DSM slenderness domain not established')
    P=My*(1-.25*My/Mcre) if Mcre>.5*My else Mcre
    local=P/(1+.55*beta*P/Mcrl)
    dist=My/(1+.60*beta*My/Mcrd)
    Mn=min(P,local,dist)
    return dict(Mne_floor_Nmm=P,Mnl_floor_Nmm=local,Mnd_floor_Nmm=dist,Mn_floor_Nmm=Mn,
        Ma_formula_floor_Nmm=PHI*Mn,phi_b=PHI,beta=beta,
        lambda_local_true_sufficient_upper=ll,lambda_dist_true_upper=ld,
        branches_controlling_floor=[k for k,v in [('F2',P),('F3',local),('F4',dist)] if v==Mn],
        literal_AISI_strength=False,physical_lower_bound_proven=False)


def full_DSM(My,Mp,Mcre,Mcrl,Mcrd,beta,alpha_l,alpha_d):
    """Literal no-hole algebra for independent controls, not a member release."""
    vals=[number(v,n,True) for v,n in [(My,'My'),(Mp,'Mp'),(Mcre,'Mcre'),(Mcrl,'Mcrl'),(Mcrd,'Mcrd'),(beta,'beta')]]
    My,Mp,Mcre,Mcrl,Mcrd,beta=vals
    for v in [alpha_l,alpha_d]:
        number(v,'alpha')
        if not 0<=v<=1:raise ValueError('alpha must lie in [0,1]')
    if Mp<My:raise ValueError('Mp must be >= My')
    if not .4<=beta<2:raise ValueError('beta outside section domain')
    ne=Mp*(1-.25*Mp/Mcre) if Mcre>.5*Mp else Mcre
    bar=min(ne,My);limit=Mp-(Mp-My)/9
    if math.sqrt(bar/Mcrl)>5 or math.sqrt(My/Mcrd)>5:raise ValueError('Literal DSM slenderness domain exceeded')
    nl=min((Mp/My)*bar*(1+.1*alpha_l*bar/Mcrl)/(1+.55*beta*bar/Mcrl),limit)
    nd=min(Mp*(1+.07*alpha_d*My/Mcrd)/(1+.6*beta*My/Mcrd),limit)
    return dict(Mne=ne,Mnl=nl,Mnd=nd,Mn=min(ne,nl,nd),My3=limit)


def dimensional_gate(t):
    h,b,d=100-4*t,50-4*t,17-2*t
    checks=dict(stiffened_web_uniform_compression=h/t<=500,stiffened_element_bending=h/t<=300,
        edge_stiffened_element=b/t<=160,unstiffened_lip=d/t<=60,inside_R_t=1<=20,
        lip_ratio=17/50<=.7,no_intermediate_stiffeners=True,Fy=FY<=655)
    if not all(checks.values()):raise ValueError('B4 dimensional gate failed')
    return dict(passed=True,checks=checks,h_t=h/t,b_t=b/t,d_t=d/t,
        scope='B4.1 numerical geometry/material-range only; A3 material and B7 delivered thickness remain unverified')


def _row(t):
    t=number(t,'thickness',True)
    if t not in THICKNESSES:raise ValueError('Only six own identities; no interpolation or 1.20-mm inheritance')
    pins={p['copy']:p['sha256'] for p in json.loads((ROOT/'SOURCE_PINS.json').read_text())}
    inp=ROOT/'inputs/elastic_inputs.json'
    if hashlib.sha256(inp.read_bytes()).hexdigest()!=pins['inputs/elastic_inputs.json']:raise ValueError('Elastic input digest mismatch')
    profile_name=f'inputs/ue100x50x17_t{t:.2f}.json'
    if hashlib.sha256((ROOT/profile_name).read_bytes()).hexdigest()!=pins[profile_name]:raise ValueError('Profile digest mismatch')
    r=next(r for r in json.loads(inp.read_text())['profiles'] if r['thickness_mm']==t)
    if r['material']!={'E_MPa':200000.,'nu':.3,'G_MPa':200000/2.6}:raise ValueError('Unexpected source material')
    p=json.loads((ROOT/'inputs'/f'ue100x50x17_t{t:.2f}.json').read_text())
    digest=hashlib.sha256(json.dumps(p['nodes_xy_mm'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    if digest!=r['nodes_sha256'] or r['profile_id']!=p['profile_id']:raise ValueError('Geometry identity mismatch')
    return r


def f4_pure_web_applicability(row,*,side='web',N_N=0.,Mx_Nmm=0.,B_Nmm2=0.,V_N=0.,T_Nmm=0.,uniform_pure_weak=True):
    """Bounded applicability interpretation, not a mixed-field waiver.

    This gate concerns the PURE component used to define its denominator.
    Do not pass actual combined actions here to bypass an interaction check.
    """
    if side!='web' or uniform_pure_weak is not True:raise ValueError('F4 non-applicability requires pure weak web compression')
    for name,value in [('N',N_N),('Mx',Mx_Nmm),('B',B_Nmm2),('V',V_N),('T',T_Nmm)]:
        if number(value,name)!=0:raise ValueError('Mixed action not covered by pure-component F4 gate')
    base=ROOT/'f4_applicability/independent'
    expected='5d48a42b3a9b9bc7717a53574b5409ab22c81902154b9075ad3f787aa08ef248'
    if hashlib.sha256((base/'MANIFEST.json').read_bytes()).hexdigest()!=expected:raise ValueError('F4 review manifest mismatch')
    for name,digest in json.loads((base/'MANIFEST.json').read_text()).items():
        if hashlib.sha256((base/name).read_bytes()).hexdigest()!=digest:raise ValueError('F4 independent source changed')
    result=json.loads((base/'RESULTS.json').read_text())
    if result['status']!='PASS_INDEPENDENT_SIGN_GEOMETRY_REVIEW' or result['profiles']!=6 or result['negative_controls']!=12:
        raise ValueError('Independent F4 applicability review not complete')
    matches=[r for r in result['rows'] if r['profile_id']==row['profile_id']]
    if len(matches)!=1:raise ValueError('Unreviewed F4 profile')
    evidence=matches[0];t=row['thickness_mm'];profile_path=ROOT/'inputs'/f'ue100x50x17_t{t:.2f}.json'
    if hashlib.sha256(profile_path.read_bytes()).hexdigest()!=evidence['profile_sha256']:raise ValueError('F4 geometry mismatch')
    profile=json.loads(profile_path.read_text());g=profile['geometry_external_mm']
    if row['nodes_sha256']!=profile['geometry_identity']['nodes_canonical_sha256']:raise ValueError('F4 node identity mismatch')
    if g!={'h':100.0,'b':50.0,'lip':17.0,'t':t,'ri':t}:raise ValueError('F4 topology/dimensions changed')
    # Conservative lower x of entire lip+corner material, including t/2.
    clearance=(g['b']-t)-(g['ri']+t/2)-t/2-row['properties']['centroid_xy_mm'][0]
    if (not evidence['both_lips_and_their_corners_in_tension'] or clearance<=0 or
        not math.isclose(clearance,evidence['entire_lip_corner_min_x_minus_CG_mm'],rel_tol=2e-12) or
        evidence['compression_positive_stress_upper_MPa_per_kNm']>=0):
        raise ValueError('Tension-only edge-stiffener condition not demonstrated')
    return dict(classification='F4_NOT_APPLICABLE_PURE_WEAK_WEB',Mcrd_Nmm=None,Mcrd_is_infinite=False,
        independent_manifest_sha256=expected,lip_corner_clearance_lower_mm=clearance,
        source='AISI RP21-01 Example I item4 p10/PDF15, interpreted with AISI2024 F1/F4 scope',
        normative_universal_exclusion_clause=False,pure_component_only=True,mixed_field_waiver=False,
        F2_and_F3_still_required=True,fully_braced_RP21_assumption_transferred=False,
        physical_continuum_absence_proven=False)


def reference_capacity(t,L,side,*,support='ideal_forks_free_warping',loading='pure_end_moments',N_N=0,holes=False,Mx_Nmm=0,B_Nmm2=0,V_N=0,T_Nmm=0):
    """Only this named ideal reference. Real biaxial/torsion calls rejected.

    Web-compression uses the independently reviewed pure-component F4
    non-applicability gate. It is never a waiver for an actual combined field.
    """
    verify_sources()
    L=number(L,'L',True);number(N_N,'N')
    if not 3000<=L<=6000:raise ValueError('Length outside original qualified reference interval')
    if side not in SIDES:raise ValueError('Compression side required')
    if support!='ideal_forks_free_warping' or loading!='pure_end_moments' or N_N!=0 or holes is not False:
        raise ValueError('Changed load, support, axial force or holes requires new applicability qualification')
    for name,value in [('Mx',Mx_Nmm),('B',B_Nmm2),('V',V_N),('T',T_Nmm)]:
        if number(value,name)!=0:raise ValueError('Pure component definition only; combined action not accepted')
    r=_row(t);yield_data=first_yield_and_beta(r,side);g=global_weak(r,L,side);cr=r['modal_criticals']
    Mcrl=E/200000*cr[side+'_local']['value_Nmm']
    Mcrd=E/200000*cr['lips_distortional']['value_Nmm'] if side=='lips' else None
    partial=local_global_floor(yield_data['My_Nmm'],g['Mcre_Nmm'],Mcrl,yield_data['beta'])
    f4gate=f4_pure_web_applicability(r) if side=='web' else dict(classification='F4_APPLICABLE_LIPS_COMPRESSED',pure_component_only=True,mixed_field_waiver=False)
    if Mcrd:
        floor=flexural_floor(yield_data['My_Nmm'],g['Mcre_Nmm'],Mcrl,Mcrd,yield_data['beta'])
    else:
        P=partial['Mne_floor_Nmm'];local=partial['Mnl_floor_Nmm'];Mn=min(P,local)
        floor=dict(Mne_floor_Nmm=P,Mnl_floor_Nmm=local,Mnd_floor_Nmm=None,Mn_floor_Nmm=Mn,
            Ma_formula_floor_Nmm=PHI*Mn,phi_b=PHI,beta=yield_data['beta'],
            lambda_local_true_sufficient_upper=partial['lambda_local_true_sufficient_upper'],lambda_dist_true_upper=None,
            branches_controlling_floor=[k for k,v in [('F2',P),('F3',local)] if v==Mn],
            literal_AISI_strength=False,physical_lower_bound_proven=False,F4_non_applicability=f4gate['classification'])
    return dict(profile_id=r['profile_id'],thickness_mm=t,L_mm=L,compressed_side=side,
        material=dict(E_MPa=E,G_MPa=G,nu_plate=NU,Fy_MPa=FY),yield_and_asymmetry=yield_data,
        global_elastic=g,Mcrl_Nmm=Mcrl,Mcrd_identified_Nmm=Mcrd,
        Mcrd_kind='own_conventional_distortional_valley' if Mcrd else 'not_applicable_pure_weak_web',
        F4_applicability=f4gate,partial_F2_F3=partial,
        dimensional_gate=dimensional_gate(t),reference_formula_floor=floor,
        Ma_reference_floor_Nmm=floor['Ma_formula_floor_Nmm'],
        status='CONDITIONAL_IDEAL_REFERENCE_FLOOR',
        H4_for_actual_member_eligible=False,whole_member_approved=False,NBR_capacities_used=False,
        modal_scope='Inherited 209-node conventional signature minima, not exact eigenvalues for each finite span or all boundary conditions',
        pending=['Actual product/material A3 and B7','Demand C1 and actual load/support correspondence',
            'Combined Mx+My+B/Wagner/shear and their stability domain',
            'No transfer to external girts or changed end bimoment conditions',
            'F4 pure-web component interpretation is not a combined-field D waiver'])


def discrete_web_diagnostic(t,L,*,accept_discrete_only=False):
    if accept_discrete_only is not True:raise ValueError('Explicit acknowledgement of discrete-only diagnostic required')
    strict=reference_capacity(t,L,'web');r=_row(t);b=r['web_all_spectrum_bound']
    certificate_path=ROOT/b['bundle_certificate']
    if hashlib.sha256(certificate_path.read_bytes()).hexdigest()!=b['bound_source']['sha256']:raise ValueError('Certificate digest mismatch')
    c=json.loads(certificate_path.read_text())
    if not c['passed'] or not c['coverage']['all_positive_integer_harmonics'] or not c['coverage']['continuous_p_to_infinity']:
        raise ValueError('Full spectral certificate is incomplete')
    if c['nodes_sha256']!=r['nodes_sha256'] or c['material']!=r['material'] or c['lower_bound_Nmm']!=b['lower_bound_Nmm']:
        raise ValueError('Certificate identity mismatch')
    if not c['model']['span_domain_mm'][0]<=L<=c['model']['span_domain_mm'][1]:raise ValueError('Certificate span domain')
    exact_Q=Fraction(203,200)*c['lower_bound_Nmm'];Q=float(exact_Q)
    while Fraction(Q)>exact_Q:Q=math.nextafter(Q,-math.inf)
    y=strict['yield_and_asymmetry']
    f=flexural_floor(y['My_Nmm'],strict['global_elastic']['Mcre_Nmm'],strict['Mcrl_Nmm'],Q,y['beta'])
    return dict(profile_id=r['profile_id'],thickness_mm=t,L_mm=L,compressed_side='web',
        Mcrd_identified_Nmm=None,spectral_lower_bound_AISI_E_Nmm=Q,
        scaled_bound_exact_rational=str(exact_Q),scaled_bound_float_not_above_exact=Fraction(Q)<=exact_Q,
        scalar_conditional_floor=f,status='DISCRETE_DIAGNOSTIC_ONLY',capacity_for_H4_Nmm=None,
        ordering_statement='Within the same discrete admissible space, every critical including any D critical exceeds Q; floor decreases when Q replaces that critical.',
        unresolved=['Continuum adequacy/convergence of the certified lower bound','Identification or equivalent justified finite-member D domain',
            'Nonuniform/biaxial/Wagner stress or changed support has no bound here'],
        physical_continuum_proof=False,distortional_exemption=False,whole_member_approved=False)


def run():
    verify_sources()
    cases=[reference_capacity(t,L,s) for t in THICKNESSES for L in [3000.,4000.,5000.,6000.] for s in SIDES]
    diagnostics=[discrete_web_diagnostic(t,L,accept_discrete_only=True) for t in THICKNESSES for L in [3000.,4000.,5000.,6000.]]
    out=dict(schema='AISI2024_weak_reference_floor_v1',references=cases,web_discrete_diagnostics=diagnostics,
        whole_member_approved=False,NBR_capacities_used=False,new_H4_check_performed=False)
    (ROOT/'RESULTS.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    summary=dict(reference_cases=len(cases),conditional_lips_cases=sum(c['compressed_side']=='lips' for c in cases),
        conditional_web_F2_F3_cases=sum(c['compressed_side']=='web' for c in cases),
        strict_web_cases_blocked=sum(c['Ma_reference_floor_Nmm'] is None for c in cases),web_discrete_diagnostics=len(diagnostics),
        baseline_web=next(c for c in cases if c['thickness_mm']==1.5 and c['L_mm']==4000 and c['compressed_side']=='web'),
        baseline_lips=next(c for c in cases if c['thickness_mm']==1.5 and c['L_mm']==4000 and c['compressed_side']=='lips'),
        baseline_web_discrete=next(c for c in diagnostics if c['thickness_mm']==1.5 and c['L_mm']==4000),
        whole_member_approved=False,new_H4_check_performed=False)
    (ROOT/'SUMMARY.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
