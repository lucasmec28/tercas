"""Versioned parameterized NBR references for complete nominal Pierin Ue rows.

V1 arithmetic is retained in nbr_ue_family_v1 for saved-certificate replay.
Published criticals never substitute for own-rounded-contour elastic criticals.
"""
from __future__ import annotations
import copy
import math
from . import nbr_ue_family_v1 as legacy
from . import nbr_ue_family_base as base
from . import nbr_ue_family_expansion as expanded
from .nbr_ue_family_base import (FIELD, DEFAULT_MATERIAL, OutsideMethod, positive,
    material_values, rho, elastic_distortion, weak_kernel, section_constants,
    prepare, registry, digest, chi_flt, tabulated_reference, _missing)

SCHEMA='nbr_ue_family_components_v3_rp23_candidate'
SOURCE_DOCUMENTS=copy.deepcopy(legacy.SOURCE_DOCUMENTS)+copy.deepcopy(expanded.SOURCE_DOCUMENTS)


def _geometry(index):
    record=registry.select_new_study(index,include_routes=False)
    sec=prepare(index)['section'];props=sec['properties']
    p=dict(record['dimensions_mm'],ri_mm=record['published_properties']['ri_mm'],
        Ix_cm4=props['Ix_strong_mm4']/1e4)
    return p,props


def strong_capacity_at_me(index,*,material=None,Me_Nmm):
    """NBR local+FLT arithmetic for a separately qualified elastic Me.

    This helper never qualifies Me, its lengths, load heights or coefficients.
    MSE is used only within Table12; the other branch is conventional MLE.
    """
    me=positive(Me_Nmm,'supplied Me');m=material_values(DEFAULT_MATERIAL if material is None else material)
    p,props=_geometry(index);W=props['Ix_strong_mm4']/(p['h']/2)
    chi,branch=chi_flt(math.sqrt(W*m['fy_MPa']/me))
    try:
        local=legacy.local_critical('Ue',p['h'],p['bf'],p['t'],W,m['E_MPa'],m['nu'],p['lip'])
    except ValueError:
        effective=expanded.strong_effective_modulus(p,props,m,chi*m['fy_MPa'])
        we=effective['Wc_mm3'];method='NBR9.8.2.2(a)_MLE'
    else:
        we=expanded.rho(math.sqrt(chi*W*m['fy_MPa']/local['Ml_Nmm']))*W
        effective=dict(Ml_Nmm=local['Ml_Nmm'],Wc_mm3=we,source=local['origin'])
        method='NBR9.8.2.2(b)_MSE'
    return dict(eligible=True,MRd_Nmm=chi*m['fy_MPa']*we/m['gamma'],
        chi=chi,curve_branch=branch,Wc_gross_mm3=W,Wc_effective_mm3=we,
        method=method,effective_section=effective,Me_supplied_Nmm=me,
        Me_qualified_by_this_helper=False,resistance_lower_bound_qualified=False,whole_member_approved=False)


def assess(index,**inputs):
    """Fresh v3 candidate; versioned v2 readers retain their original producer."""
    from .nbr_ue_weak_rp23 import assess as candidate_assess
    return candidate_assess(index,**inputs)


def validate_saved(evidence,**inputs):
    if evidence.get('schema')==legacy.SCHEMA:
        return legacy.validate_saved(evidence,**inputs)
    if evidence.get('schema')=='nbr_ue_family_components_v2':
        from .nbr_ue_family_v2 import validate_saved as validate_v2
        return validate_v2(evidence,**inputs)
    expected=assess(**inputs)
    if evidence!=expected:raise ValueError('Changed family components or inputs; recalculate explicitly')
    return copy.deepcopy(expected)


def coverage(*,L_mm,material=None,lengths=None,load_position='unknown'):
    records=[assess(i,L_mm=L_mm,material=material,lengths=lengths,load_position=load_position) for i in registry.new_study_indices()]
    names=('strong_local','strong_distortional','strong_FLT_reference',
        'weak_positive_local','weak_negative_local','weak_positive_reference','weak_negative_reference',
        'weak_positive_distortional','weak_negative_distortional')
    counts={k:0 for k in names};rows=[]
    for r in records:
        branches={**{'strong_'+k:v for k,v in r['strong'].items()},
            **{'weak_'+s+'_'+k:v[k] for s,v in r['weak'].items() for k in ('local','distortional')}}
        row=dict(catalog_index=r['catalog_index'],catalog_id=r['catalog_id'],branches={})
        for name,b in branches.items():
            row['branches'][name]=dict(eligible=b['eligible'],reason=b.get('reason'),status=b.get('status'),
                MRd_Nmm=b.get('MRd_Nmm'),method=b.get('method'),approximate=b.get('elastic_approximation',False))
            if b['eligible']:counts[name]+=1
        for sign in ('positive','negative'):
            counts['weak_'+sign+'_reference']+=r['weak'][sign]['complete_reference_components']
        rows.append(row)
    return dict(schema=SCHEMA,total=len(records),counts=counts,rows=rows,
        material=material_values(DEFAULT_MATERIAL if material is None else material),physical_span_mm=L_mm,
        own_contour_only=True,approximations_counted_separately_in_rows=True,whole_member_approved=False)


def attach(result,*,fresh_calculation=False,lengths=None,load_position='unknown',formula_nu=.3):
    if fresh_calculation is not True:return result
    data=result['input_data'];index=data['catalog_index'];row=registry.select_new_study(index,include_routes=False);p=data['properties']
    if any(p.get(k)!=v for k,v in row['dimensions_mm'].items()):raise ValueError('Current nominal dimensions differ from selected complete Pierin row')
    m=dict(E_MPa=p['E_MPa'],G_MPa=p['G_MPa'],fy_MPa=p['fy_MPa'],nu=formula_nu,gamma=1.1)
    packet=dict(schema='nbr_ue_family_reference_attachment_v3_rp23_candidate',
        own_rounded_contour=assess(index,L_mm=data['L_mm'],material=m,lengths=lengths,load_position=load_position),
        published_nominal_reference=tabulated_reference(index,material=m),routes_must_not_be_mixed=True,
        legacy_denominators_replaced=False,roof_height_effect_qualified=False,whole_member_approved=False)
    packet['snapshot_sha256']=digest(packet);out=copy.deepcopy(result);out[FIELD]=packet;return out
