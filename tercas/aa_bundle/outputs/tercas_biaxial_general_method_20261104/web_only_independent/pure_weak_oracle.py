"""Independent closed-form reference for NBR AA web-only reduction.

No imports from the section solver or candidate application. Uses Decimal
integration and a quadratic root, not nonlinear section equilibrium iteration.
Prepared during the integrator's suite; main is run only after coordination.
"""
from decimal import Decimal as D, localcontext
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # shared outputs directory
GEOMETRY = ROOT / "tercas_biaxial_research_integration_20261104/candidate/tercas/data/torsion_profiles/ue100x50x17_t1.20.json"
GEOMETRY_SHA = "f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005"
CASE_FILE = ROOT / "tercas_girt_biaxial_component_integration_20261104/qa_r2/GIRT_BATCH_PARTIAL.json"


def number(v):
    return D(v)  # Preserve the actual binary input, not a rounded decimal text.


def geometry():
    raw = GEOMETRY.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GEOMETRY_SHA
    obj = json.loads(raw)
    pts = [tuple(number(v) for v in p) for p in obj["nodes_xy_mm"]]
    t = number(obj["thickness_mm"])
    A=Sx=Sy=Jx=Jy=Jxy=D(0)
    for a,b in zip(pts[:-1],pts[1:]):
        da = t*sum((b[i]-a[i])**2 for i in (0,1)).sqrt()
        A += da
        Sx += da*(a[0]+b[0])/2
        Sy += da*(a[1]+b[1])/2
        Jx += da*(a[0]**2+a[0]*b[0]+b[0]**2)/3
        Jy += da*(a[1]**2+a[1]*b[1]+b[1]**2)/3
        Jxy += da*(2*a[0]*a[1]+a[0]*b[1]+b[0]*a[1]+2*b[0]*b[1])/6
    nf=obj["geometry_identity"]["flat_segment_counts"]
    na=obj["geometry_identity"]["arc_segment_counts"]
    i=nf[0]+na[0]+nf[1]+na[1]
    j=i+nf[2]
    assert all(p[0]==0 for p in pts[i:j+1])
    y1,y2=pts[i][1],pts[j][1]
    width=y2-y1
    assert abs(Sy/A-(y1+y2)/2)<D('1e-12')
    return dict(A0=A,Sx=Sx,Sy=Sy,Jx=Jx,Jy=Jy,Jxy=Jxy,
                t=t,b=width,Aw=t*width,yc=Sy/A,
                Iy_gross=Jx-Sx*Sx/A,Ix_gross=Jy-Sy*Sy/A,
                E=D(200000),points=pts)


def solve_pure_weak(g, M):
    if M < 0:
        raise ValueError("This closed-form branch is web compression, My>=0 only.")
    A0,Aw,Sx,Jx = (g[k] for k in ('A0','Aw','Sx','Jx'))
    c=(g['b']/g['t']/D('.95'))**2/(4*g['E'])
    D0=A0*Jx-Sx*Sx
    Dp=(A0-Aw)*Jx-Sx*Sx
    B=Aw*Jx
    assert Dp>0
    transition=(1+D('.12').sqrt())/2
    lam_gross=(c*M*Sx/D0).sqrt()
    if lam_gross <= transition:
        lam,rho=lam_gross,D(1)
        branch='integral_including_rounded_formula_plateau'
        equation_residual=None
    else:
        C=D('.22')*B+c*M*Sx
        lam=2*C/(B+(B*B+4*Dp*C).sqrt())
        rho=(1-D('.22')/lam)/lam
        equation_residual=Dp*lam*lam+B*lam-C
        branch='closed_form_uniform_AA_web_reduction'
        assert 0<rho<1
    A=A0-Aw*(1-rho)
    xc=Sx/A
    Iy=Jx-Sx*Sx/A
    Ix=g['Ix_gross']-g['t']*(g['b']*(1-rho))**3/12
    ky=M/(g['E']*Iy)
    e0=ky*xc
    sigma_web=g['E']*e0
    return dict(branch=branch,My_Nmm=M,lambda_gross=lam_gross,
                lambda_effective=lam,rho=rho,A_mm2=A,xc_mm=xc,yc_mm=g['yc'],
                Ix_mm4=Ix,Iy_mm4=Iy,Ixy_mm4=D(0),
                strain=[e0,D(0),ky],web_line_stress_MPa=sigma_web,
                lambda_stress_identity_error=lam*lam-c*sigma_web,
                quadratic_residual=equation_residual,
                axial_resultant=e0*g['E']*A-ky*g['E']*Sx,
                weak_moment_resultant=-g['E']*(e0*Sx-ky*Jx),
                removed_web_length_mm=g['b']*(1-rho),
                reduction_transition_lambda=transition,
                reduction_transition_moment_Nmm=transition**2*D0/(c*Sx))


def encode(v):
    if isinstance(v,D): return str(v)
    if isinstance(v,dict): return {k:encode(w) for k,w in v.items()}
    if isinstance(v,(list,tuple)): return [encode(w) for w in v]
    return v


def main():
    with localcontext() as ctx:
        ctx.prec=70
        g=geometry()
        obj=json.loads(CASE_FILE.read_text())
        record=obj['gross_biaxial_component_evidence']['records']['ELSQP_00001']
        case=record['case'];L=number(obj['input_data']['L_mm'])
        assert case['q_N_mm'][0]==0 and case['P_N']==[0.,0.]
        M=number(case['q_N_mm'][1])*L*L/8
        answer=solve_pure_weak(g,M)
        origin=solve_pure_weak(g,D(0))
        threshold=answer['reduction_transition_moment_Nmm']
        controls=[solve_pure_weak(g,threshold*f) for f in
                  [D('.5'),D('.999999999'),D(1),D('1.000000001'),D('1.1')]]
        out=dict(status='independent_numerical_reference_not_design_qualification',
                 source_geometry_sha256=GEOMETRY_SHA,
                 input_sha256=hashlib.sha256(CASE_FILE.read_bytes()).hexdigest(),
                 source_case='ELSQP_00001',midspan=answer,zero=origin,
                 transition_controls=controls,
                 numerical_method='70-digit polynomial integration and stable positive quadratic root',
                 limits='Only uniform straight-web compression from pure positive My. Nonweb integral guards, material faces and full beam response are separate; no physical ELS/global approval.')
        (HERE/'PURE_WEAK_ORACLE.json').write_text(json.dumps(encode(out),indent=2)+'\n')
        print(json.dumps(encode(answer),indent=2))


if __name__=='__main__':
    main()
