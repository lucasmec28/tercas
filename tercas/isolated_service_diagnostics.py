"""Explain an already authenticated gross-service screen; no new check.

The caller authenticates the saved component before presentation. This module
neither evaluates stresses nor promotes a result or prescribes a reduced model.
"""

WALLS = (
    ('bottom_lip', 'lábio inferior'),
    ('bottom_flange', 'mesa inferior'),
    ('web', 'alma'),
    ('top_flange', 'mesa superior'),
    ('top_lip', 'lábio superior'),
)


def explain(comparison):
    """Return display-only detail, preserving v1/v2/v3 arithmetic and verdicts.

    Inconclusive wall sufficiency is not evidence of actual width loss. An
    elastic upper bound above fy likewise does not establish an actual excess.
    Only recorded booleans are read; diagnostic ratios never become indices.
    """
    screen = comparison.get('gross_screen', {})
    rows = screen.get('walls', [])
    if (not isinstance(rows, list) or len(rows) != len(WALLS)
            or any(not isinstance(row, dict) for row in rows)
            or [row.get('name') for row in rows] != [name for name, _ in WALLS]
            or any(type(row.get('sufficient')) is not bool for row in rows)
            or type(screen.get('elastic_field_sufficient')) is not bool):
        return {'Detalhe do crivo salvo': 'Detalhamento completo das cinco paredes e da guarda elástica não registrado.'}

    unresolved = [label for row, (_, label) in zip(rows, WALLS) if not row['sufficient']]
    elastic = screen['elastic_field_sufficient']
    detail = {
        'Crivo local inconclusivo em': ', '.join(unresolved) if unresolved else 'Nenhuma parede neste crivo suficiente',
        'Guarda elástica do campo bruto': (
            'Limite superior de von Mises ≤ fy' if elastic else
            'Limite superior de von Mises > fy; suficiência elástica não demonstrada'),
    }
    if unresolved:
        detail['Alcance da pendência'] = (
            'O crivo não conclui integralidade dessas paredes; não demonstra redução real ou falha. '
            'A implementação ainda não calcula a seção efetiva compatível com Mx+My+B. '
            'O deslocamento bruto permanece diagnóstico, sem índice. '
            'A flecha MSE uniaxial é uma componente separada e não substitui esse cálculo combinado.')
    elif not elastic:
        detail['Alcance da pendência'] = (
            'As cinco paredes passam no crivo local, mas a guarda elástica adotada pelo aplicativo '
            'não conclui suficiência do campo bruto. Isso não demonstra falha física nem é uma '
            'exigência normativa adicional. Uma seção reduzida não resolve automaticamente essa pendência.')
    return detail
