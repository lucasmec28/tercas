"""Opt-in candidate: RP23 negative-weak local elastic approximation + NBR curve.

The isolated v3 candidate dispatcher imports this module; not published. MLE remains preferred.
RP23 is not a sign assignment of the scalar Pierin table, a certified identical
contour eigenanalysis, or a guaranteed lower bound. Distortion is independent.
"""
from __future__ import annotations
import copy
import math
from . import nbr_ue_family_v2 as prior
from .nbr_ue_family_expansion import rho, OutsideMethod

SCHEMA = 'nbr_ue_family_components_v3_rp23_candidate'
SOURCE = dict(title='AISI RP23-01, second printing, July 2023',
    url='https://www.buildusingsteel.org/wp-content/uploads/2023/07/AISI-RP23-01-Analytical-Equations-for-Critical-Local-Buckling-Stress-of-Lipped-Channels-second-printing.pdf',
    pages_printed=[9,11,16,17,18,19,20,37,38],
    equations=[11,28,29,30],
    role='Published section-level elastic local approximation, not an NBR resistance formula')


LOCAL_MLE_GAPS = (
    'Negative weak Is<Ia under final flange envelope: partially supported flange under gradient needs a qualified reduced-section/local-elastic method',
    'Negative weak flange requires local width reduction under gradient; current full-flange MLE branch does not cover it',
)


def coefficients(eta, psi):
    """RP23 Eq28–30; explicit formula intervals, no favourable clipping."""
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (eta,psi)):
        raise ValueError('Finite numeric eta and psi required')
    if not 2.5 <= eta <= 11.1 or not .07 <= psi <= .77:
        raise OutsideMethod('RP23 requires 2.5<=b/d<=11.1 and 0.07<=psi<=0.77')
    k1=4+(0.8-.758*eta+.234*eta**2)/(1-.533*eta+.09*eta**2)
    k2=(0 if eta<=2.75 else 4*eta-11 if eta<=6 else 13)*psi
    return dict(k1=k1,k2=k2,k=k1+k2)


def critical(p, props, material, *, sign):
    """Simple unperforated Ue with 90-degree lips; nominal dimensions in mm.

    The family registry supplies this section type; this low-level helper does
    not qualify arbitrary sections by their names. No table critical is read.
    """
    if sign != 'negative':
        raise OutsideMethod('RP23 Eq28–30 here apply only to negative My_app, lips compressed')
    m=prior.material_values(material)
    h,bf,D,t,ri=[prior.positive(p[k],k) for k in ('h','bf','lip','t','ri_mm')]
    cg=prior.positive(props['centroid_xy_mm'][0],'centroid x')
    iy=prior.positive(props['Iy_weak_mm4'],'Iy')
    b,d=bf-t,D-t/2
    if min(b,d,h-2*(ri+t),bf-2*(ri+t),D-ri-t)<=0:
        raise OutsideMethod('RP23 requires physically positive straight plates and centerlines')
    if not 0<cg<b or not cg<bf-2*t-ri:
        raise OutsideMethod('Web tension and compressed lip/connecting bend not proved')
    if d/t<4.4:
        raise OutsideMethod('RP23 explicitly excludes d/t<4.4; local/distortional mixed modes')
    flat_ratios=dict(flange=(bf-2*(ri+t))/t,web=(h-2*(ri+t))/t,lip=(D-ri-t)/t)
    if flat_ratios['flange']>60 or flat_ratios['web']>200 or flat_ratios['lip']>60:
        raise OutsideMethod('NBR Table4 general unreinforced-beam width/thickness applicability remains required')
    eta,psi=b/d,cg/(b-cg)
    coef=coefficients(eta,psi)
    # Additional sample coordinates are descriptive, not invented normative vetoes.
    sample=dict(B_over_H=bf/h,D_over_B=D/bf,B_over_t=bf/t,D_over_t=D/t,
        noncommercial_sample_coordinate_envelope=(.05<=bf/h<=.75 and .1<=D/bf<=.4 and bf/t>8 and D/t>4),
        ri_over_t=ri/t,same_contour_FSM_validation=False,
        reported_fit_statistics_transferred=False,radius_sample_range_is_not_a_normative_prohibition=True)
    F=coef['k']*math.pi**2*m['E_MPa']/(12*(1-m['nu']**2))*(t/b)**2
    # Eq11 explicitly uses extreme compressed fibre, not centreline x=b.
    ccomp=bf-t/2-cg;ctension=cg+t/2
    if not ccomp>=ctension:
        raise OutsideMethod('Compressed exterior fibre must govern first yield for this NBR scalar route')
    W=iy/ccomp
    return dict(eligible=True,status='computed_published_elastic_approximation',
        method='RP23_01_Eq28_30_lips_compressed',sign=sign,compression_side='lips',
        b_mm=b,d_mm=d,centroid_from_web_midline_mm=cg,eta=eta,psi=psi,
        d_over_t=d/t,NBR_Table4_flat_ratios=flat_ratios,coefficients=coef,Fcrl_MPa=F,Ml_Nmm=F*W,Wc_mm3=W,
        exterior_compression_distance_mm=ccomp,exterior_tension_distance_mm=ctension,
        modulus_basis='RP23 Eq11: own rounded gross Iy / exterior compressed fibre distance',
        geometry_approximation='Published fitted centerline model with own rounded centroid and exterior modulus',
        material=m,source=copy.deepcopy(SOURCE),sample=sample,
        elastic_approximation=True,guaranteed_lower_bound=False,
        inherited_criticals_used=False,distortional_qualification_implied=False,
        pierin_sign_assignment=False,physical_section_verified=False)


def capacity(elastic, material, Me_Nmm):
    """NBR MSE curve using explicit approximate local critical; no AISI DSM curve."""
    m=prior.material_values(material);me=prior.positive(Me_Nmm,'Me')
    if elastic.get('material')!=m or elastic.get('sign')!='negative':
        raise ValueError('Elastic RP23 evidence must match material and negative sense')
    W=elastic['Wc_mm3'];ml=elastic['Ml_Nmm'];fy=m['fy_MPa'];g=m['gamma']
    lam=math.sqrt(W*fy/ml);chi,branch=prior.chi_flt(math.sqrt(W*fy/me))
    local=dict(elastic,MRd_Nmm=rho(lam)*W*fy/g,lambda_local=lam,
        resistance_source='NBR14762:2010 9.8.2.1(b), elastic local stability; RP23 fitted approximation explicitly adopted, not a 9.3 local exemption')
    flt=dict(eligible=True,status='computed_approximate_reference',
        method='NBR9.8.2.2(b)_MSE_with_RP23_approximate_Ml',
        MRd_Nmm=chi*rho(math.sqrt(chi*W*fy/ml))*W*fy/g,
        Me_reference_Nmm=me,Ml_Nmm=ml,Wc_mm3=W,chi=chi,curve_branch=branch,
        elastic_approximation=True,guaranteed_lower_bound=False,
        Me_qualified_by_this_helper=False)
    return local,flt


def assess(index, **inputs):
    """Candidate only, preserving existing positive and admissible negative MLE."""
    out=prior.assess(index,**inputs);out['schema']=SCHEMA
    p,props=prior._geometry(index);m=out['source_binding']['material']
    neg=out['weak']['negative'];reason=neg['local'].get('reason')
    try:el=critical(p,props,m,sign='negative')
    except OutsideMethod as exc:
        out['rp23_negative_local_candidate']=dict(eligible=False,reason=str(exc))
    else:
        out['rp23_negative_local_candidate']=el
        if not neg['local']['eligible'] and reason in LOCAL_MLE_GAPS:
            local,flt=capacity(el,m,neg['FLT_reference']['Me_reference_Nmm'])
            local['previous_MLE_gap']=reason
            neg.update(local=local,FLT_reference=flt)
    out['RP23_fallback_scope']='Only explicit gradient-flange MLE gaps; general NBR applicability is not bypassed'
    complete=all(neg[k]['eligible'] for k in ('local','FLT_reference','distortional'))
    neg['complete_reference_components']=complete
    neg['pure_weak_reference_MRd_Nmm']=min(neg[k]['MRd_Nmm'] for k in ('local','FLT_reference','distortional')) if complete else None
    neg['complete_reference_is_approximate']=complete and any(neg[k].get('elastic_approximation',False) for k in ('local','FLT_reference','distortional'))
    out['source_documents'].append(copy.deepcopy(SOURCE))
    out['method_status']='integrated_approximate_reference'
    out['physical_section_verified']=False
    out['method_revision']='RP23 candidate: negative local gaps only; MLE preferred; D independent'
    out.pop('snapshot_sha256',None);out['snapshot_sha256']=prior.digest(out)
    return out


def validate_saved(evidence,**inputs):
    expected=assess(**inputs)
    if evidence!=expected:raise ValueError('Changed RP23 candidate evidence or inputs')
    return copy.deepcopy(expected)
