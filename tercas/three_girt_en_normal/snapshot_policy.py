"""Decision provenance, separate from immutable saved numerical observations.

A digest proves identity, not that an upper bound encloses a physical field.
Older snapshots remain readable; only a new explicitly requested calculation
can produce the versioned replay proof. No legacy schema is silently promoted.
"""
SCHEMA = 'EN_saved_decision_authentication_v1'
CERTIFIED_SCHEMAS = ('three_girt_EN_middle_normal_shear_certified_v6',
                     'three_girt_EN_normal_shear_certified_v6')
PENDING = 'pending_saved_EN_decision_authentication'
NOTICE = ('Registro histórico EN sem prova verificável dos limites e das testemunhas. '
          'Os números e observações salvos foram preservados, mas não demonstram '
          'atendimento ou excesso autenticado nesta leitura. Solicite explicitamente '
          'um novo cálculo para obter a verificação atual; abrir ou exportar não recalcula o modelo.')


def certified(component):
    # The source reader must verify every proof and witness before presenting
    # this schema. A marker or a rewritten hash is never its validation.
    return component.get('schema') in CERTIFIED_SCHEMAS


def decision(component, saved):
    if not certified(component) and saved and saved.startswith(('within_1', 'above_1')):
        return PENDING
    return saved


def verify_assessment(component, assessment, members):
    if certified(component):return
    checks=list(assessment.get('checks', []))
    checks.extend(check for group in assessment.get('groups', [])
                  if group['id']=='EN_section' for check in group['checks'])
    if any(check['id'].startswith('EN:') and check['status'] in ('meets','fails','failed')
           for check in checks):
        raise ValueError('Panorama EN histórico sem autenticação das decisões; monte novamente o panorama. Os números salvos não serão recalculados.')
