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

SCHEMA='nbr_ue_family_components_v2'
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


def assess(index,*,L_mm,material=None,lengths=None,load_position='unknown'):
    out=base.assess(index,L_mm=L_mm,material=material,lengths=lengths,load_position=load_position)
    m=out['source_binding']['material'];p,props=_geometry(index);L=out['physical_span_mm']
    out['schema']=SCHEMA;out['source_documents']=copy.deepcopy(SOURCE_DOCUMENTS)
    out['method_revision']='R11: sign-specific full-flange MLE, conventional strong MLE and weak-negative elastic distortion'
    out['complete_reference_meaning']='All pure-axis reference components available, including labelled approximations; not actual-load, biaxial or member approval.'
    if not out['strong']['local']['eligible']:
        old_reason=out['strong']['local']['reason']
        try:
            sec=expanded.strong_effective_modulus(p,props,m,m['fy_MPa'])
        except expanded.OutsideMethod as exc:
            out['strong']['local'].update(reason=old_reason+'; '+str(exc))
        else:
            out['strong']['local']=dict(eligible=True,status='computed_conventional_MLE',
                method=sec['method'],source=expanded.SOURCE_MLE,section=sec,
                Wc_mm3=props['Ix_strong_mm4']/(p['h']/2),
                Wfirst_effective_mm3=sec['Wfirst_mm3'],
                MRd_Nmm=sec['Wfirst_mm3']*m['fy_MPa']/m['gamma'],
                table12_outside_reason=old_reason,local_elastic_critical_inferred=False)
            flt=out['strong']['FLT_reference']
            try:
                flt.update(strong_capacity_at_me(index,material=m,Me_Nmm=flt['Me_reference_Nmm']))
            except expanded.OutsideMethod as exc:
                flt.update(_missing(str(exc)))
    positive_branch=out['weak']['positive']
    if not positive_branch['local']['eligible']:
        try:
            weak,section,width=expanded.weak_positive_full_flange(p,props,m)
        except expanded.OutsideMethod as exc:
            positive_branch['local']['reason']=str(exc)
        else:
            sec,proof=weak['section'],weak['proof'];fy=m['fy_MPa'];gamma=m['gamma']
            wc=props['Iy_weak_mm4']/(props['centroid_xy_mm'][0]+p['t']/2)
            me=positive_branch['FLT_reference']['Me_reference_Nmm']
            chi,branch=chi_flt(math.sqrt(wc*fy/me));local=sec['Wfirst_mm3']*fy/gamma
            if chi*fy>=proof['compression_stress_at_first_yield_MPa']:
                trial=sec;fltval=local;method='Local first yield verified below chi*fy compression cap'
            else:
                trial=section(width(chi*fy));fltval=chi*fy*trial['Wc_web_mm3']/gamma
                method='NBR9.8.2.2(a), uniform-web MLE at chi*fy; fully effective flange rechecked'
            gradient=(m['fy_MPa']/(p['bf']-p['t']/2-trial['centroid_x_mm'])
                if fltval==local else chi*fy/(trial['centroid_x_mm']+p['t']/2))
            try:
                flt_proof=expanded.positive_flange_majorant(p,m,trial['centroid_x_mm'],gradient)
                if not flt_proof['fully_effective']:
                    raise expanded.OutsideMethod('Positive FLT flange full-effectiveness proof unavailable')
            except expanded.OutsideMethod as exc:
                flt_branch=dict(_missing(str(exc)),Me_reference_Nmm=me)
            else:
                flt_branch=dict(eligible=True,Me_reference_Nmm=me,chi=chi,curve_branch=branch,
                    MRd_Nmm=fltval,method=method,section=trial,flange_proof=flt_proof,
                    local_first_yield_cap_required=True)
            positive_branch.update(local=dict(eligible=True,status='computed_sign_specific_MLE',
                MRd_Nmm=local,section=sec,proof=proof,source=expanded.SOURCE_MLE),
                FLT_reference=flt_branch,
                distortional=dict(eligible=True,status='not_applicable_lips_in_tension',MRd_Nmm=None),
                pure_weak_reference_MRd_Nmm=min(local,fltval) if flt_branch['eligible'] else None,
                complete_reference_components=flt_branch['eligible'])
    negative_branch=out['weak']['negative']
    if not negative_branch['local']['eligible']:
        try:
            weak=expanded.weak_negative_full_flange(p,props,m,m['fy_MPa'])
        except expanded.OutsideMethod as exc:
            negative_branch['local']['reason']=str(exc)
        else:
            sec,proof=weak['section'],weak['proof'];fy=m['fy_MPa'];gamma=m['gamma']
            local=sec['Wfirst_mm3']*fy/gamma
            wc=props['Iy_weak_mm4']/(p['bf']-p['t']/2-props['centroid_xy_mm'][0])
            me=negative_branch['FLT_reference']['Me_reference_Nmm']
            chi,branch=chi_flt(math.sqrt(wc*fy/me))
            negative_branch['local']=dict(eligible=True,status='computed_sign_specific_MLE',
                MRd_Nmm=local,section=sec,proof=proof,source=expanded.SOURCE_MLE)
            try:
                trial=expanded.weak_negative_full_flange(p,props,m,chi*fy)
            except expanded.OutsideMethod as exc:
                negative_branch['FLT_reference']=dict(_missing(str(exc)),Me_reference_Nmm=me)
            else:
                negative_branch['FLT_reference']=dict(eligible=True,Me_reference_Nmm=me,
                    chi=chi,curve_branch=branch,MRd_Nmm=chi*fy*trial['section']['Wc_lips_mm3']/gamma,
                    method='NBR9.8.2.2(a), reduced uniform lips and proved full flanges',
                    section=trial['section'],proof=trial['proof'],local_first_yield_cap_required=True)
    # This is a new elastic computation specific to web-tension bending, never
    # the strong Mdist or the sign-unknown published Mly.
    try:
        distortion=expanded.weak_negative_distortion(p,props,m,elastic_distortion(p,m)['flange_lip'])
    except expanded.OutsideMethod as exc:
        distortion=_missing(str(exc))
    neg=out['weak']['negative'];neg['distortional']=distortion
    complete=all(neg[k]['eligible'] for k in ('local','FLT_reference','distortional'))
    neg['complete_reference_components']=complete
    neg['pure_weak_reference_MRd_Nmm']=min(neg[k]['MRd_Nmm'] for k in ('local','FLT_reference','distortional')) if complete else None
    neg['complete_reference_is_approximate']=complete and distortion.get('elastic_approximation',False)
    out.pop('snapshot_sha256',None);out['snapshot_sha256']=digest(out)
    return out


def validate_saved(evidence,**inputs):
    if evidence.get('schema')==legacy.SCHEMA:
        return legacy.validate_saved(evidence,**inputs)
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
    packet=dict(schema='nbr_ue_family_reference_attachment_v2',
        own_rounded_contour=assess(index,L_mm=data['L_mm'],material=m,lengths=lengths,load_position=load_position),
        published_nominal_reference=tabulated_reference(index,material=m),routes_must_not_be_mixed=True,
        legacy_denominators_replaced=False,roof_height_effect_qualified=False,whole_member_approved=False)
    packet['snapshot_sha256']=digest(packet);out=copy.deepcopy(result);out[FIELD]=packet;return out
