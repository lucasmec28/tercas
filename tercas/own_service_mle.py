"""Bound fresh-only MLE service adapter; no artificial Ml or ELU changes."""
import copy
from . import ue_catalog_reference as own
from .nbr_service_strong_mle import INDICES, SOURCE, peak_deflection


def qualify(service_critical):
    ev=service_critical['evidence']
    if (ev['status']!='outside_Table12b_domain'
            or ev['source_binding']['catalog_index'] not in INDICES):return None
    out=dict(schema='own_Ue_local_service_MLE_v1',
        source_binding=copy.deepcopy(ev['source_binding']),
        service_critical_snapshot_sha256=ev['snapshot_sha256'],
        source=copy.deepcopy(SOURCE), use_scope='isolated_local_strong_axis_service_only',
        local_elastic_critical_inferred=False, strength_denominators_changed=False,
        whole_member_approved=False)
    out['snapshot_sha256']=own.digest(out)
    return out


def evaluate(spec):
    from .own_service_critical import for_spec
    critical=for_spec(spec)
    ev=spec['MLE_SLS']
    if ev!=qualify(critical):
        raise ValueError('Snapshot MLE de serviço incompatível com contorno/material e escopo consumidos.')
    binding=ev['source_binding']
    packet=own._source(binding['catalog_index'])
    identity=own._identity(packet,binding['catalog_index'],
        'wall_girt' if binding.get('schema')==own.GIRT_SCHEMA else 'purlin')
    if (any(binding.get(k)!=v for k,v in identity.items())
            or critical['evidence']['geometric_properties']!=own._properties(packet)):
        raise ValueError('Identidade geométrica MLE divergente do contorno próprio utilizado.')
    material=dict(
        {k:binding['material'][k] for k in ('E_MPa','G_MPa','fy_MPa')},nu=.3,gamma=1.1)
    sls=spec['SLS']
    result=peak_deflection(binding['catalog_index'],L_mm=spec['L_mm'],
        q_Nmm=sls['q_Nmm'],P_N=sls['P_N'],a_mm=sls['x_mm'],material=material)
    return dict(status='computed_bending_component',x_mm=result['peak_x_mm'],
        deflection_mm=result['deflection_mm'],same_span_mm=spec['L_mm'],
        model='Euler-Bernoulli local strong bending with pointwise service MLE Ixef(M)',
        service_mle_evidence=dict(input=copy.deepcopy(ev),calculation=result),
        section_property_convention_pending=spec['selected_section']['source_geometry_convention_unresolved'],
        criterion_scope='bending component only, not complete system ELS approval')
