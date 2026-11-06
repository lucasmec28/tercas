"""Own Ue125 positive-only route, separated from archived catalogue v1/v2.

This consumer does not infer action applicability from net moment. The caller
must supply the preserved per-action classifier, whose linked roof evidence is
validated before this module. No new supports or strong-axis solve are made.
"""
import copy
from . import roof_biaxial_positive as arithmetic

KIND = 'own_catalog_Ue125_positive_bending_components_v3'
SCHEMA = 'NBR_9_9_own_Ue125_positive_roof_v1'
SOURCE = 'NBR14762:2010 §§9.8.2 e 9.9, Anexo E; aplicabilidade D pura positiva AISI RP21-01 pp10–11.'
SCOPE = ('Interação §9.9 N=0, My não negativo em todo trecho, capacidades próprias '
         'do Ue125: mínimo forte local/FLT com altura/D aproximado e mínimo fraco '
         'positivo local/Anexo E, Cm=1. Não aproveita posição estabilizante. '
         'D convencional não aplicável somente à referência pura fraca positiva; '
         'D forte integra a resistência forte. A referência uniaxial positiva é usada em §9.9; '
         'isso não verifica torção, grandes giros, aplicabilidade física ou aprovação global.')


def decorate_section(source, data):
    if not source.get('strong_bending_complete'):
        return source
    from .ue_catalog_nbr_weak_positive import qualify_reference
    positive = qualify_reference(data, sign='positive', axial_force_N=0.)
    if positive is None:
        return source
    out = copy.deepcopy(source)
    out.update(kind=KIND, biaxial_qualified=False,
               positive_biaxial_route=True, weak_positive_reference=positive,
               distortion_scope=SCOPE)
    return out


def validate_section(saved, original, data):
    from .ue_catalog_nbr_weak_positive import validate_saved
    positive = saved.get('weak_positive_reference')
    validate_saved(positive, data)
    expected = copy.deepcopy(original)
    expected.update(kind=KIND, biaxial_qualified=False,
                    positive_biaxial_route=True, weak_positive_reference=positive,
               distortion_scope=SCOPE)
    if not original.get('strong_bending_complete') or not arithmetic._same(saved, expected):
        raise ValueError('Fonte própria positiva diverge da componente forte/contrato v3.')


def _capacity(source):
    return source['weak_positive_reference']['MRd_positive_reference_Nmm']


def _wrap(proof):
    return dict(schema=SCHEMA, source=SOURCE, scope=SCOPE, status='computed_fixed_position', missing=[],
                governing=copy.deepcopy(proof['governing']), candidate_count=proof['candidate_count'],
                criterion_status=proof['arithmetic_criterion_status'],
                strong_capacity_Nmm=proof['strong_capacity_Nmm'],
                weak_axis_capacities={'positive': {'MRd_Nmm': proof['positive_capacity_Nmm']}},
                positive_arithmetic_certificate=copy.deepcopy(proof),
                weak_distortional_floor_can_govern=False,
                combined_buckling_eigenvalue=False, primary_torsion_assessed=False,
                whole_member_approved=False)


def fields(combo, L, strong, source, position_scope):
    if position_scope.get('applicable') is not True:
        return {}
    proof = arithmetic.interaction(combo, L, strong, _capacity(source))
    if proof['missing']:
        return dict(biaxial_pending=dict(status='not_evaluated', index=None,
            missing=proof['missing'],
            reason='My negativo em algum trecho: resistência própria negativa ainda pendente; nenhum índice §9.9 emitido.',
            positive_arithmetic_certificate=proof, whole_member_approved=False))
    return dict(biaxial=_wrap(proof))


def validate_fields(record, combo, L, strong, source, position_scope):
    """No fresh producer, eigenproblem or source lookup at preserved boundary."""
    applicable = position_scope.get('applicable') is True
    active, pending = 'biaxial' in record, 'biaxial_pending' in record
    if not applicable:
        if active or pending:
            raise ValueError('Interação positiva sem classificação individual das ações.')
        return
    if active == pending:
        raise ValueError('Inventário positivo ausente/duplicado.')
    item = record['biaxial' if active else 'biaxial_pending']
    if not isinstance(item, dict):
        raise ValueError('Registro positivo malformado.')
    proof = item.get('positive_arithmetic_certificate')
    arithmetic.validate_saved(proof, combo, L, strong, _capacity(source))
    if active:
        if proof['missing'] or not arithmetic._same(item, _wrap(proof)):
            raise ValueError('Interação positiva promovida/alterada.')
    else:
        expected = dict(status='not_evaluated', index=None, missing=['weak_negative'],
            reason='My negativo em algum trecho: resistência própria negativa ainda pendente; nenhum índice §9.9 emitido.',
            positive_arithmetic_certificate=proof, whole_member_approved=False)
        if proof['missing'] != ['weak_negative'] or not arithmetic._same(item, expected):
            raise ValueError('Pendência negativa omitida/alterada.')
