"""Own Ue strong-axis MSE certificate, separate from inherited criticals.

Qualification is deliberately limited to one public nominal contour/material.
Table 12 uses nominal dimensions. The v2 certificate adds a separately reviewed
approximate elastic Mdist, not a Table 14 exemption or a weak-axis resistance.
Historical v1 partial snapshots remain readable without migration.
"""
import copy
import math

from . import ue_catalog_reference as own
from .core.local_table12 import local_critical
from .core.ue_nbr import table14

FIELD = 'ue_catalog_nbr_bending_evidence'
SCHEMA_V1 = 'ue_catalog_nbr_bending_v1'
SCHEMA = 'ue_catalog_nbr_bending_v2'
SOURCE = 'ABNT NBR 14762:2010 §§9.3, 9.8.2.1(b), 9.8.2.3; Tabelas 12(b) e 14'
FORMULA_NU = .3
GAMMA = 1.1
MATERIAL = dict(E_MPa=200000., G_MPa=77000., fy_MPa=300., fu_MPa=400.)
GEOMETRY = dict(h=125, bf=50, lip=17, t=2, ri_mm=2,
    A_cm2=4.916953270111933, mass_kg_m=3.859808317037867,
    Ix_cm4=118.12876899091285, Iy_cm4=17.044494310055477,
    Wx_cm3=18.900603038546056, J_mm4=655.5937693482578,
    Cw_mm6=569368182.448454)
PIN = dict(schema=own.SCHEMA, catalog_index=26, catalog_id='planilha_v03_r31',
    geometry_schema='pierin_nominal_torsion_geometry_v1',
    nominal_identity_sha256='980dc2f8d7fbf830fcdae22160f06a103c576fccccde62525824795dfe18c716',
    nodes_sha256='3814f4cd9fcfa474b6e3fcbd21eedb3fdee38818eca0440abb4408fd506143e2',
    section_profile_id='OWN_PIERIN_NOMINAL_planilha_v03_r31_980dc2f8d7fbf830',
    properties_sha256='7576f160b8cf970eb46e0ea4e01d8bbe752e70e4f1999059d481b770fca02f4d',
    material_sha256='6dd10ebc19ece54e2c8c99d65d2d5a49e91ef8bc267515d695379746b27c02d5',
    density_kg_m3=7850.)
SOURCE_DOCUMENTS = [
    dict(title=SOURCE, role='Normative calculation; existing reviewed Table 12/14 implementations'),
    dict(title='CBCA, Steel Framing: Engenharia, 2ª edição, 2016, pp.73–77',
         url='https://www.skylightestruturas.com.br/downloads/101497_manual_lsf_engenharia_2016.pdf',
         role='Independent explanation of MSE, elastic criticals and Table 14 scope'),
]
DISTORTIONAL_REASON = (
    'Tabela 14 não dispensa: D/bw=0,136 < 0,2175 para bf/bw=0,4 e bw/t=62,5. '
    'Mdist compatível ainda não qualificado. §9.3 admite análise de estabilidade '
    'elástica ou formulação direta aproximada com correlação adequada; não exige '
    'especificamente FEM. Ml, crítico de outra seção e resistência EN/AISI não '
    'substituem Mdist. Ausência de dispensa não significa reprovação.')
WEAK_REASON = (
    'Tabela 12(b) e dispensa da Tabela 14 são limitadas à flexão forte. '
    'Não se transferem ao eixo fraco nem aos dois lados comprimidos.')


def _saved_binding(data):
    """Verify the exact packaged scalar identity without reopening any source."""
    # Recheck the same semantic domain as fresh own-contour validation. These
    # checks inspect declarations only; they do not prepare geometry or solve.
    version = own._domain(data)
    if (data.get('model_domain') != version
            or any(key in data for key in own.OLD_REFERENCE_FIELDS)):
        raise ValueError('Domínio/referências do certificado NBR próprio alterados.')
    marker = data.get(own.FIELD)
    if not isinstance(marker, dict):
        raise ValueError('Certificado NBR exige marcador do contorno próprio.')
    marker_fields = set(PIN) | {'material', 'geometric_properties',
        'superseded_section_inputs', 'old_criticals_inactive', 'whole_member_approved'}
    if (set(marker) != marker_fields
            or not isinstance(marker.get('superseded_section_inputs'), dict)):
        raise ValueError('Marcador do certificado NBR próprio malformado.')
    binding = {key: copy.deepcopy(marker.get(key)) for key in PIN}
    binding['material'] = copy.deepcopy(marker.get('material'))
    if any(binding[key] != value for key, value in PIN.items()):
        raise ValueError('Certificado NBR fora do contorno próprio qualificado.')
    if (data.get('catalog_index') != PIN['catalog_index']
            or binding['material'] != MATERIAL or own.material(data) != MATERIAL
            or marker.get('material_sha256') != own.digest(marker.get('material'))
            or marker.get('properties_sha256') != own.digest(marker.get('geometric_properties'))
            or marker.get('geometric_properties') != GEOMETRY
            or any(not own._same(data['properties'].get(key), value)
                   for key, value in GEOMETRY.items())
            or marker.get('old_criticals_inactive') is not True
            or marker.get('whole_member_approved') is not False):
        raise ValueError('Contorno/material do certificado NBR alterado.')
    return binding


def _certificate_v1(binding):
    """Immutable historical partial replay. Never promote a saved v1 result."""
    p = GEOMETRY
    # Exterior fibre, not the more favourable midsurface extreme h/2-t/2.
    W = p['Ix_cm4'] * 1e4 / (p['h'] / 2.)
    local = local_critical('Ue', p['h'], p['bf'], p['t'], W,
                           E_MPa=MATERIAL['E_MPa'], nu=FORMULA_NU, D_mm=p['lip'])
    lam = math.sqrt(W * MATERIAL['fy_MPa'] / local['Ml_Nmm'])
    rho = 1. if lam <= .673 else (1. - .22 / lam) / lam
    local.update(status='computed', W_mm3=W, Wc_mm3=W, Wef_mm3=rho * W,
        MRd_Nmm=rho * W * MATERIAL['fy_MPa'] / GAMMA,
        MRd_local_Nmm=rho * W * MATERIAL['fy_MPa'] / GAMMA,
        lambda_local=lam, rho_local=rho, gamma=GAMMA, formula_nu=FORMULA_NU,
        formula_E_MPa=MATERIAL['E_MPa'],
        formula_nu_origin='Parâmetro explícito da fórmula NBR; não deduzido do G arredondado.',
        nominal_dimensions_mm={key: p[key] for key in ('h', 'bf', 'lip', 't')},
        exterior_fibre_distance_mm=p['h'] / 2., signs=['positive', 'negative'],
        geometry_basis='Mesmo Ix do contorno próprio; dimensões nominais na Tabela 12(b).',
        method='MSE_Table12b_nominal_dimensions', modal_critical_computed=False,
        symmetric_strong_axis=True, whole_member_approved=False)
    t14 = table14(p['h'], p['bf'], p['lip'], p['t'])
    t14.update(bf_bw=p['bf']/p['h'], bw_t=p['h']/p['t'],
               required_D_mm=t14['required_D_bw']*p['h'])
    # A future scope expansion must supply a new, reviewed D decision.
    if t14['exempt'] is not False:
        raise ValueError('Decisão distorcional do certificado NBR mudou.')
    out = dict(schema=SCHEMA_V1, status='partial_strong_local_only',
        reference_id=PIN['section_profile_id']+'_NBR_MSE_fy300_v1',
        source=SOURCE, source_documents=copy.deepcopy(SOURCE_DOCUMENTS),
        source_binding=copy.deepcopy(binding), model=dict(MATERIAL, formula_nu=FORMULA_NU),
        strong=dict(local=local, distortional=dict(status='not_evaluated',
            table14=t14, Mdist_Nmm=None, MRd_Nmm=None, MRd_dist_Nmm=None,
            reason=DISTORTIONAL_REASON, exemption=False)),
        weak={side: dict(status='not_evaluated', MRd_Nmm=None, reason=WEAK_REASON)
              for side in ('web', 'lips')},
        inherited_criticals_used=False, complete_bending_capacity_qualified=False,
        combined_stress_qualified=False, whole_member_approved=False)
    out['snapshot_sha256'] = own.digest(out)
    return out


def _certificate(binding, data):
    """New calculation uses v2; weak/biaxial capacities remain unqualified."""
    from . import ue_catalog_nbr_distortional as dist
    out = _certificate_v1(binding)
    supported = dist.supports_member_length(data)
    out.update(schema=SCHEMA, status='strong_local_distortional_qualified',
        reference_id=PIN['section_profile_id']+'_NBR_MSE_approxD_fy300_v2',
        strong_bending_complete=supported, biaxial_qualified=False)
    out['source_documents'] += copy.deepcopy(dist.SOURCE_DOCUMENTS)
    if not supported:
        out['status'] = 'partial_strong_local_only'
        out['strong']['distortional'].update(status='not_evaluated',
            reason=dist.SHORT_MEMBER_REASON, length_scope='member_shorter_than_qualified_halfwave',
            required_minimum_member_length_mm=dist._elastic()['Lcrd_mm'])
        out.pop('snapshot_sha256')
        out['snapshot_sha256'] = own.digest(out)
        return out
    d = dist._certificate(binding)
    out['strong']['distortional'].update(status='computed_approximate',
        Mdist_Nmm=d['elastic']['Mdist_Nmm'], MRd_Nmm=d['resistance']['MRd_dist_Nmm'],
        MRd_dist_Nmm=d['resistance']['MRd_dist_Nmm'],
        origin=dist.SOURCE, elastic_approximation=True, analytical_evidence=d,
        reason=('Sem dispensa Tabela 14. Mdist aproximado pelo método elástico geral AISI2024, '
                'correlacionado e adotado conforme NBR §9.3; resistência pela curva NBR §9.8.2.3. '
                'Flexão forte pura, seção ideal sem furos e pequenos giros. '
                'Não qualifica eixo fraco, §9.9, torção/bimomento nem adequação física do modelo.'))
    out.pop('snapshot_sha256')
    out['snapshot_sha256'] = own.digest(out)
    return out


def qualify(data):
    """Return a fresh certificate or None outside this exact qualification.

    Activation is explicit in ue_catalog_reference. No input value or historical
    project is mutated. Invalid own-contour declarations still raise, fail closed.
    """
    if not own.claims_reference(data):
        return None
    binding = own.source_binding(data)
    if (any(binding.get(key) != value for key, value in PIN.items())
            or binding.get('material') != MATERIAL):
        return None
    saved = _saved_binding(data)
    if binding != saved:
        raise ValueError('Fonte atual e marcador NBR próprio divergentes.')
    return _certificate(binding, data)


def validate_saved(evidence, data):
    """Reject rehashed capacity promotion without a catalogue, mesh or solve."""
    binding = _saved_binding(data)
    if not isinstance(evidence, dict):
        raise ValueError('Evidência NBR própria malformada.')
    schema = evidence.get('schema')
    expected = (_certificate_v1(binding) if schema == SCHEMA_V1
                else _certificate(binding, data) if schema == SCHEMA else None)
    if expected is None or evidence != expected:
        raise ValueError('Evidência NBR própria alterada ou incompatível; recalcule explicitamente.')
    return copy.deepcopy(evidence)
