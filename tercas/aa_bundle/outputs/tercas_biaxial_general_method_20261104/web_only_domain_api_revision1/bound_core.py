"""Sufficient AA-web-domain bound from a nested retained-area subset.

No nonlinear section solves or application imports. High-precision 3x3
matrix arithmetic and monotone scalar cubic bracketing only. Research.
"""
from pathlib import Path
import sys
import json
import hashlib
from decimal import localcontext
import mpmath

# Private context per loaded core: do not change the caller/global precision.
mp = mpmath.mp.clone()

HERE=Path(__file__).resolve().parent

mp.dps=70
v=lambda z:mp.mpf(str(z))
PAD=mp.mpf('1e-20')


def model(source):
    with localcontext() as c:
        c.prec=70
        gd=source.geometry()
    g={k:v(z) for k,z in gd.items() if k!='points'}
    g['points']=[tuple(v(z) for z in p) for p in gd['points']]
    obj=json.loads(source.GEOMETRY.read_text())
    nf=obj['geometry_identity']['flat_segment_counts'];na=obj['geometry_identity']['arc_segment_counts']
    walls=[];start=0
    for j,name in enumerate(('bottom_lip','bottom_flange','web','top_flange','top_lip')):
        end=start+nf[j];a,b=g['points'][start],g['points'][end]
        length=mp.sqrt(sum((b[i]-a[i])**2 for i in (0,1)))
        normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
        walls.append((name,start,end,length,normal))
        start=end+(na[j] if j<4 else 0)
    g['walls']=walls
    w=walls[2];g['web_mid']=(g['points'][w[1]][1]+g['points'][w[2]][1])/2
    y=g['yc'];E=g['E'];sx=g['Sx'];sy=g['Sy'];A=g['A0']
    # Shift only y for conditioning. N=0 leaves the moment vector unchanged.
    scy=sy-y*A;jcy=g['Jy']-2*y*sy+y*y*A;jcxy=g['Jxy']-y*sx
    g['Kg']=E*mp.matrix([[A,scy,-sx],[scy,jcy,-jcxy],[-sx,-jcxy,g['Jx']]])
    g['Cg']=g['Kg']**-1
    return g


def compliance_difference(g,eta):
    length=g['b']*(1-2*eta);area=g['t']*length
    dy=g['web_mid']-g['yc']
    removed=g['E']*mp.matrix([[area,area*dy,0],
        [area*dy,area*dy*dy+g['t']*length**3/12,0],[0,0,0]])
    low=g['Kg']-removed
    return low**-1-g['Cg'],low


def dot(a,b):return (a.T*b)[0]


def functional_bounds(g,H,R,vector):
    center=dot(vector,g['Cg']*R)+dot(vector,H*R)/2
    av=dot(vector,H*vector);ar=dot(R,H*R)
    # PSD follows from geometric inclusion; tiny negative cancellation is
    # handled only under a scale many orders below the explicit padding.
    scale=max(1,abs(center),abs(av),abs(ar))
    if min(av,ar)<-mp.mpf('1e-55')*scale:
        raise ArithmeticError('PSD arithmetic inconsistent with the model')
    radius=mp.sqrt(max(0,av)*max(0,ar))/2
    pad=PAD*max(1,abs(center)+radius)
    return center-radius-pad,center+radius+pad


def stress_bounds(g,H,R,point):
    x,y=point
    return functional_bounds(g,H,R,g['E']*mp.matrix([1,y-g['yc'],-x]))


def guaranteed_edge_fraction(g,S):
    """Valid for either physical stress orientation and any psi<=1."""
    lu=g['b']/g['t']/v('.95')*mp.sqrt(S/(4*g['E']))
    ls=(1+mp.sqrt(v('.12')))/2
    if lu<=ls*(1-PAD):return v('.5'),dict(lambda_uniform=lu,entire_web=True)
    rho=min(1,(1-v('.22')/lu)/lu)
    target=4*(lu/ls)**2*(1+PAD)
    lo=mp.mpf(0);hi=max(1,target)
    while 4+2*hi+2*hi**3<target:hi*=2
    for _ in range(180):
        mid=(lo+hi)/2
        if 4+2*mid+2*mid**3<target:lo=mid
        else:hi=mid
    # hi is the upper bracket of rmax; shrink the retained subset.
    eta=rho/(2+hi)*(1-PAD)
    return eta,dict(lambda_uniform=lu,rho_lower=rho,r_upper=hi,
                   eta_lower=eta,entire_web=False)


def wall_guards(g,H,R):
    rows=[];lim=v('.673')*(1-PAD)
    for i,(name,a,b,width,n) in enumerate(g['walls']):
        if name=='web':continue
        maxima=[]
        for p in (g['points'][a],g['points'][b]):
            for sign in (-1,1):
                pt=[p[j]+sign*g['t']/2*n[j] for j in (0,1)]
                maxima.append(stress_bounds(g,H,R,pt)[1])
        S=max(0,*maxima)*(1+PAD)
        lp0=width/g['t']/v('.623')*mp.sqrt(S/g['E'])
        Ia=Is=None
        if 'lip' in name:
            k=v('.43');lp=width/g['t']/v('.95')*mp.sqrt(S/(g['E']*k));full=lp<=lim
        elif lp0<=lim:
            k=None;lp=lp0;full=True
        else:
            d=g['walls'][0 if name.startswith('bottom') else 4][3]
            ratio=v(17)/width
            k=min(4,4 if ratio<=v('.25') else v('5.25')-5*ratio)
            Is=g['t']*d**3/12
            Ia=min(g['t']**4*(56*lp0+5),399*g['t']**4*(v('.487')*(lp0-v('.673')))**3)
            lp=width/g['t']/v('.95')*mp.sqrt(S/(g['E']*k))
            full=Is>=Ia*(1+PAD) and lp<=lim
        rows.append(dict(wall=name,sigma_upper_MPa=S,lambda_local=lp,
                         Is_mm4=Is,Ia_upper_mm4=Ia,full_sufficient=bool(full)))
    absolute=mp.mpf(0)
    for a,b in zip(g['points'][:-1],g['points'][1:]):
        le=mp.sqrt(sum((b[j]-a[j])**2 for j in (0,1)))
        normal=(-(b[1]-a[1])/le,(b[0]-a[0])/le)
        for p in (a,b):
            for sign in (-1,1):
                pt=[p[j]+sign*g['t']/2*normal[j] for j in (0,1)]
                absolute=max(absolute,*map(abs,stress_bounds(g,H,R,pt)))
    return dict(walls=rows,face_absolute_upper_MPa=absolute,
                material_sufficient=bool(absolute<=250*(1-PAD)),
                nonweb_sufficient=all(r['full_sufficient'] for r in rows))


def run_ray(g,R,L,max_stages=12):
    eta=mp.mpf(0);trace=[]
    for stage in range(max_stages):
        H,low=compliance_difference(g,eta)
        i,j=g['walls'][2][1:3]
        S=max(0,*[stress_bounds(g,H,R,g['points'][z])[1] for z in (i,j)])
        improved,formula=guaranteed_edge_fraction(g,S)
        if improved < eta-PAD*max(1,eta):
            raise ArithmeticError('Nested lower-bound construction lost monotonicity')
        trace.append(dict(stage=stage,eta_used=eta,web_compression_upper_MPa=S,
                          next_eta=max(eta,improved),derivation=formula))
        eta=max(eta,improved)
    H,low=compliance_difference(g,eta)
    guards=wall_guards(g,H,R)
    i,j=g['walls'][2][1:3]
    web_endpoint_intervals=[stress_bounds(g,H,R,g['points'][z]) for z in (i,j)]
    positive_web_box=all(a>0 for a,b in web_endpoint_intervals)
    curvatures=[]
    for i in (1,2):
        vec=mp.matrix([0,0,0]);vec[i]=1
        curvatures.append(functional_bounds(g,H,R,vec))
    # For uniform q on a simple span, R(s)=4s(L-s)/L^2 Rmid.
    # Positive Green kernel converts these bounds directly, no uniform
    # effective matrix or monotonic component assumption is used.
    factor=5*L*L/48
    displacements=[dict(midspan_interval_mm=[factor*a,factor*b],
                        absolute_max_upper_mm=factor*max(abs(a),abs(b)))
                   for a,b in curvatures]
    return dict(resultants_N_Nmm=list(R),eta=eta,trace=trace,guards=guards,
                web_endpoint_stress_intervals_MPa=web_endpoint_intervals,
                entire_final_web_box_compressive=positive_web_box,
                curvature_peak_intervals=curvatures,
                displacement_component_bounds=displacements,
                all_guards_sufficient=guards['material_sufficient'] and guards['nonweb_sufficient'],
                exact_AA_law_section_existence_sufficient=positive_web_box,
                existence_basis='Compact convex invariant compliance image and continuity of the exact AA law on positive-compression web fields. Does not assert literal continuity of floating-point interval merging tolerances.',
                uniqueness_proved=False,continuous_branch_selected=False,
                physical_ELS_approved=False,
                whole_member_approved=False,published=False)


def encode(obj):
    if isinstance(obj,mp.mpf):return mp.nstr(obj,60)
    if isinstance(obj,dict):return {k:encode(z) for k,z in obj.items()}
    if isinstance(obj,(tuple,list)):return [encode(z) for z in obj]
    return obj

