"""Pure positive-My arithmetic contract; not a resistance qualification.

Only the separately qualified consumer may bind positive_capacity_Nmm to the minimum
of the OWN Ue125 local/Annex E evidence and its distortional applicability.
It must independently retain the per-action roof_biaxial classifier. A positive
net My does not qualify action positions. Existing contracts remain untouched.
"""
import copy
import math
import json

SCHEMA = 'roof_positive_My_arithmetic_v1'
SCOPE = ('Certificado aritmético N=0 de |Mx|/Rx + My/Ry, somente My>=0 em todo '
         'o vão. Não qualifica resistências, posição das ações, distorção, torção '
         'ou aprovação global. Qualificação normativa pertence ao consumidor separado.')
_FLAGS = dict(arithmetic_only=True, resistance_qualified=False,
              action_positions_qualified=False, primary_torsion_assessed=False,
              whole_member_approved=False)


def _safe(value):
    json.dumps(value, sort_keys=True, allow_nan=False)
    return value


def _same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _number(value, name, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0)):
        raise ValueError('Valor inválido: ' + name)
    return value


def _inputs(combo, L, rx):
    _number(L, 'vão físico', True)
    _number(rx, 'resistência forte', True)
    a = _number(combo['x_mm'], 'posição P')
    if not 0 <= a <= L:
        raise ValueError('Posição P fora do vão físico.')
    for key in ('q_vector', 'P_vector'):
        for axis in ('normal', 'parallel'):
            _number(combo[key][axis], key + ':' + axis)


def _coefficients(combo, L, after, axis):
    q, p, a = combo['q_vector'][axis], combo['P_vector'][axis], combo['x_mm']
    return [-q / 2, q * L / 2 + p * (L - a) / L - (p if after else 0),
            p * a if after else 0]


def _pieces(combo, L):
    a = combo['x_mm']
    return [(lo, hi, after) for lo, hi, after in
            ((0., a, False), (a, L, True)) if lo < hi]


def _stations(co, lo, hi):
    xs = [lo, hi]
    if co[0]:
        vertex = -co[1] / (2 * co[0])
        if lo < vertex < hi:
            xs.append(vertex)
    return xs


def _value(co, x):
    return (co[0] * x + co[1]) * x + co[2]


def _sign_proof(combo, L):
    proof = []
    for lo, hi, after in _pieces(combo, L):
        co = _coefficients(combo, L, after, 'parallel')
        xs = _stations(co, lo, hi)
        # Exact simply supported boundary identity, not a tolerance clamp.
        values = [0. if x in (0., L) else _value(co, x) for x in xs]
        proof.append(dict(start_mm=lo, end_mm=hi, after_P=after,
                          coefficients=co, candidate_x_mm=xs,
                          minimum_My_Nmm=min(values), maximum_My_Nmm=max(values)))
    return proof


def _state(x, combo, L, rx, ry):
    after = x > combo['x_mm']
    mx = 0. if x in (0., L) else _value(_coefficients(combo, L, after, 'normal'), x)
    my = 0. if x in (0., L) else _value(_coefficients(combo, L, after, 'parallel'), x)
    return dict(x_mm=x, Mx_Nmm=mx, My_Nmm=my,
                index=abs(mx) / rx + (my / ry if ry is not None else 0.))


def interaction(combo, L, strong_capacity_Nmm, positive_capacity_Nmm=None):
    """Return proof or explicit negative/positive-capacity pending state.

    Continuous sign is established by both endpoints and the interior vertex of
    EVERY piece, never by a grid, maximum alone, or force netting. A demand that
    is identically zero needs no weak resistance. No negative capacity exists in
    this contract. Supplied capacities are arithmetic inputs, not qualifications.
    """
    _inputs(combo, L, strong_capacity_Nmm)
    proof = _sign_proof(combo, L)
    minimum = min(row['minimum_My_Nmm'] for row in proof)
    maximum = max(row['maximum_My_Nmm'] for row in proof)
    # Require the zero polynomial, not numerical endpoint cancellation.
    zero = all(all(v == 0 for v in row['coefficients']) for row in proof)
    ry = None if zero else positive_capacity_Nmm
    missing = ['weak_negative'] if minimum < 0 else ['weak_positive'] if ry is None and not zero else []
    if ry is not None:
        _number(ry, 'resistência fraca positiva', True)
    base = dict(schema=SCHEMA, scope=SCOPE, **_FLAGS, span_mm=L,
                strong_capacity_Nmm=strong_capacity_Nmm,
                positive_capacity_Nmm=ry, My_identically_zero=zero,
                minimum_My_Nmm=minimum, maximum_My_Nmm=maximum,
                sign_certificate=proof, missing=missing)
    if missing:
        return _safe(dict(base, status='not_evaluated', governing=None,
                    envelope_certificate=[], candidate_count=0,
                    arithmetic_criterion_status=None))
    certificate = []
    for lo, hi, after in _pieces(combo, L):
        mx = _coefficients(combo, L, after, 'normal')
        my = _coefficients(combo, L, after, 'parallel')
        for sx in (-1, 1):
            co = [sx * u / strong_capacity_Nmm + (v / ry if ry is not None else 0.)
                  for u, v in zip(mx, my)]
            certificate.append(dict(start_mm=lo, end_mm=hi, after_P=after,
                                    strong_sign=sx, coefficients=co,
                                    candidate_x_mm=_stations(co, lo, hi)))
    xs = sorted({x for row in certificate for x in row['candidate_x_mm']})
    governing = max((_state(x, combo, L, strong_capacity_Nmm, ry) for x in xs),
                    key=lambda state: state['index'])
    return _safe(dict(base, status='computed_arithmetic_only', governing=governing,
                envelope_certificate=certificate, candidate_count=len(xs),
                arithmetic_criterion_status='meets' if governing['index'] <= 1 else 'fails'))


def validate_saved(record, combo, L, strong_capacity_Nmm, positive_capacity_Nmm=None):
    """Independent proof checks, never producer call or resistance/source solve.

    A new outer hash cannot legitimize a forged maximum, truncated inventory,
    omitted negative interior, resistance swap, or altered domain flags.
    """
    _inputs(combo, L, strong_capacity_Nmm)
    if not isinstance(record, dict):
        raise ValueError('Certificado positivo ausente.')
    if (record.get('schema') != SCHEMA or record.get('scope') != SCOPE
            or any(record.get(k) is not v for k, v in _FLAGS.items())
            or record.get('span_mm') != L
            or record.get('strong_capacity_Nmm') != strong_capacity_Nmm):
        raise ValueError('Contrato aritmético positivo divergente.')
    _safe(record)
    expected_keys = set(_FLAGS) | {'schema','scope','span_mm','strong_capacity_Nmm','positive_capacity_Nmm',
        'My_identically_zero','minimum_My_Nmm','maximum_My_Nmm','sign_certificate','missing',
        'status','governing','envelope_certificate','candidate_count','arithmetic_criterion_status'}
    if set(record) != expected_keys or type(record.get('candidate_count')) is not int:
        raise ValueError('Campos/tipos extras no certificado positivo.')
    for key in ('span_mm','strong_capacity_Nmm','positive_capacity_Nmm','minimum_My_Nmm','maximum_My_Nmm'):
        if record.get(key) is not None:
            _number(record[key], key)
    a = combo['x_mm']
    pieces = [(lo, hi, after) for lo, hi, after in
              ((0., a, False), (a, L, True)) if lo < hi]
    proof = record.get('sign_certificate')
    if not isinstance(proof, list) or len(proof) != len(pieces):
        raise ValueError('Inventário de sinal positivo incompleto.')
    matrices = []
    lows, highs = [], []
    for row, (lo, hi, after) in zip(proof, pieces):
        axes = []
        for axis in ('normal', 'parallel'):
            q, p = combo['q_vector'][axis], combo['P_vector'][axis]
            axes.append([-q / 2, q * L / 2 + p * (L - a) / L - (p if after else 0),
                         p * a if after else 0])
        mx, my = axes
        xs = [lo, hi]
        if my[0]:
            vertex = -my[1] / (2 * my[0])
            if lo < vertex < hi:
                xs.append(vertex)
        values = [0. if x in (0., L) else (my[0] * x + my[1]) * x + my[2] for x in xs]
        expected = dict(start_mm=lo, end_mm=hi, after_P=after,
                        coefficients=my, candidate_x_mm=xs,
                        minimum_My_Nmm=min(values), maximum_My_Nmm=max(values))
        if not _same(row, expected):
            raise ValueError('Prova contínua de sinal My adulterada.')
        lows.append(min(values)); highs.append(max(values))
        matrices.append((lo, hi, after, mx, my))
    zero = all(all(v == 0 for v in row[4]) for row in matrices)
    ry = None if zero else positive_capacity_Nmm
    if ry is not None:
        _number(ry, 'resistência fraca positiva salva', True)
    missing = ['weak_negative'] if min(lows) < 0 else ['weak_positive'] if ry is None and not zero else []
    if (record.get('minimum_My_Nmm') != min(lows) or record.get('maximum_My_Nmm') != max(highs)
            or record.get('My_identically_zero') is not zero
            or record.get('positive_capacity_Nmm') != ry or record.get('missing') != missing):
        raise ValueError('Domínio/capacidade positiva alterados.')
    if missing:
        if any(record.get(k) != v for k, v in dict(status='not_evaluated', governing=None,
                envelope_certificate=[], candidate_count=0, arithmetic_criterion_status=None).items()):
            raise ValueError('Pendência positiva promovida indevidamente.')
        return copy.deepcopy(record)
    certificate = record.get('envelope_certificate')
    if not isinstance(certificate, list) or len(certificate) != 2 * len(pieces):
        raise ValueError('Inventário de envelope positivo incompleto.')
    stations = set()
    for i, (lo, hi, after, mx, my) in enumerate(matrices):
        for j, sx in enumerate((-1, 1)):
            co = [sx * u / strong_capacity_Nmm + (v / ry if ry is not None else 0.)
                  for u, v in zip(mx, my)]
            xs = [lo, hi]
            if co[0]:
                vertex = -co[1] / (2 * co[0])
                if lo < vertex < hi:
                    xs.append(vertex)
            if not _same(certificate[2 * i + j], dict(start_mm=lo, end_mm=hi, after_P=after,
                    strong_sign=sx, coefficients=co, candidate_x_mm=xs)):
                raise ValueError('Cobertura dos dois polinômios adulterada.')
            stations.update(xs)
    def state(x):
        # Independent concomitant moment identity; no producer helper.
        after = x > a
        values = []
        for axis in ('normal', 'parallel'):
            q, p = combo['q_vector'][axis], combo['P_vector'][axis]
            A, B, C = -q / 2, q * L / 2 + p * (L - a) / L - (p if after else 0), p * a if after else 0
            values.append(0. if x in (0., L) else (A * x + B) * x + C)
        mx, my = values
        return dict(x_mm=x, Mx_Nmm=mx, My_Nmm=my,
                    index=abs(mx) / strong_capacity_Nmm + (my / ry if ry is not None else 0.))
    g = record.get('governing')
    if not isinstance(g, dict):
        raise ValueError('Testemunha positiva malformada.')
    _number(g.get('x_mm'), 'seção governante')
    if g['x_mm'] not in stations:
        raise ValueError('Testemunha fora do inventário positivo.')
    expected = state(g['x_mm'])
    if not _same(g, expected):
        raise ValueError('Testemunha concomitante adulterada.')
    for x in stations:
        if state(x)['index'] > g['index']:
            raise ValueError('Testemunha não cobre máximo contínuo positivo.')
    if (record.get('candidate_count') != len(stations)
            or record.get('status') != 'computed_arithmetic_only'
            or record.get('arithmetic_criterion_status') != ('meets' if g['index'] <= 1 else 'fails')):
        raise ValueError('Conclusão/inventário aritmético positivo adulterados.')
    return copy.deepcopy(record)
