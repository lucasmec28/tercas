"""Consume same-contour NBR family components in the N=0 member interaction.

Called by the authenticated fresh/replay family application, not an alternate
authority accepting arbitrary external component dictionaries. Nominal Pierin
and own-contour capacities are deliberately never mixed.
"""
import copy
from . import nbr_family_biaxial as arithmetic

SCHEMA = 'NBR_family_member_interaction_v1'
SOURCE = 'NBR14762:2010 §§9.8.2.1,9.8.2.2,9.8.2.3 e9.9, N=0'


def _number(value):
    import math
    return type(value) in (int,float) and math.isfinite(value) and value>0


def _zero_moment_rotation(record,active):
    """Zero net moment does not remove destabilizing height couples.

Each distinct shape/point is kept separate. Favourable potential at another
position is not used to waive an adverse one. This does not solve stability.
"""
    from fractions import Fraction as F
    rows=[];missing=[]
    for axis,sign,coordinate,force_prefix in (('Mx',1,'height_above_SC_mm','down'),('My',-1,'x_from_SC_mm','parallel')):
        if active[axis+'_positive'] or active[axis+'_negative']:continue
        grouped={};unknown=False
        for a in record.get('actions',[]):
            uniform=a['kind']=='uniform';force=a[('q_'+force_prefix+'_N_mm') if uniform else ('P_'+force_prefix+'_N')]
            if not force:continue
            offset=a[coordinate]
            if offset is None:unknown=True;continue
            key=('uniform',None) if uniform else ('point',a.get('x_mm',a.get('s_mm')))
            grouped[key]=grouped.get(key,F(0))+sign*F(force)*F(offset)
        adverse=any(v>0 for v in grouped.values())
        if unknown or adverse:missing.append(axis+':rotation_potential_without_reference_bending')
        rows.append(dict(axis=axis,unknown_position=unknown,destabilizing_group=adverse,
            groups=[dict(kind=k[0],position_mm=k[1],destabilizing_potential_exact=str(v)) for k,v in grouped.items()]))
    return dict(records=rows,missing=missing,stability_solved=False)


def build(record, sources, span_mm):
    """Use every applicable local/FLT/D denominator, with proven exemptions.

Load-height qualification belongs to the individual component producer. A
reference-only capacity without a usable index is not a design denominator.
No positive net force can waive a destabilizing individual action.
"""
    parts = [r for r in record['components'] if r['route']=='own_rounded_contour']
    by_method = {r['method']:r for r in parts}
    if len(by_method)!=len(parts):
        raise ValueError('Componentes resistentes próprias duplicadas.')
    own=sources['own_rounded_contour']
    material=own['source_binding']['material']
    from .nbr_ue_family import material_values
    material_values(material)
    combo=record['combination']
    # First derive active signs exactly; these placeholders do not qualify a
    # resistance and never escape into the final arithmetic certificate.
    active=arithmetic.interaction(combo,span_mm,dict.fromkeys(arithmetic.NAMES,1.))['active_signed_branches']
    capacities={k:None for k in arithmetic.NAMES};trace={};missing=[]
    def use(name):
        p=by_method.get(name)
        if p is None or p.get('index') is None or not _number(p.get('capacity_Nmm')):
            return None
        return dict(method=name,capacity_Nmm=p['capacity_Nmm'],
                    approximate=p.get('approximate',False),reason=p.get('reason',''),
                    lower_bound_only=p.get('capacity_lower_bound_only',False),floor_source_sha256=p.get('floor_source_sha256'))
    def distortional_exemption(name):
        from .nbr_ue_family_application import _not_applicable_basis
        p=by_method.get(name)
        return None if p is None else _not_applicable_basis(p,sources)
    for key in arithmetic.NAMES:
        if not active[key]:
            trace[key]=dict(required=False,selected=[],exemptions=[],missing=[])
            continue
        sign='positive' if key.endswith('_positive') else 'negative'
        strong=key.startswith('Mx')
        prefix='' if strong else 'weak_'+sign+'_'
        selected=[];exemptions=[];absent=[]
        gate=record.get('shear_lag_applicability',{}).get('axes',{}).get('normal' if strong else 'parallel',{})
        if gate.get('qualified') is not True:absent.append('NBR_9_4_applicability')
        local=use(prefix+'local')
        if local:selected.append(local)
        else:absent.append(prefix+'local')
        # Prefer classical Cb=1 when its actual position is qualified. The
        # documented height route is used only when classical is unavailable.
        flt=use(prefix+'FLT_reference')
        if flt is None and strong:
            flt=use('FLT_height_effective_reference')
        if flt is None and strong:
            flt=use('FLT_height_energy_floor')
        if flt:selected.append(flt)
        else:absent.append(prefix+'FLT_with_actual_position')
        dname=prefix+'distortional';d=use(dname);exempt=distortional_exemption(dname)
        if d is None and strong and exempt is None:d=use('distortional_approximation_floor')
        if d:selected.append(d)
        elif exempt is not None:exemptions.append(dict(method=dname,basis=copy.deepcopy(exempt)))
        else:absent.append(dname)
        trace[key]=dict(required=True,selected=selected,exemptions=exemptions,missing=absent)
        if absent:missing.extend(key+':'+s for s in absent)
        else:capacities[key]=min(p['capacity_Nmm'] for p in selected)
        trace[key]['denominator_lower_bound_only']=bool(not absent and all(
            p['lower_bound_only'] for p in selected if p['capacity_Nmm']==capacities[key]))
    rotation=_zero_moment_rotation(record,active)
    missing.extend(rotation['missing'])
    calculation=arithmetic.interaction(combo,span_mm,capacities)
    lower_only=any(t.get('denominator_lower_bound_only') for t in trace.values())
    inconclusive_floor=not missing and lower_only and calculation['criterion_status']!='meets'
    return dict(schema=SCHEMA,source=SOURCE,source_binding=copy.deepcopy(own['source_binding']),
        material=copy.deepcopy(material),physical_span_mm=span_mm,
        combination_id=record['combination_id'],load_position_by_axis=copy.deepcopy(record['load_position_by_axis']),
        selection=trace,missing=missing,arithmetic=calculation,zero_moment_rotation_guard=rotation,
        status='pending_actual_member_components' if missing else 'inconclusive_resistance_floor' if inconclusive_floor else 'component_computed',
        criterion_status=calculation['criterion_status'] if not missing and not inconclusive_floor else None,
        denominator_lower_bound_only=lower_only,floor_exceeded_means='inconclusive_not_failed',
        approximate_elastic_references=any(p['approximate'] for t in trace.values() for p in t['selected']),
        own_contour_only=True,nominal_reference_mixed=False,N_N=0.,
        primary_torsion_assessed=False,shear_interaction_assessed=False,
        combined_ELS_assessed=False,whole_member_approved=False)
