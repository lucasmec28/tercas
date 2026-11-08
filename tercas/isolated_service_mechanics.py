"""Sufficient gross MLE screen and concurrent point-displacement field.

The computed criterion belongs to the declared first-order polynomial model.
No numerical twist threshold is a code limit and no physical approval follows.
"""
from fractions import Fraction as F
import copy
import heapq
import math
import numpy as np

from .torsion_vlasov.intervals import Interval as I, stack, power_to_bernstein, elevate_bernstein
from .torsion_vlasov.yield_envelope import _member_polynomials
from .torsion_vlasov.section import verify_section
from .biaxial_gross import tensor_beam as beam

LEGACY_SCHEMA='isolated_service_gross_combined_field_v1'
STIFFENED_SCHEMA='isolated_service_stiffened_combined_field_v2'
SCHEMA='isolated_service_stiffened_affine_web_combined_field_v3'
SCHEMAS=(LEGACY_SCHEMA,STIFFENED_SCHEMA,SCHEMA)


def number(x,name,positive=False):
    if type(x) not in (int,float) or not math.isfinite(x) or (positive and x<=0):
        raise ValueError(name+': finite '+('positive ' if positive else '')+'number required')
    return float(x)


def _validate(demand,dimensions):
    if (demand.get('schema')!='single_vlasov_member_demand_v1' or demand.get('limit_state')!='ELS'
        or demand.get('numerics',{}).get('qualification_passed') is not True):
        raise ValueError('Qualified dense ELS Vlasov source required')
    verify_section(demand['section']);domain=demand['analysis_domain']
    p=demand['section']['properties']
    if abs(p['Ixy_mm4'])>1e-12*math.sqrt(p['Ix_strong_mm4']*p['Iy_weak_mm4']):
        raise ValueError('Inherited Vlasov shear source requires principal symmetric axes')
    if (type(domain.get('order')) is not int or domain.get('order')!=1
        or type(domain.get('axial_force_in_this_model_N')) not in (int,float) or domain.get('axial_force_in_this_model_N')!=0
        or domain.get('intermediate_braces') is not False or domain.get('sheet_restraint') is not False):
        raise ValueError('Only the declared isolated N=0 first-order model is supported')
    L=number(demand['length_mm'],'L',True);previous=0.
    for e in demand['elements']:
        if e['a_mm']!=previous or not e['a_mm']<e['b_mm']<=L:raise ValueError('Incomplete element coverage')
        previous=e['b_mm']
    if previous!=L:raise ValueError('Missing physical span coverage')
    from .isolated_en_stress import _support_limit_guard
    _support_limit_guard(demand)
    d={k:number(dimensions[k],k,True) for k in ('h','bf','lip','t')}
    d['ri_mm']=number(dimensions['ri_mm'],'ri')
    if d['ri_mm']<0 or d['t']!=demand['section']['thickness_mm']:raise ValueError('Section dimensions disagree')
    return d


def _flat_ids(section,d):
    """Recognize all five Ue flats by coordinates, not catalogue/profile IDs."""
    h,b,l,t,ri=(d[k] for k in ('h','bf','lip','t','ri_mm'))
    height=h-t;width=b-t;r=ri+t/2;tip=l-t/2
    widths=[l-ri-t,b-2*ri-2*t,h-2*ri-2*t,b-2*ri-2*t,l-ri-t]
    if min(widths)<=0:raise ValueError('Nonpositive flat width')
    nodes=np.asarray(section['nodes_xy_mm']);tol=max(h,b)*1e-10
    def near(v,target):return abs(v-target)<=tol
    groups=[[] for _ in range(5)]
    for i,(a,z) in enumerate(zip(nodes[:-1],nodes[1:])):
        if all(near(p[0],width) and r-tol<=p[1]<=tip+tol for p in (a,z)):groups[0].append(i)
        elif all(near(p[1],0) and r-tol<=p[0]<=width-r+tol for p in (a,z)):groups[1].append(i)
        elif all(near(p[0],0) and r-tol<=p[1]<=height-r+tol for p in (a,z)):groups[2].append(i)
        elif all(near(p[1],height) and r-tol<=p[0]<=width-r+tol for p in (a,z)):groups[3].append(i)
        elif all(near(p[0],width) and height-tip-tol<=p[1]<=height-r+tol for p in (a,z)):groups[4].append(i)
    for ids,w in zip(groups,widths):
        length=math.fsum(float(np.linalg.norm(nodes[i+1]-nodes[i])) for i in ids)
        if not ids or not math.isclose(length,w,rel_tol=1e-10,abs_tol=tol):raise ValueError('Ue flat topology or width differs from the source')
    return groups,widths


def gross_screen(demand,dimensions,fy_MPa,*,schema=SCHEMA):
    """Outward Bernstein bounds of full N=0 Mx+My+B and V+T on exterior faces.

    All five flats are checked under uniform compression dominance (web AA
    k=4; lips AL k=.43; v2 also uses the existing §9.2.3 flange law).
    v3 adds the Table5 affine AA web majorant with complete residual checks. Bends are retained
    in the declared thin-wall MLE convention and included in elastic checking.
    An inconclusive sufficient comparator is never labelled a resistance fail.
    """
    if schema not in SCHEMAS:raise ValueError('Unknown combined-service arithmetic version')
    d=_validate(demand,dimensions);s=demand['section'];p=s['properties'];t=d['t']
    fy=number(fy_MPa,'fy',True);E=number(demand['E_MPa'],'E',True)
    pol,identities=_member_polynomials(demand);groups,widths=_flat_ids(s,d)
    nodes=I(s['nodes_xy_mm']);xy=nodes-I(p['centroid_xy_mm']);delta=nodes[1:]-nodes[:-1]
    length=(delta[:,0].square()+delta[:,1].square()).sqrt()
    normals=stack([-delta[:,1]/length,delta[:,0]/length],axis=-1)
    omega=I(s['omega_nodes_mm2']);w=stack([omega[:-1],omega[1:]-omega[:-1]],axis=-1)
    Ix,Iy,Ixy=I(p['Ix_strong_mm4']),I(p['Iy_weak_mm4']),I(p['Ixy_mm4'])
    det=Ix*Iy-Ixy*Ixy
    mx_x=-Ixy/det;mx_y=Iy/det;my_x=-Ix/det;my_y=Ixy/det
    def outer(a,b):return a[:,None,:,None]*b[None,:,None,:]
    st=I(s['segment_static_coefficients'])
    flow=-(outer(pol['Vx']/p['Iy_weak_mm4'],st[:,0,:])+outer(pol['Vy']/p['Ix_strong_mm4'],st[:,1,:])+
           outer(pol['Tw']/p['Cw_mm6'],st[:,2,:]))/t
    const=I(np.column_stack([np.ones(len(xy.lo)-1),np.zeros((len(xy.lo)-1,2))]))
    sv=outer(pol['Tsv']*t/p['J_mm4'],const)
    compression=[0.]*5;absolute=0.;vm_upper=0.;compression_fields=[]
    for face in (-1,1):
        pos=xy[:-1]+normals*(face*t/2)
        xm=stack([pos[:,0],delta[:,0]],axis=-1);ym=stack([pos[:,1],delta[:,1]],axis=-1)
        sigma=outer(pol['Mx'],mx_x*xm+mx_y*ym)+outer(pol['My'],my_x*xm+my_y*ym)+outer(pol['B']/p['Cw_mm6'],w)
        sigma=elevate_bernstein(power_to_bernstein(sigma),-1,2)
        if schema==SCHEMA:compression_fields.append(-sigma)
        tau=elevate_bernstein(power_to_bernstein(flow-face*sv),-2,3)
        absolute=max(absolute,float(np.max(sigma.abs().hi)))
        squared=sigma.square()+tau.square()*3
        # Intersection with the proven nonnegative range of a sum of squares.
        vm=I(np.maximum(0.,squared.lo),np.maximum(0.,squared.hi)).sqrt()
        vm_upper=max(vm_upper,float(np.max(vm.hi)))
        for j,ids in enumerate(groups):compression[j]=max(compression[j],float(np.max(-sigma[:,ids,:,:].lo)))
    walls=[]
    for name,width,k,upper in zip(('bottom_lip','bottom_flange','web','top_flange','top_lip'),widths,(.43,.43,4.,.43,.43),compression):
        limit=(I(.673)*.95).square()*k*E*(I(t)/width).square()
        threshold=float(limit.lo)
        walls.append(dict(name=name,width_mm=width,k=k,compression_upper_MPa=max(0.,upper),
                          integral_limit_lower_MPa=threshold,sufficient=max(0.,upper)<=threshold))
    sufficient=bool(walls and len(walls)==5 and all(r['sufficient'] for r in walls) and vm_upper<=fy)
    result=dict(schema='NBR14762_service_MLE_complete_normal_gross_sufficient_v1',
        source='NBR14762:2010 §9.8.5(a), §§9.2.2/9.2.3; sufficient uniform-compression comparison, not a new code formula',
        E_MPa=E,fy_MPa=fy,walls=walls,max_abs_normal_upper_MPa=absolute,
        von_mises_upper_MPa=vm_upper,elastic_field_sufficient=vm_upper<=fy,
        gross_local_normal_sufficient=sufficient,all_five_walls_and_all_bends_elastic_checked=True,
        source_piece_count=len(identities),source_section_segments=len(s['nodes_xy_mm'])-1,
        scope='Sufficient local-normal MLE and elastic-field check in the declared gross polynomial model. Does not certify member stability or physical first-order applicability.',
        failed_sufficient_screen_is_physical_failure=False)
    if schema in (STIFFENED_SCHEMA,SCHEMA):_refine_stiffened_flanges(result,d)
    if schema==SCHEMA:
        from .isolated_service_web import refine_web
        refine_web(result,s,d,groups[2],compression_fields)
    return result


def _refine_stiffened_flanges(screen,dimensions):
    """Use the existing §9.2.3 scalar law on the SAME combined stress bound.

    The common uniform compression dominates both flange and adjacent lip.
    The lip must stay fully effective even under that common majorant before
    its unmodified Is may enter the flange proof. The original AL route is
    independently retained; no inconclusive sufficient result becomes a fail.
    """
    from decimal import localcontext
    from .biaxial_gross.gross_mle import D,GUARD,LIMIT,PRECISION,number as decimal,unpack
    from .isolated_service_stiffener import flange_uniform_comparator
    walls=screen['walls'];E=screen['E_MPa'];d=dimensions
    for flange_index,lip_index in ((1,0),(3,4)):
        wall,lip=walls[flange_index],walls[lip_index]
        common=max(wall['compression_upper_MPa'],lip['compression_upper_MPa'])
        proof=dict(method='NBR14762_9_2_3_uniform_flange_and_adjacent_lip_majorant_v1',
            common_compression_upper_MPa=common,adjacent_lip_name=lip['name'],
            adjacent_lip_full_under_common_majorant=False,adjacent_lip_lambda_diagnostic=None,
            source_stresses='Same outward Mx+My+B bounds on both exterior faces over the full physical span',
            comparison=None,sufficient=False,reason=None,
            numeric_contract='70-digit decimal, exact binary inputs, 1e-20 inward acceptance guard')
        try:
            with localcontext() as ctx:
                ctx.prec=PRECISION
                t=decimal(d['t'],'thickness');ri=decimal(d['ri_mm'],'radius')
                nominal_lip=decimal(d['lip'],'nominal lip')
                width=decimal(d['bf'],'nominal flange')-2*ri-2*t
                lip_width=nominal_lip-ri-t
                elastic=decimal(E,'E');sigma=decimal(common,'combined compression')
                # Derive widths BEFORE rounding to binary64; no favourable
                # pre-rounded Is or slenderness can enter the 1e-20 guard.
                lip_lambda=lip_width/t/D('.95')*(sigma/(elastic*D('.43'))).sqrt()
                lip_full=lip_lambda<=LIMIT*(1-GUARD)
                comparison=flange_uniform_comparator(width,t,nominal_lip,lip_width,elastic,sigma)
                proof['adjacent_lip_lambda_diagnostic']=float(lip_lambda*(1+GUARD))
                proof['adjacent_lip_full_under_common_majorant']=lip_full
                proof['comparison']=unpack(comparison)
                proof['sufficient']=bool(lip_full and comparison['full_wall_sufficient'])
        except ValueError as exc:
            # The old no-stiffener branch may still prove full effectiveness.
            # A limitation of the extra comparator is not normative rejection.
            proof['reason']=str(exc)
        wall['uniform_unstiffened_sufficient']=wall['sufficient']
        wall['edge_stiffener']=proof
        wall['sufficient']=bool(wall['sufficient'] or proof['sufficient'])
    screen['schema']='NBR14762_service_MLE_stiffened_complete_normal_sufficient_v2'
    screen['gross_local_normal_sufficient']=bool(
        all(w['sufficient'] for w in walls) and screen['elastic_field_sufficient'])
    screen['source']='NBR14762:2010 §9.8.5(a), §§9.2.2/9.2.3; sufficient combined-stress uniform comparison with existing edge-stiffener law, not a new code formula'
    screen['effective_reduced_section_calculated']=False
    screen['inconclusive_means_only_this_sufficient_method_unresolved']=True


def _fraction(x):return F(number(x,'polynomial input'))


def _bernstein(c):
    n=len(c)-1
    return [sum((c[k]*F(math.comb(i,k),math.comb(n,k)) for k in range(i+1)),F(0)) for i in range(n+1)]


def _split(b):
    left=[];right=[]
    while b:
        left.append(b[0]);right.append(b[-1]);b=[(x+y)/2 for x,y in zip(b[:-1],b[1:])]
    return left,list(reversed(right))


def _outward(value,upper):
    f=float(value)
    if not math.isfinite(f):raise ValueError('Nonfinite field bound')
    if (F(f)<value if upper else F(f)>value):f=math.nextafter(f,math.inf if upper else -math.inf)
    return f


def envelope(pieces,*,absolute_tolerance_mm=1e-7,relative_tolerance=1e-8,max_splits=4096):
    """Exact-rational de Casteljau bounds; no sum of separate field maxima."""
    if not pieces:raise ValueError('Nonempty displacement field required')
    heap=[];serial=0;best=F(0);witness=None
    for i,p in enumerate(pieces):
        c=[F(v) for v in p['coefficients']];b=_bernstein(c)
        for u in (F(0),F(1,2),F(1)):
            value=beam.value(c,u)
            if witness is None or abs(value)>best:
                best=abs(value);witness=dict(piece_index=i,u=float(u),station_mm=float(p['a']+(p['b']-p['a'])*u),signed_mm=float(value))
        heapq.heappush(heap,(-max(map(abs,b)),serial,i,F(0),F(1),b));serial+=1
    splits=0
    while -heap[0][0]-best>max(F(absolute_tolerance_mm),F(relative_tolerance)*best) and splits<max_splits:
        _,_,i,a,z,b=heapq.heappop(heap);mid=(a+z)/2
        left,right=_split(b);value=left[-1]
        if abs(value)>best:
            best=abs(value);p=pieces[i];witness=dict(piece_index=i,u=float(mid),station_mm=float(p['a']+(p['b']-p['a'])*mid),signed_mm=float(value))
        for lo,hi,part in ((a,mid,left),(mid,z,right)):
            heapq.heappush(heap,(-max(map(abs,part)),serial,i,lo,hi,part));serial+=1
        splits+=1
    upper=max(best,-heap[0][0]);lower=best
    return dict(abs_displacement_lower_mm=_outward(lower,False),abs_displacement_upper_mm=_outward(upper,True),
        witness=witness,subdivisions=splits,converged=upper-lower<=max(F(absolute_tolerance_mm),F(relative_tolerance)*best),
        method='Exact-rational Bernstein subdivision of the combined projected polynomial; bounds enclose the saved field, not FE discretization error')


def displacement_field(demand,point_xy_from_CG_mm,projection_xy):
    """Euler-Bernoulli tensor flexure at SC plus SAME field phi cross(SC->P)."""
    p=demand['section']['properties'];L=demand['length_mm'];acts=demand['loads']
    q=[sum((F(a['q_xy_N_mm'][j]) for a in acts if a['kind']=='uniform'),F(0)) for j in (0,1)]
    pts=[a for a in acts if a['kind']=='point']
    if len(pts)>1:raise ValueError('This source supports one concentrated transverse force')
    P=pts[0]['force_xy_N'] if pts else [0.,0.];position=pts[0]['s_mm'] if pts else None
    # Fixed endpoint forces have zero interior flexure, like the mathematical
    # support-limit branch, but retain their original transfer/torque records.
    if pts and position in (0.,L):pos='support_limit';a=None
    elif pts:pos='finite_interior';a=position
    else:pos=None;a=None
    model=beam.build_beam(dict(L_mm=L,E_MPa=demand['E_MPa'],supports='simply_supported_bending',
                              prismatic=True,scope='gross_flexural_component_only'),
        dict(Ix_mm4=p['Ix_strong_mm4'],Iy_mm4=p['Iy_weak_mm4'],Ixy_mm4=p['Ixy_mm4']),
        dict(q_N_mm=[-q[1],q[0]],P_N=[-P[1],P[0]],point_position=pos,a_mm=a))
    if not isinstance(point_xy_from_CG_mm,list) or len(point_xy_from_CG_mm)!=2:raise ValueError('Explicit point required')
    if not isinstance(projection_xy,list) or len(projection_xy)!=2:raise ValueError('Explicit projection required')
    dx,dy=map(_fraction,point_xy_from_CG_mm);nx,ny=map(_fraction,projection_xy)
    if not math.isclose(float(nx*nx+ny*ny),1.,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Unit direction required')
    rx=F(p['centroid_xy_mm'][0])-F(p['shear_center_xy_mm'][0])+dx
    ry=F(p['centroid_xy_mm'][1])-F(p['shear_center_xy_mm'][1])+dy
    rotation_factor=-nx*ry+ny*rx
    rows=[]
    for e in demand['elements']:
        aa,bb=F(e['a_mm']),F(e['b_mm']);length=bb-aa
        candidates=[part for part in model.pieces if part.start<=aa and bb<=part.end]
        if len(candidates)!=1:raise ValueError('Flexural/torsion partition mismatch')
        part=candidates[0];u=(aa-part.start)/(part.end-part.start);du=length/(part.end-part.start)
        normal,parallel=[beam.compose_affine(c,u,du) for c in part.coefficients]
        phi=tuple(F(v) for v in e['coefficients']['phi_rad'])
        c=beam.add(beam.add(beam.scale(parallel,nx),beam.scale(normal,-ny)),beam.scale(phi,rotation_factor))
        rows.append(dict(a=aa,b=bb,coefficients=c,element_id=e['element_id']))
    # Relative to chord of the same point. Fork source endpoints have phi=0;
    # retain their tiny saved numerical endpoint values rather than assuming 0.
    v0=beam.value(rows[0]['coefficients'],F(0));vL=beam.value(rows[-1]['coefficients'],F(1))
    for r in rows:
        chord=(v0+(vL-v0)*r['a']/F(L),(vL-v0)*(r['b']-r['a'])/F(L))
        r['coefficients']=beam.add(r['coefficients'],beam.scale(chord,-1))
    return rows


def calculate(demand,dimensions,fy_MPa,configuration,limit_mm,*,schema=SCHEMA):
    screen=gross_screen(demand,dimensions,fy_MPa,schema=schema)
    field=displacement_field(demand,configuration['point_xy_from_CG_mm'],configuration['projection_xy'])
    env=envelope(field);limit=number(limit_mm,'service limit',True)
    lo=_outward(F(env['abs_displacement_lower_mm'])/F(limit),False)
    hi=_outward(F(env['abs_displacement_upper_mm'])/F(limit),True)
    state=('within_declared_linear_model' if hi<=1 else 'above_declared_linear_model' if lo>1 else 'numerical_boundary_inconclusive')
    if not screen['gross_local_normal_sufficient']:state='gross_MLE_sufficient_condition_inconclusive'
    return dict(schema=schema,combination_id=demand['combination_id'],limit_state='ELS',
        source_section_sha256=demand['section']['content_sha256'],source_length_mm=demand['length_mm'],
        gross_screen=screen,envelope=env,limit_mm=limit,criterion_status=state,
        index_upper=hi if screen['gross_local_normal_sufficient'] else None,
        index_lower=lo if screen['gross_local_normal_sufficient'] else None,
        diagnostic_ratio_upper=hi,diagnostic_ratio_lower=lo,
        index_kind='bounds_of_combined_displacement_in_declared_linear_gross_model',
        stored_linear_twist_max_rad=abs(demand['max_abs_phi']['phi_rad']),
        rotation_screening_warning=demand['small_rotation_warning'],
        physical_first_order_applicability_qualified=False,combined_ELS_approved=False,whole_member_approved=False,
        displacement_definition='point displacement relative to the chord of the same point at physical member ends',
        source_point_xy_from_CG_mm=copy.deepcopy(configuration['point_xy_from_CG_mm']),
        source_projection_xy=copy.deepcopy(configuration['projection_xy']))
