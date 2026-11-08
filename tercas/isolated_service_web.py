"""Sufficient AA affine compression majorant of the saved complete ELS field.

Table 5 cases a/b only: nonnegative endpoint bounds, hence 0 <= psi <= 1.
Every wall segment, exterior face and span Bernstein coefficient is checked.
No assumption that omega is exactly affine in the discrete source is needed.
"""
from decimal import DecimalException, localcontext
import math
import numpy as np

from .torsion_vlasov.intervals import Interval as I, stack
from .biaxial_gross.gross_mle import D, GUARD, LIMIT, PRECISION, number, web_index


def affine_web_comparator(section, dimensions, E, ids, compression_fields):
    """Build and verify one exterior affine upper field, not a physical state.

    compression_fields contains BOTH exterior-face tensor Bernstein fields
    with axes (span piece, section segment, span coefficient, wall coefficient).
    All entries are already concurrent Mx+My+B, compression positive.
    """
    proof=dict(method='NBR14762_Table5_ab_complete_affine_web_majorant_v1',
        sufficient=False,reason=None,dominance_verified=False,
        source_stresses='Same concurrent Mx+My+B, both exterior faces and full physical span',
        endpoint_maxima_are_a_comparator_not_a_concomitant_state=True,
        tensile_edge_credit=False,reduced_section_calculated=False,
        numeric_contract='Outward binary64 Bernstein residuals; Decimal70 exact binary inputs and 1e-20 inward acceptance guard')
    try:
        if not ids or ids!=list(range(ids[0],ids[-1]+1)):
            raise ValueError('Contiguous complete web segments required')
        nodes=np.asarray(section['nodes_xy_mm'],dtype=float)[ids[0]:ids[-1]+2]
        # This extra comparator has an exact geometric domain. The existing
        # uniform route retains its own domain and remains independently usable.
        if not np.all(nodes[:,0]==nodes[0,0]) or not np.all(np.diff(nodes[:,1])>0):
            raise ValueError('Exactly aligned, strictly ordered flat web nodes required')
        if len(compression_fields)!=2:
            raise ValueError('Both exterior faces are required')
        fields=[field[:,ids,:,:] for field in compression_fields]
        shape=fields[0].lo.shape
        if (len(shape)!=4 or min(shape)<1 or shape[-1]<2
                or any(field.lo.shape!=shape for field in fields)):
            raise ValueError('Complete matching face polynomial arrays required')
        y=I(nodes[:,1]);height=y[-1]-y[0]
        u=(y-y[0])/height
        # Enclosure may cross 0 or 1 by rounding. Do not snap it favourably.
        coordinates=stack([u[:-1]+(u[1:]-u[:-1])*(I(float(j))/float(shape[-1]-1))
                           for j in range(shape[-1])],axis=-1)
        endpoints=[max(0.,max(float(np.max(field[:,0,:,0].hi)) for field in fields)),
                   max(0.,max(float(np.max(field[:,-1,:,-1].hi)) for field in fields))]
        def residual(edge):
            line=(I(1.)-coordinates)*edge[0]+coordinates*edge[1]
            return max(float(np.max((field-line[None,:,None,:]).hi)) for field in fields)
        before=residual(endpoints)
        correction=max(0.,before)
        # An explicitly adverse margin absorbs re-evaluation rounding. It is
        # NOT an acceptance tolerance: the final outward residual must be <=0.
        margin=float((I(max(1.,*endpoints,correction))*1e-12).hi)
        shift=float((I(correction)+margin).hi)
        corrected=[float((I(value)+shift).hi) for value in endpoints]
        after=residual(corrected)
        proof.update(endpoint_compression_upper_MPa=endpoints,
            residual_before_upper_MPa=before,residual_correction_upper_MPa=correction,
            arithmetic_margin_upper_MPa=margin,total_endpoint_shift_upper_MPa=shift,
            corrected_endpoint_upper_MPa=corrected,residual_after_upper_MPa=after,
            web_segment_indices=list(ids),web_node_count=len(nodes),exterior_face_count=2,
            source_piece_count=shape[0],checked_bernstein_coefficient_count=2*int(np.prod(shape)),
            geometric_width_upper_mm=float(height.hi),dominance_verified=after<=0.)
        if after>0:
            raise ValueError('Outward residual does not certify complete affine dominance')
        with localcontext() as ctx:
            ctx.prec=PRECISION
            t=number(dimensions['t'],'thickness');ri=number(dimensions['ri_mm'],'radius')
            nominal=number(dimensions['h'],'nominal height')-2*ri-2*t
            width=max(nominal,number(float(height.hi),'geometric width upper'))
            elastic=number(E,'E')
            if min(t,nominal,width,elastic)<=0:
                raise ValueError('Positive web dimensions and elastic modulus required')
            lam,psi,k=web_index([number(value,'corrected endpoint') for value in corrected],width,t,elastic)
            if psi is not None and not D(0)<=psi<=D(1):
                raise ValueError('Affine compression comparator restricted to Table 5 cases a/b')
            width_upper=float(width)
            if D(width_upper)<width:width_upper=math.nextafter(width_upper,math.inf)
            lambda_diagnostic=float(lam)
            if not math.isfinite(lambda_diagnostic):
                raise ValueError('Web slenderness diagnostic cannot be represented as finite JSON')
            proof.update(comparison_width_upper_mm=width_upper,psi=None if psi is None else float(psi),
                k=float(k),lambda_local_diagnostic=lambda_diagnostic,
                sufficient=bool(lam<=LIMIT*(1-GUARD)))
    except (ValueError,FloatingPointError,OverflowError,DecimalException) as exc:
        proof['reason']=str(exc)
    return proof


def refine_web(screen,section,dimensions,ids,compression_fields):
    """Retain uniform k=4 as an independent sufficient route."""
    wall=screen['walls'][2]
    wall['uniform_k4_sufficient']=wall['sufficient']
    wall['affine_web']=affine_web_comparator(section,dimensions,screen['E_MPa'],ids,compression_fields)
    wall['sufficient']=bool(wall['sufficient'] or wall['affine_web']['sufficient'])
    screen['schema']='NBR14762_service_MLE_stiffened_affine_web_sufficient_v3'
    screen['gross_local_normal_sufficient']=bool(
        all(row['sufficient'] for row in screen['walls']) and screen['elastic_field_sufficient'])
    screen['source']='NBR14762:2010 §§9.8.5(a), 9.2.2/Table5 and 9.2.3; sufficient combined-stress affine web and uniform stiffened-flange comparisons, not a new code formula'
