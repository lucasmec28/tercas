"""Experimental signed EN6.27 envelope, isolated from all released consumers.

Authority comes from a separately reviewed, immutable capacity inventory, NOT
from a candidate certificate's self-hash or from JSON submitted by a caller.
The external inventory is intentionally not installed by this module. Reading
saved results replays only polynomial/convex-envelope arithmetic, never the
network solver, geometry builder or effective-section/capacity producer.
"""
from __future__ import annotations

import copy
from fractions import Fraction as F
import hashlib
import json
import math

SCHEMA = 'EN_Ue_signed_partial_6_27_experimental_v1'
REFERENCE_SCHEMA = 'EN_Ue_catalog_signed_capacity_reference_v1'
ACTION_CONVENTION = 'N tension positive, Mx=integral(y*sigma)dA, My=-integral(x*sigma)dA'
SHEAR_METHOD = 'EN13_Table6.1_unstiffened_web_and_two_rotated_flange_webs_v1'
SOURCE = 'EN1993-1-3:2006 6.1.3(3),6.1.5,6.1.10 Eq6.27; conservative signed envelope, Mf=0'
ACTIONS = ('N', 'Mx', 'My', 'Vstrong', 'Vweak', 'Mx_original', 'My_original')
BRANCHES = ('N_tension', 'N_compression', 'Mx_positive', 'Mx_negative',
            'My_positive', 'My_negative')
MATERIAL = dict(E_MPa=210000., nu=.3, fyb_MPa=250., fya_MPa=250., gamma_M0=1.)
FALSE_FLAGS = ('whole_member_approved', 'complete_EN_design_qualified',
               'global_stability_qualified', 'torsional_interaction_qualified',
               'NBR_capacities_used', 'AISI_capacities_used',
               'runtime_release_approved', 'physical_geometry_verified',
               'pierin_criticals_transferred', 'legacy_certificates_changed')
SCOPE = ('Componente experimental N–Mx–My e dois cortantes para Ue tabulado, '
         'material EN fixo e pisos assinados de inventário qualificado externo. '
         'Cada eixo cobre separadamente momentos original e corrigido, sem crédito '
         'de cancelamento do transporte N·e. B/Tsv/Tw permanecem na EN6.1.6 '
         'concomitante, sem exigir T=0 ou converter T em V. Não aprova barra/rede.')


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _digest(value, name):
    if (type(value) is not str or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('SHA-256 explícito inválido: ' + name)
    return value


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Coeficiente real finito requerido; booleano não é ação.')
    # Integer inputs are exact, too. Floats retain their actual binary64 value.
    return F(value)


def _outward(value, direction):
    """Finite binary64 enclosure without expanding exact zero or a threshold."""
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError('Teto fora do intervalo numérico finito.') from error
    if not math.isfinite(result):
        raise ValueError('Teto fora do intervalo numérico finito.')
    actual = F(result)
    if (direction > 0 and actual < value) or (direction < 0 and actual > value):
        result = math.nextafter(result, math.inf if direction > 0 else -math.inf)
    if not math.isfinite(result):
        raise ValueError('Teto fora do intervalo numérico finito.')
    return 0. if result == 0. else result


def _pair(pair):
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError('Par de limites explícitos requerido.')
    lo, hi = map(_finite, pair)
    if lo > hi:
        raise ValueError('Limites de coeficiente invertidos.')
    return lo, hi


def _coefficients(fields):
    """Seven mandatory concurrent fields, degree <=2 on the same u in [0,1].

    Values are exact scalars, Interval objects, or explicit {'lo': [], 'hi': []}
    coefficient boxes. No small-action tolerance and no caller-supplied zero
    flag. Missing originals are never copied from the corrected moments.
    """
    if not isinstance(fields, dict) or set(fields) != set(ACTIONS):
        raise ValueError('Sete campos concomitantes explícitos requeridos.')
    normalized, rational = {}, {}
    for key in ACTIONS:
        raw = fields[key]
        if hasattr(raw, 'lo') and hasattr(raw, 'hi'):
            lo, hi = raw.lo.tolist(), raw.hi.tolist()
        elif isinstance(raw, dict) and set(raw) == {'lo', 'hi'}:
            lo, hi = raw['lo'], raw['hi']
        elif isinstance(raw, (list, tuple)):
            lo = hi = raw
        else:
            raise ValueError('Fonte polinomial explícita inválida: ' + key)
        if (not isinstance(lo, (list, tuple)) or not isinstance(hi, (list, tuple))
                or not 1 <= len(lo) == len(hi) <= 3):
            raise ValueError('Polinômio de grau até dois requerido: ' + key)
        values = [_pair([a, b]) for a, b in zip(lo, hi)]
        values += [(F(0), F(0))] * (3-len(values))
        # Keep exact supplied integers, rather than silently casting them to float.
        normalized[key] = dict(lo=list(lo)+[0.]*(3-len(lo)), hi=list(hi)+[0.]*(3-len(hi)))
        rational[key] = values
    return normalized, rational


def _bernstein(values):
    a, b, c = values
    return (a, (a[0]+b[0]/2, a[1]+b[1]/2),
            (a[0]+b[0]+c[0], a[1]+b[1]+c[1]))


def _required(axis, pair):
    lo, hi = pair
    positive, negative = (('N_tension', 'N_compression') if axis == 'N'
                          else (axis+'_positive', axis+'_negative'))
    return ([positive] if hi > 0 else []) + ([negative] if lo < 0 else [])


def _gauge(axis, pair, floors):
    """sup g over an interval, g is convex even with unequal signed floors."""
    lo, hi = pair
    names = _required(axis, pair)
    value = F(0)
    for name in names:
        magnitude = hi if name.endswith(('positive', 'tension')) else -lo
        value = max(value, magnitude / floors[name])
    return value


def _objective(intervals, floors, shear):
    normal = _gauge('N', intervals['N'], floors)
    for axis in ('Mx', 'My'):
        normal += max(_gauge(axis, intervals[axis], floors),
                      _gauge(axis, intervals[axis+'_original'], floors))
    ratios = {axis: max(abs(v) for v in intervals[key]) / F(shear[axis])
              for key, axis in (('Vstrong', 'strong'), ('Vweak', 'weak'))}
    penalty = max(max(F(0), 2*value-1)**2 for value in ratios.values())
    return dict(normal_ratio_upper=normal, strong_shear_ratio_upper=ratios['strong'],
        weak_shear_ratio_upper=ratios['weak'], shear_ratio_upper=max(ratios.values()),
        shear_penalty_upper=penalty, index_upper=normal+penalty)


def _qualified_reference(index, component_sections_sha256):
    """Only a code-owned inventory may provide authority; absent means blocked.

    Integration must install en_ue_catalog_capacity_reference.qualified_reference
    with an immutable exact index/certificate-hash inventory after independent QA.
    That provider must not build sections, repair a candidate, load caller JSON,
    infer qualification from a self-hash, or admit a different material/contour.
    """
    try:
        from .en_ue_catalog_capacity_reference import qualified_reference
    except ImportError as error:
        raise ValueError('Inventário resistente externo qualificado ainda indisponível.') from error
    return qualified_reference(index, component_sections_sha256)


def _reference(index, digest):
    if type(index) is not int or index < 0:
        raise ValueError('Índice Ue tabulado inteiro requerido.')
    _digest(digest, 'component_sections_sha256')
    ref = copy.deepcopy(_qualified_reference(index, digest))
    if not isinstance(ref, dict) or ref.get('schema') != REFERENCE_SCHEMA:
        raise ValueError('Referência resistente externa incompatível.')
    if (ref.get('catalog_index') != index or type(ref.get('catalog_index')) is not int
            or ref.get('component_sections_sha256') != digest
            or ref.get('qualification_status') != 'independently_qualified_frozen_reference'
            or ref.get('family') != 'Ue' or _sha(ref.get('material')) != _sha(MATERIAL)
            or ref.get('action_convention') != ACTION_CONVENTION
            or any(ref.get(k) is not False for k in FALSE_FLAGS)):
        raise ValueError('Referência fora do domínio Ue/material/identidade/qualificação.')
    for key in ('nominal_identity_sha256', 'nodes_sha256', 'inventory_sha256'):
        _digest(ref.get(key), key)
    for key in ('catalog_id', 'profile_id'):
        if type(ref.get(key)) is not str or not ref[key]:
            raise ValueError('Identidade nominal incompleta: ' + key)
    floors, eligible = ref.get('signed_capacity_floor'), ref.get('eligible_components')
    if (not isinstance(floors, dict) or set(floors) != set(BRANCHES)
            or not isinstance(eligible, dict) or set(eligible) != set(BRANCHES)):
        raise ValueError('Inventário dos seis ramos incompleto.')
    for key in BRANCHES:
        if type(eligible[key]) is not bool:
            raise ValueError('Elegibilidade deve ser booleana: ' + key)
        if eligible[key]:
            if type(floors[key]) is not int or floors[key] <= 0:
                raise ValueError('Piso inteiro positivo requerido: ' + key)
        elif floors[key] is not None:
            raise ValueError('Ramo ausente não pode possuir piso: ' + key)
    shear = ref.get('shear_capacity_lower_N')
    if (not isinstance(shear, dict) or set(shear) != {'strong', 'weak'}
            or any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0
                   for v in shear.values())):
        raise ValueError('Dois pisos distintos de cortante EN requeridos.')
    shear_proof = ref.get('shear_capacity_qualification')
    if (not isinstance(shear_proof, dict)
            or shear_proof.get('status') != 'independently_qualified_frozen_reference'
            or shear_proof.get('method') != SHEAR_METHOD
            or _sha(shear_proof.get('walls')) != _sha({'strong': 1, 'weak': 2})
            or shear_proof.get('nominal_identity_sha256') != ref['nominal_identity_sha256']
            or shear_proof.get('nodes_sha256') != ref['nodes_sha256']
            or _sha(shear_proof.get('material')) != _sha(MATERIAL)
            or shear_proof.get('support_stiffener_credit') is not False
            or shear_proof.get('lip_or_corner_resistance_credit') is not False):
        raise ValueError('Pisos de cortante sem qualificação própria vinculada ao contorno.')
    for key in ('source_sha256', 'inventory_sha256'):
        _digest(shear_proof.get(key), 'shear_capacity_qualification.'+key)
    return ref


def _binding(source_binding, ref):
    """External caller must supply its already validated concomitant source."""
    keys = {'source_sha256', 'catalog_index', 'profile_id', 'nominal_identity_sha256',
            'nodes_sha256', 'component_sections_sha256', 'material', 'case_id', 'segment_id',
            'action_convention'}
    if not isinstance(source_binding, dict) or set(source_binding) != keys:
        raise ValueError('Vínculo externo completo da fonte concomitante requerido.')
    for key in keys-{'source_sha256', 'case_id', 'segment_id'}:
        if _sha(source_binding[key]) != _sha(ref[key]):
            raise ValueError('Fonte não corresponde à referência: ' + key)
    _digest(source_binding['source_sha256'], 'source_sha256')
    for key in ('case_id', 'segment_id'):
        if type(source_binding[key]) is not str or not source_binding[key]:
            raise ValueError('Identidade do trecho/caso requerida: ' + key)
    return copy.deepcopy(source_binding)


def polynomial_bound(fields, *, catalog_index, component_sections_sha256, source_binding):
    """Bound a validated concurrent field; never accept a caller capacity dict.

    Missing necessary normal branches return an explicit pending result with no
    numerical index. Unneeded branches stay absent. The mandatory binding is to
    the SAME source/segment as fields; the upstream reader remains responsible
    for validating its demand and once-only centroid transport before calling.
    """
    normalized, rational = _coefficients(fields)
    ref = _reference(catalog_index, component_sections_sha256)
    binding = _binding(source_binding, ref)
    controls = {key: _bernstein(value) for key, value in rational.items()}
    required = set()
    for key in ('N', 'Mx', 'My', 'Mx_original', 'My_original'):
        for pair in controls[key]:
            required.update(_required(key.split('_')[0], pair))
    missing = sorted(key for key in required if not ref['eligible_components'][key])
    rows = []
    exact = []
    for j in range(3):
        pairs = {key: controls[key][j] for key in ACTIONS}
        row = dict(control=j, is_physical_state=False,
            intervals={key: [_outward(lo, -1), _outward(hi, 1)]
                       for key, (lo, hi) in pairs.items()})
        if not missing:
            values = _objective(pairs, ref['signed_capacity_floor'], ref['shear_capacity_lower_N'])
            exact.append(values)
            row.update({key: _outward(value, 1) for key, value in values.items()})
        rows.append(row)
    out = dict(schema=SCHEMA, source=SOURCE, scope=SCOPE, action_convention=ACTION_CONVENTION,
        source_binding=binding, capacity_reference=ref, capacity_reference_sha256=_sha(ref),
        source_polynomials=normalized, source_polynomials_sha256=_sha(normalized),
        identically_zero_by_exact_coefficients={key: all(a == b == 0 for a, b in values)
                                               for key, values in rational.items()},
        controls=rows, required_branches=sorted(required), missing_branches=missing,
        status='pending_required_signed_capacity' if missing else None,
        component_qualified=False, transverse_subproblem_sufficient=False,
        observed_failure=False, weak_transverse_shear_included=True,
        torsion_zero_required=False, separate_EN_6_1_6_required=True,
        flange_reserve_Mf=0, no_favorable_centroid_cancellation_credit=True,
        **{key: False for key in FALSE_FLAGS})
    if missing:
        out.update(index_upper=None, shear_ratio_upper=None, shear_reduction_waived=False,
            reason='Ramo resistente assinado requerido ausente: '+', '.join(missing))
    else:
        maximum = max(row['index_upper'] for row in exact)
        shear = max(row['shear_ratio_upper'] for row in exact)
        sufficient = maximum <= 1 and shear <= 1
        out.update(index_upper=_outward(maximum, 1), shear_ratio_upper=_outward(shear, 1),
            shear_reduction_waived=shear <= F(1, 2),
            status='sufficient' if sufficient else 'inconclusive_upper_bound',
            component_qualified=sufficient, transverse_subproblem_sufficient=sufficient,
            reason='Teto suficiente da componente, não aprovação global.' if sufficient
                else 'Teto conservador excedido: inconclusivo, sem falha física demonstrada.')
    out['content_sha256'] = _sha(out)
    return out


def validate_polynomial_bound(out, fields, *, catalog_index,
                              component_sections_sha256, source_binding):
    """Read-only mathematical replay against independent expected source inputs.

    Do NOT feed fields/binding back from the snapshot under validation: obtain
    them from the caller's validated source inventory. Equality is strict and
    covers controls, zero proofs, identities, signed floors, flags and indices,
    even after a malicious edit has recomputed every snapshot self-hash.
    """
    if not isinstance(out, dict):
        raise ValueError('Snapshot EN6.27 inválido.')
    expected = polynomial_bound(fields, catalog_index=catalog_index,
        component_sections_sha256=component_sections_sha256, source_binding=source_binding)
    # Canonical JSON also distinguishes true from 1 and rejects NaN/infinity.
    if _sha(out) != _sha(expected):
        raise ValueError('Snapshot EN6.27 diverge da fonte/referência/aritmética conferida.')
