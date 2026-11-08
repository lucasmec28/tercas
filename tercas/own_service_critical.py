"""Fresh-only Table 12(b) critical for local scalar service, never ELU/FLT.

Historical inputs without the explicit local mode keep their original route.
This evidence is frozen in the consumed spec; rendering does not recompute it.
"""
from . import ue_catalog_reference as own
from .deflection_scope import enabled
from .core.local_table12 import local_critical


def qualify(data):
    if not own.claims_reference(data) or not enabled(data):
        return None
    binding = own.source_binding(data)
    p = data['properties']
    W = p['Ix_cm4'] * 1e4 / (p['h'] / 2.)
    evidence = dict(schema='own_Ue_local_service_Table12b_v1',
        source_binding=binding, model_domain=data['model_domain'],
        nominal_dimensions_mm={k:p[k] for k in ('h','bf','lip','t')},
        geometric_properties=own._properties(own.validate(data)),
        E_MPa=p['E_MPa'], formula_nu=.3,
        formula_nu_origin='Parâmetro explícito da fórmula, não inferido de G ou de Pierin.',
        Wc_mm3=W, Ig_mm4=p['Ix_cm4']*1e4,
        exterior_fibre_distance_mm=p['h']/2.,
        use_scope='isolated_local_strong_axis_service_only',
        inherited_criticals_used=False, strength_denominators_changed=False,
        combined_ELS_approved=False, whole_member_approved=False)
    try:
        local = local_critical('Ue',p['h'],p['bf'],p['t'],W,p['E_MPa'],nu=.3,D_mm=p['lip'])
    except ValueError as exc:
        evidence.update(status='outside_Table12b_domain',reason=str(exc))
        scalar = dict(value=None,origin='NBR14762:2010 Tabela12(b)',reason=str(exc))
    else:
        evidence.update(status='computed_own_contour_Table12b',formula=local)
        scalar = dict(value=local['Ml_Nmm'],origin=local['origin'])
    evidence['snapshot_sha256'] = own.digest(evidence)
    scalar['evidence'] = evidence
    return scalar


def for_spec(spec):
    """Reject accidental transplantation into an unrelated core spec."""
    from .deflection_scope import MODE
    scalar = spec['Ml_SLS']
    ev = scalar.get('evidence', {})
    if (spec.get('deflection_model') != MODE
            or ev.get('schema') != 'own_Ue_local_service_Table12b_v1'
            or ev.get('use_scope') != 'isolated_local_strong_axis_service_only'
            or ev.get('snapshot_sha256') != own.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})):
        raise ValueError('Snapshot Ml de serviço incompatível com o modelo local.')
    domain = spec.get('model_domain_evidence', {})
    if domain.get('version') != ev['model_domain'] or domain.get('conflict') or domain.get('status') != 'fixed_model_domain':
        raise ValueError('Domínio de Ml de serviço incompatível.')
    binding = ev['source_binding']
    fields = spec['selected_section']['fields']
    props = ev['geometric_properties']
    if (binding['properties_sha256'] != own.digest(props)
            or binding['material_sha256'] != own.digest(binding['material'])
            or any(fields[k]['value'] != v for k,v in props.items())
            or any(fields[k]['value'] != v for k,v in binding['material'].items())
            or ev['E_MPa'] != fields['E_MPa']['value']
            or ev['formula_nu'] != .3
            or ev['Wc_mm3'] != fields['Ix_cm4']['value']*1e4/(fields['h']['value']/2.)):
        raise ValueError('Contorno/material de Ml de serviço divergente do snapshot consumido.')
    # Hashes detect accidental damage, not authorization. Recheck this cheap
    # formula against consumed fields so a coherent rehash cannot forge Ml.
    try:
        fresh = local_critical('Ue',fields['h']['value'],fields['bf']['value'],
            fields['t']['value'],ev['Wc_mm3'],fields['E_MPa']['value'],
            nu=.3,D_mm=fields['lip']['value'])
    except ValueError:
        if ev.get('status') != 'outside_Table12b_domain' or 'formula' in ev:
            raise ValueError('Promoção indevida fora da Tabela12(b).')
        expected = None
    else:
        if ev.get('status') != 'computed_own_contour_Table12b' or ev.get('formula') != fresh:
            raise ValueError('Fórmula Ml de serviço divergente da Tabela12(b).')
        expected = fresh['Ml_Nmm']
    if scalar.get('value') != expected:
        raise ValueError('Ml de serviço divergente da evidência consumida.')
    return scalar
