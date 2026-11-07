"""A directed point witness, not a physical maximum or a new member solver.

Only geometric endpoints are candidates. A governing Bernstein control may
identify a source patch, never a physical observation or its stress value.
"""
from fractions import Fraction as F
from .torsion_vlasov.intervals import Interval as I
from .torsion_vlasov.yield_envelope import _member_polynomials
from .en_ue125_300_authority import _sha


def _pair(value):return [float(value.lo),float(value.hi)]


def _evaluate(coefficients,u):
    out=I(0.)
    for i in range(len(coefficients.lo)-1,-1,-1):out=out*u+coefficients[i]
    return out


def _exact_zero_moments(demand,element,u):
    """Exact rational identity at this point, never a small-value threshold."""
    x=F(element['a_mm'] if u==0 else element['b_mm'])
    ra=list(map(F,demand['support_reactions']['left_force_xy_N']))
    q=[sum((F(a['q_xy_N_mm'][j]) for a in demand['loads'] if a['kind']=='uniform'),F(0)) for j in (0,1)]
    mx=-ra[1]*x-q[1]*x*x/2;my=ra[0]*x+q[0]*x*x/2
    for a in demand['loads']:
        if a['kind']=='point' and a['s_mm']<=element['a_mm']:
            distance=x-F(a['s_mm']);mx-=F(a['force_xy_N'][1])*distance;my+=F(a['force_xy_N'][0])*distance
    return dict(Mx=mx==0,My=my==0)


def observe(demand,normal,control):
    """Return only a strict, source-bound |sigma| lower-bound exceedance."""
    if (type(control.get('longitudinal_control')) is not int or control['longitudinal_control'] not in (0,3)
        or type(control.get('wall_control')) is not int or control['wall_control'] not in (0,2)
        or type(control.get('face')) is not int):return None
    piece=control['source_piece'];u=0. if control['longitudinal_control']==0 else 1.
    wall_u=0. if control['wall_control']==0 else 1.;j=control['wall_segment'];face=control['face']
    section=demand['section'];props=section['properties'];th=section['thickness_mm']
    if type(j) is not int or not 0<=j<len(section['nodes_xy_mm'])-1 or face not in (-1,1):return None
    pol,identities=_member_polynomials(demand)
    if piece['kind']=='element':
        index=piece['element_index']
        if type(index) is not int or not 0<=index<len(demand['elements']) or identities[index]!=piece:return None
        element=demand['elements'][index];x=element['a_mm'] if u==0 else element['b_mm']
        zero=_exact_zero_moments(demand,element,u)
        location=dict(element_index=index,element_id=element['element_id'],x_mm=x,
            longitudinal_parameter=u,side='right' if u==0 else 'left',position_limit=None)
    elif piece['kind']=='support_limit':
        matches=[i for i,identity in enumerate(identities) if identity==piece]
        if len(matches)!=1:return None
        index=matches[0];state=piece['state']
        zero=dict(Mx=state['Mx_physical_Nmm']==0,My=state['My_physical_Nmm']==0)
        location=dict(element_index=None,element_id=state['element_id'],x_mm=state['x_mm'],
            longitudinal_parameter=0.,side=state['side'],position_limit=state['position_limit'])
    else:return None
    fields={key:_evaluate(value[index],u) for key,value in pol.items()}
    fields['N']=I(0.)  # source contract is exactly N=0
    operators={}
    for axis in ('Mx','My'):
        if zero[axis]:fields[axis]=I(0.);operators[axis]=None
        elif float(fields[axis].lo)>0:operators[axis]=axis+'_positive'
        elif float(fields[axis].hi)<0:operators[axis]=axis+'_negative'
        else:return None
    p0=I(section['nodes_xy_mm'][j]);p1=I(section['nodes_xy_mm'][j+1]);delta=p1-p0
    length=(delta[0].square()+delta[1].square()).sqrt()
    normal_vector=[-delta[1]/length,delta[0]/length]
    node=j+int(wall_u);xy=I(section['nodes_xy_mm'][node])-I(props['centroid_xy_mm'])
    xy=[xy[k]+face*I(th)/2*normal_vector[k] for k in (0,1)]
    omega=I(section['omega_nodes_mm2'][node])
    sigma=fields['B']*omega/props['Cw_mm6']
    for axis,key in operators.items():
        if key is None:continue
        co=I(normal['components'][key]['sigma_coefficients_c0_cx_cy'])
        sigma=sigma+fields[axis]*(co[0]+co[1]*xy[0]+co[2]*xy[1])
    absolute=sigma.abs()
    if float(absolute.lo)<=normal['normal_yield_limit_MPa']:return None
    static=I(section['segment_static_coefficients'][j])
    primitive=[_evaluate(static[k],wall_u) for k in (0,1,2)]
    tau=-(fields['Vx']*primitive[0]/props['Iy_weak_mm4']+
        fields['Vy']*primitive[1]/props['Ix_strong_mm4']+fields['Tw']*primitive[2]/props['Cw_mm6'])/th-face*fields['Tsv']*th/props['J_mm4']
    ratio=absolute/normal['normal_yield_limit_MPa']
    out=dict(schema='EN_Ue_family_normal_physical_point_witness_v1',
        combination_id=demand['combination_id'],member_id=demand['member_id'],
        source_demand_sha256=_sha(demand),normal_source_sha256=normal['content_sha256'],
        source_section_sha256=section['content_sha256'],location=location,
        wall_segment=j,wall_parameter=wall_u,face=face,selected_operators=operators,
        exactly_zero_moments=zero,action_intervals={k:_pair(v) for k,v in fields.items()},
        face_xy_from_gross_centroid_interval_mm=[_pair(v) for v in xy],
        sigma_interval_MPa=_pair(sigma),tau_interval_MPa=_pair(tau),
        absolute_sigma_lower_MPa=float(absolute.lo),normal_ratio_interval=_pair(ratio),
        normal_limit_MPa=normal['normal_yield_limit_MPa'],strict_exceedance_proven=True,is_physical_state=True,
        physical_maximum_claimed=False,first_order_analysis_qualified=False,whole_member_approved=False,
        semantics='One concomitant physical point of the recovered linear field; not a maximum or validation of first-order physics')
    out['content_sha256']=_sha(out)
    return out


def search_endpoints(demand,normal,control):
    """Try at most eight real corners of this source patch, never its controls.

    Preserve an already proven endpoint candidate first. Otherwise derive fresh
    selectors for both longitudinal endpoints, wall endpoints and exterior faces.
    This bounded search does not claim a maximum, refine bounds or change fields.
    """
    if (type(control.get('longitudinal_control')) is not int or control['longitudinal_control'] not in (0,1,2,3)
        or type(control.get('wall_control')) is not int or control['wall_control'] not in (0,1,2)
        or type(control.get('face')) is not int or control['face'] not in (-1,1)):
        return None
    tried=set()
    if control['longitudinal_control'] in (0,3) and control['wall_control'] in (0,2):
        result=observe(demand,normal,control)
        if result is not None:return result
        tried.add((control['longitudinal_control'],control['wall_control'],control['face']))
    piece=control['source_piece']
    longitudinal=(0,) if piece.get('kind')=='support_limit' else (0,3)
    for face in (control['face'],-control['face']):
        for u in longitudinal:
            for v in (0,2):
                if (u,v,face) in tried:continue
                candidate=dict(source_piece=piece,wall_segment=control['wall_segment'],
                    longitudinal_control=u,wall_control=v,face=face)
                result=observe(demand,normal,candidate)
                if result is not None:
                    result['candidate_search']=dict(method='separate_physical_endpoints_of_governing_patch',
                        governing_longitudinal_control=control['longitudinal_control'],
                        governing_wall_control=control['wall_control'],governing_face=control['face'],
                        governing_control_is_physical_state=False,
                        candidate_is_re_evaluated_endpoint=True)
                    result['content_sha256']=_sha({k:v for k,v in result.items() if k!='content_sha256'})
                    return result
    return None
