"""Additional EN 1993-1-3:2006 6.1.3(3) coverage, without new mechanics.

The axial effective centroid is determined at fyb. A beneficial shift therefore
cannot be credited in the stress check. Covering both the transported and the
unshifted scenarios is sufficient. Only the former has physical witnesses here.
The latter receives a conservative upper bound, never a fabricated witness.

For each signed operator pair, sigma_original - sigma_corrected is quadratic
along the beam and affine on each wall. B and all shear stresses cancel. An
exact-rational Bernstein bound on a containing section rectangle gives D.
Triangle/Lipschitz inequalities give Uoriginal <= Ucorrected + D/fy (normal)
and Uoriginal <= Ucorrected + D/(1.1 fy) (normal/shear interaction).
"""
import hashlib
import itertools
import json
import math
from fractions import Fraction as Q
from . import field_envelope as f
from .en1993_normal_components import GEOMETRY_PINS

FIELD = 'centroid_shift_policy'
ASSESSMENT_REVISION = 'EN_centroid_qualification_revision'
SCHEMA = 'EN_6_1_3_3_yield_centroid_original_stress_bound_v1'
PENDING = 'favourable_centroid_shift_coverage_pending'
SOURCE = 'EN1993-1-3:2006 6.1.3(3), applied to 6.1.6'
NOTICE = ('EN §6.1.3(3): o centroide efetivo foi calculado em fyb. '
          'O cenário sem deslocamento também precisa estar coberto para não aproveitar benefício de N·e. '
          'O teto adicional não é testemunha física; se não decidir, permanece pendência, não reprovação.')


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        allow_nan=False,separators=(',',':')).encode()).hexdigest()


def _up(value):
    result=float(value)
    if not math.isfinite(result):raise ArithmeticError('Nonfinite centroid-policy bound')
    return math.nextafter(result,math.inf) if Q(result)<value else result


def required(row,certificate):
    """Read-only applicability, including old snapshots with no policy field."""
    reference=row.get('normal_action_reference')
    if reference is not None:
        n=reference['original_polynomials_R01']['N'][0]
        if n>=0:return False
        if reference.get('available') is not True:
            return bool(certificate['components']['N_compression'].get('moment_transport_required'))
        return reference['additional_Mx_Nmm']!=0 or reference['additional_My_Nmm']!=0
    axial=certificate['components']['N_compression']
    shift=axial.get('centroid_shift_from_gross_mm')
    if not shift or not any(shift):return False
    # Old schemas retain their numerical results. Their saved signed intervals
    # can exclude compression; an unknown sign cannot establish an exemption.
    pieces=row.get('pieces',[])
    return not pieces or any(-1 in p.get('required_signs',{}).get('N',
        [p.get('signs',{}).get('N',-1)]) for p in pieces)


def _box(certificate):
    """Containing rectangle of the seven pinned Ue100x50x17 faceted sections.

    This is geometry arithmetic, not a section/property reconstruction. The
    1e-9 mm outward pad also contains binary64 exterior-vertex construction.
    Generation independently checks every actual exterior vertex against it.
    """
    t=certificate['thickness_mm']
    if t not in GEOMETRY_PINS or certificate.get('nodes_sha256')!=GEOMETRY_PINS[t]:
        raise ValueError('Centroid policy requires the pinned Ue100x50x17 family')
    cx,cy=map(Q,certificate['gross_properties']['centroid_xy_mm'])
    half=Q(t)/2;pad=Q(1,10**9)
    return ((-half-cx-pad,Q(50)-half-cx+pad),
            (-half-cy-pad,Q(100)-half-cy+pad))


def _operators(polynomials,certificate):
    intervals=f.sign_intervals(polynomials);result={}
    for axis in ('Mx','My'):
        signs={s for row in intervals for s in row['required_signs'][axis] if s}
        choices=[]
        for sign in sorted(signs):
            key=axis+('_positive' if sign>0 else '_negative')
            record=certificate['components'][key]
            if not record['eligible']:return None
            coef=tuple(map(Q,record['sigma_coefficients_c0_cx_cy']))
            if coef not in choices:choices.append(coef)
        result[axis]=choices or [(Q(0),Q(0),Q(0))]
    return result


def difference_bound(reference,certificate):
    """Union of possible operators, not a claim that every pairing is physical."""
    original=reference['original_polynomials_R01'];corrected=reference['corrected_polynomials_R01']
    oo=_operators(original,certificate);cc=_operators(corrected,certificate)
    if oo is None or cc is None:return None
    box=_box(certificate);axis_bounds={}
    for axis in ('Mx','My'):
        # Identical action fields have identical physical sign/operator at
        # every point, even across roots. Do not invent cross-sign differences
        # on the unaffected axis (ey=0 throughout the pinned family).
        if original[axis]==corrected[axis]:
            axis_bounds[axis]=0.
            continue
        p=[Q(v) for v in original[axis]]+[Q(0)]*(3-len(original[axis]))
        q=[Q(v) for v in corrected[axis]]+[Q(0)]*(3-len(corrected[axis]))
        bound=Q(0)
        for a,b in itertools.product(oo[axis],cc[axis]):
            for x,y in itertools.product(*box):
                ca=a[0]+a[1]*x+a[2]*y;cb=b[0]+b[1]*x+b[2]*y
                z=[v*ca-w*cb for v,w in zip(p,q)]
                # Quadratic Bernstein convex hull on the complete [0,1].
                bound=max(bound,abs(z[0]),abs(z[0]+z[1]/2),abs(sum(z)))
        axis_bounds[axis]=_up(bound)
    # Separate axis maxima are a sufficient bound only, never a witness.
    return dict(difference_upper_MPa=_up(sum(map(Q,axis_bounds.values()))),
                axis_difference_upper_MPa=axis_bounds,
                operator_union_counts={axis:[len(oo[axis]),len(cc[axis])] for axis in oo})


def build(row,certificate,*,fibers=None):
    reference=row['normal_action_reference'];needed=required(row,certificate)
    normal=row.get('normal');interaction=(row.get('shear_interaction') or {}).get('interaction')
    sources=dict(complete=row['complete'],normal_upper=None if normal is None else normal['index_upper_bound'],
        interaction_upper=None if interaction is None else interaction['index_upper_bound'])
    result=dict(schema=SCHEMA,source=SOURCE,
        source_section_certificate_sha256=certificate['content_sha256'],
        source_action_reference_sha256=_sha(reference),source_corrected_bounds_sha256=_sha(sources),
        row_identity={k:row[k] for k in ('combination_id','girt','segment_id','x_start_mm','x_end_mm')},
        required=needed,centroid_calculation_stress='fyb',
        method='Exact-rational quadratic Bernstein/operator union over pinned containing rectangle; upward-rounded binary64 output',
        original_scenario_witness=None,bound_is_not_a_concomitant_state=True,
        original_index_upper_bounds=dict(normal=None,interaction=None),difference_bound=None,
        status='not_required_no_compressive_centroid_moment')
    if needed:
        result['status']=PENDING
        if reference.get('available') is True:
            proof=difference_bound(reference,certificate)
            result['difference_bound']=proof
            if fibers is not None:
                box=_box(certificate)
                if not all(box[0][0]<=Q(x)<=box[0][1] and box[1][0]<=Q(y)<=box[1][1]
                           for x,y in fibers['xy_mm']):
                    raise ValueError('Pinned containing rectangle excludes an exterior vertex')
            if proof is not None and row['complete']:
                limit=certificate['normal_yield_limit_MPa']
                for key,denominator in (('normal',limit),('interaction',1.1*limit)):
                    upper=sources[key+'_upper']
                    if upper is not None:
                        result['original_index_upper_bounds'][key]=_up(Q(upper)+Q(proof['difference_upper_MPa'])/Q(denominator))
                if all(v is not None and v<=1 for v in result['original_index_upper_bounds'].values()):
                    result['status']='original_and_corrected_scenarios_within_1_by_sufficient_bounds'
    result['content_sha256']=_sha(result)
    return result


def verify(component):
    """Verify saved arithmetic/binding only. No solver, section build or envelope."""
    for row in component['rows']:
        if FIELD in row and row[FIELD]!=build(row,component['component_sections']):
            raise ValueError('Saved favourable-centroid policy/binding changed')


def qualification(component,member,criterion):
    """A separate read-time gate; never alter historical indices or witnesses."""
    if criterion not in ('normal','shear','interaction'):raise ValueError('Unknown centroid-policy criterion')
    relevant=[] if criterion=='shear' else [row for row in component['rows'] if row['girt']==member
        and required(row,component['component_sections'])]
    uppers=[];pending=[]
    for row in relevant:
        policy=row.get(FIELD)
        upper=None if policy is None else policy['original_index_upper_bounds'][criterion]
        if upper is not None:uppers.append(upper)
        if upper is None or upper>1:pending.append(row['segment_id']+'@'+row['combination_id'])
    return dict(schema=SCHEMA,required_segments=len(relevant),covered_segments=len(relevant)-len(pending),
        pending_segments=pending,qualified=not pending,
        original_index_upper_bound=max(uppers) if uppers and len(uppers)==len(relevant) else None,
        criterion=PENDING if pending else 'original_scenario_covered' if relevant else 'not_required',
        reason=NOTICE if pending else '',bound_is_not_a_concomitant_state=True)


def decision(component,member,criterion,saved_criterion):
    gate=qualification(component,member,criterion)
    failed=saved_criterion is not None and saved_criterion.startswith('above_1')
    return PENDING if not failed and not gate['qualified'] else saved_criterion


def verify_assessment(component,assessment,members):
    """Do not revive a pre-policy cached panorama for affected compression.

    Retiring a stale sidecar does not rewrite or recalculate its mechanical
    source. A newly requested panorama reads the same saved stress numbers.
    """
    affected={row['girt'] for row in component['rows'] if row['girt'] in members
              and required(row,component['component_sections'])}
    if not affected:return
    if assessment.get(ASSESSMENT_REVISION)!=SCHEMA:
        raise ValueError('Panorama anterior à cobertura EN6.1.3(3) do centroide; monte novamente o panorama, sem recalcular o modelo')
    grouped=[check for group in assessment.get('groups',[]) if group['id']=='EN_section'
             for check in group['checks']]
    for member in affected:
        for criterion in ('normal','interaction'):
            expected=qualification(component,member,criterion);key='EN:'+member+':'+criterion
            for records in (assessment['checks'],grouped):
                selected=[row for row in records if row['id']==key]
                # A source-reader failure may already have replaced the EN
                # checks with a wholly pending inventory. It grants no credit.
                if not selected and not any(row['id'].startswith('EN:') and row['status']=='meets' for row in records):
                    continue
                if (len(selected)!=1 or selected[0].get('trace',{}).get(FIELD)!=expected or
                    (selected[0]['status']=='meets' and not expected['qualified'])):
                    raise ValueError('Saved panorama favourable-centroid qualification changed')
