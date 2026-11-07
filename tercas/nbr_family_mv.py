"""NBR 14762:2010 9.8.4, same-section strong bending and single-web shear.

Pure arithmetic only: no geometry preparation, eigenproblem, frame solver,
legacy-denominator repair, EN reference, or application/presentation mutation.
The family consumer MUST authenticate its entire source packet before build().
Rational Bernstein covers certify the continuous maximum over x for one fixed
P position. Witness values are lower bounds, never purported exact maxima.
"""
from fractions import Fraction as F
import copy
import math
from decimal import Decimal, localcontext

SCHEMA = 'NBR_family_strong_web_MV_v1'
ARITHMETIC_SCHEMA = 'NBR_9_8_4_qP_Bernstein_arithmetic_v1'
SOURCE = 'ABNT NBR14762:2010 9.8.3-9.8.4, pp.50-51'
RELATIVE_GAP = F(1, 10**10)
MAX_SUBDIVISIONS = 2048
SCOPE = ('Componente forte/alma, NBR9.8.4, sem enrijecedores transversais. '
         'Nao encerra eixo fraco, torcao/bimomento, forcas locais, ligacoes, '
         'estabilidade, ELS ou aprovacao global.')


def _real(value, name, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError('Numero finito invalido: ' + name)
    return F(value)


def _bound(value, upper):
    try:
        out = float(value)
    except OverflowError as exc:
        raise ValueError('Resultado fora do intervalo numerico finito.') from exc
    if not math.isfinite(out):
        raise ValueError('Resultado fora do intervalo numerico finito.')
    if (upper and F(out) < value) or (not upper and F(out) > value):
        out = math.nextafter(out, math.inf if upper else -math.inf)
    if not math.isfinite(out):
        raise ValueError('Limite dirigido fora do intervalo numerico finito.')
    return out


def _sqrt_bound(value, upper):
    # Decimal is only a starting approximation; exact rational squaring checks
    # every returned bound, including subnormals. It is not the certificate.
    with localcontext() as ctx:
        ctx.prec = 80
        out = float((Decimal(value.numerator)/Decimal(value.denominator)).sqrt())
    if not math.isfinite(out):
        raise ValueError('Raiz fora do intervalo numerico finito.')
    while (upper and F(out)**2 < value) or (not upper and F(out)**2 > value):
        out = math.nextafter(out, math.inf if upper else -math.inf)
        if not math.isfinite(out):
            raise ValueError('Limite da raiz fora do intervalo numerico finito.')
    return out


def _value(coeff, x):
    result = F(0)
    for c in reversed(coeff):
        result = result*x+c
    return result


def _square(coeff):
    out = [F(0)]*(2*len(coeff)-1)
    for i, a in enumerate(coeff):
        for j, b in enumerate(coeff):
            out[i+j] += a*b
    return out


def _bernstein(power):
    """Exact power -> Bernstein conversion on [0,1], degree preserved."""
    n = len(power)-1
    return [sum((power[k]*F(math.comb(i, k), math.comb(n, k))
                 for k in range(i+1)), F(0)) for i in range(n+1)]


def _split(control):
    """Exact de Casteljau at 1/2, preserving the whole parent interval."""
    levels = [list(control)]
    while len(levels[-1]) > 1:
        row = levels[-1]
        levels.append([(a+b)/2 for a, b in zip(row, row[1:])])
    return [row[0] for row in levels], [row[-1] for row in reversed(levels)]


def _cover(power):
    """Every leaf is retained; its maximum control coefficient bounds it.

    Thus the largest leaf bound bounds every point, irrespective of whether the
    requested arithmetic gap or the subdivision budget is reached. The gap is
    not a structural acceptance tolerance and never changes the threshold 1.
    """
    control = _bernstein(power)
    leaves = [(F(0), F(1), control)]
    witness_u = max((F(0), F(1)), key=lambda u: _value(power, u))
    lower = _value(power, witness_u)
    steps = 0
    while True:
        pos = max(range(len(leaves)), key=lambda i: max(leaves[i][2]))
        upper = max(leaves[pos][2])
        if upper-lower <= RELATIVE_GAP*max(F(1), abs(upper)) or steps >= MAX_SUBDIVISIONS:
            break
        lo, hi, b = leaves.pop(pos)
        mid = (lo+hi)/2
        left, right = _split(b)
        value = left[-1]
        if value > lower:
            lower, witness_u = value, mid
        leaves.extend(((lo, mid, left), (mid, hi, right)))
        steps += 1
    return dict(lower=lower, upper=upper, witness_u=witness_u,
        converged=upper-lower <= RELATIVE_GAP*max(F(1), abs(upper)), steps=steps,
        leaves=sorted(leaves, key=lambda r: r[0]))


def _inputs(combo, span_mm):
    L = _real(span_mm, 'vao fisico', True)
    a = _real(combo['x_mm'], 'posicao P')
    if not 0 <= a <= L:
        raise ValueError('Posicao P fora do vao fisico.')
    fields = {(kind, axis): _real(combo[kind+'_vector'][axis], kind+' '+axis)
              for kind in ('q', 'P') for axis in ('normal', 'parallel')}
    return L, a, fields


def _segment(lo, hi, after, q, p, L, a, mr, vr2):
    length = hi-lo
    reaction = q*L/2+p*(L-a)/L
    slope = reaction-(p if after else F(0))
    offset = p*a if after else F(0)
    m = [offset+slope*lo-q*lo*lo/2, (slope-q*lo)*length, -q*length*length/2]
    v = [slope-q*lo, -q*length]
    power = _square([c/mr for c in m])
    shear = [c/vr2 for c in _square(v)]
    for i, c in enumerate(shear):
        power[i] += c
    cover = _cover(power)
    u = cover['witness_u']; x = lo+length*u
    moment, force = _value(m, u), _value(v, u)
    side = ('right_limit' if u == 0 else 'left_limit' if u == 1 else 'interior')
    witness = dict(x_mm=float(x), x_exact=str(x), u_exact=str(u), side=side,
        Mstrong_Nmm=float(moment), Mstrong_exact=str(moment),
        Vweb_N=float(force), Vweb_exact=str(force),
        index_squared_exact=str(cover['lower']),
        index_squared_lower=_bound(cover['lower'], False),
        witness_is_exact_maximum=False)
    proof = dict(x_start_exact=str(lo), x_end_exact=str(hi), after_P=after,
        normalized_coordinate='u=(x-x_start)/(x_end-x_start)',
        Mstrong_power_exact=[str(c) for c in m], Vweb_power_exact=[str(c) for c in v],
        index_squared_power_exact=[str(c) for c in power],
        leaves=[dict(u_start_exact=str(left), u_end_exact=str(right),
                     bernstein_exact=[str(c) for c in control],
                     upper_exact=str(max(control))) for left, right, control in cover['leaves']],
        maximum_lower_exact=str(cover['lower']), maximum_upper_exact=str(cover['upper']),
        subdivisions=cover['steps'], requested_gap_reached=cover['converged'], witness=witness)
    return proof, cover['lower'], cover['upper'], v


def web_shear(combo, span_mm, *, VRd_squared_exact):
    """Exact endpoint maximum of linear V, independent of bending or NBR9.4."""
    L, a, fields = _inputs(combo, span_mm)
    if not isinstance(VRd_squared_exact, str) or F(VRd_squared_exact) <= 0:
        raise ValueError('VRd quadrado positivo em fracao textual requerido.')
    vr2 = F(VRd_squared_exact)
    q, p = fields['q', 'normal'], fields['P', 'normal']
    reaction = q*L/2+p*(L-a)/L
    states = []
    for lo, hi, after in ((F(0), a, False), (a, L, True)):
        if lo == hi:
            continue
        for x, side in ((lo, 'right_limit'), (hi, 'left_limit')):
            value = reaction-q*x-(p if after else 0)
            states.append((abs(value), x, value, side))
    magnitude, x, signed, side = max(states, key=lambda r: r[0])
    ratio2 = magnitude**2/vr2
    return dict(maximum_abs_exact=str(magnitude), maximum_abs_N=_bound(magnitude, True),
        x_exact=str(x), x_mm=float(x), side=side, Vweb_exact=str(signed),
        index_squared_exact=str(ratio2), index_lower=_sqrt_bound(ratio2, False),
        index_upper=_sqrt_bound(ratio2, True),
        criterion_status='meets' if ratio2 <= 1 else 'fails',
        source='NBR14762:2010 9.8.3', weak_shear_assessed=False,
        torsional_shear_included=False, whole_member_approved=False)


def interaction(combo, span_mm, *, MRd_local_Nmm, VRd_N=None, VRd_squared_exact=None):
    """Certified bounds for max_x ((M(x)/MRd,local)^2+(V(x)/VRd)^2).

    Inputs are exact binary rationals, NOT increased physical precision. M and
    V follow the same q+P equilibrium, V=dM/dx in the application's sign basis.
    All physical segment endpoints and both one-sided values at an interior P
    are covered. At P on a support, only the member's physical side is retained.
    P position is fixed for this combination: no moving-P envelope is implied.
    Resistance qualification and NBR9.4 belong to the authenticated consumer.
    """
    L, a, fields = _inputs(combo, span_mm)
    q, p = fields['q', 'normal'], fields['P', 'normal']
    strong_zero = q == 0 and (p == 0 or a in (0, L))
    # Filler never leaves this arithmetic; no bending denominator is needed
    # when every moment is identically zero, proved from exact equilibrium.
    mr = F(1) if MRd_local_Nmm is None and strong_zero else _real(MRd_local_Nmm, 'MRd local 9.8.2.1', True)
    if (VRd_N is None) == (VRd_squared_exact is None):
        raise ValueError('Forneca um unico denominador VRd ou VRd quadrado exato.')
    if VRd_N is not None:
        vr2 = _real(VRd_N, 'VRd alma 9.8.3', True)**2
    else:
        if not isinstance(VRd_squared_exact, str):
            raise ValueError('VRd quadrado exato deve ser uma fracao textual.')
        vr2 = F(VRd_squared_exact)
        if vr2 <= 0:
            raise ValueError('VRd quadrado positivo requerido.')
    pieces = []; bounds = []
    for lo, hi, after in ((F(0), a, False), (a, L, True)):
        if lo == hi:
            continue
        proof, lower, upper, v = _segment(lo, hi, after, q, p, L, a, mr, vr2)
        pieces.append(proof); bounds.append((lower, upper))
    lower = max(v[0] for v in bounds); upper = max(v[1] for v in bounds)
    witness = copy.deepcopy(max(pieces, key=lambda r: F(r['maximum_lower_exact']))['witness'])
    weak_zero = fields['q', 'parallel'] == fields['P', 'parallel'] == 0
    return dict(schema=ARITHMETIC_SCHEMA, source=SOURCE, scope=SCOPE,
        physical_span_mm=span_mm, point_position_mm=combo['x_mm'],
        MRd_denominator_Nmm=MRd_local_Nmm, VRd_denominator_N=VRd_N,
        VRd_squared_exact=str(vr2), strong_moment_identically_zero=strong_zero,
        MRd_basis='NBR9.8.2.1 only; not FLT/distortional minimum',
        maximum_lower_exact=str(lower), maximum_upper_exact=str(upper),
        index_squared_lower=_bound(lower, False), index_squared_upper=_bound(upper, True),
        criterion_status='meets' if upper <= 1 else 'fails' if lower > 1 else 'boundary_inconclusive',
        maximum_is_enclosed=True, witness=witness, envelope_certificate=pieces,
        requested_relative_gap_exact=str(RELATIVE_GAP),
        requested_gap_reached=upper-lower <= RELATIVE_GAP*max(F(1), abs(upper)),
        web_shear=web_shear(combo, span_mm, VRd_squared_exact=str(vr2)),
        weak_actions_identically_zero=weak_zero, weak_shear_assessed=False,
        primary_torsion_assessed=False, warping_bimoment_assessed=False,
        resistance_qualified=False, section94_qualified=False,
        moving_point_position_envelope=False, whole_member_approved=False)


def web_capacity(source_binding):
    """Own nominal flat web/material, never an EN or published resistance.

    Source authentication is external. Dimensions and material are read from
    exactly the same binding as local MRd. No transverse-stiffener credit.
    """
    identity = source_binding['nominal_identity']
    dimensions = identity['dimensions_mm']
    h = _real(dimensions['h'], 'h', True)
    t = _real(dimensions['t'], 't', True)
    _real(dimensions['lip'], 'lip Ue', True)
    ri = _real(identity['inner_radius_mm'], 'ri')
    if ri < 0 or h-2*(ri+t) <= 0:
        raise ValueError('Alma plana nao positiva ou raio negativo.')
    material = source_binding['material']
    E = _real(material['E_MPa'], 'E', True)
    fy = _real(material['fy_MPa'], 'fy', True)
    gamma = _real(material['gamma'], 'gamma', True)
    if gamma != F(1.1):
        raise ValueError('NBR9.8.3 requer gamma=1.10; material nao pode ser misturado.')
    # Normative decimal coefficients are exact rationals. In the intermediate
    # branch squaring removes sqrt(kv*fy*E); no rounded VRd enters the proof.
    flat = h-2*(ri+t); kv = F(5); g = F(11, 10)
    slenderness2 = (flat/t)**2; elastic = E*kv/fy
    if slenderness2 <= F(27, 25)**2*elastic:
        vr2 = (F(3, 5)*fy*flat*t/g)**2; branch = 'yield'
    elif slenderness2 <= F(7, 5)**2*elastic:
        vr2 = (F(13, 20)*t*t/g)**2*kv*fy*E; branch = 'intermediate'
    else:
        vr2 = (F(181, 200)*E*kv*t**3/(flat*g))**2; branch = 'elastic'
    return dict(source='NBR14762:2010 9.8.3, pp.50-51',
        VRd_squared_exact=str(vr2), VRd_lower_N=_sqrt_bound(vr2, False),
        VRd_upper_N=_sqrt_bound(vr2, True), display_bounds_not_denominators=True,
        branch=branch, kv=5, gamma=1.1, gamma_normative_exact='11/10',
        h_external_mm=float(h), h_flat_mm=float(flat), h_flat_exact=str(flat),
        t_mm=float(t), ri_mm=float(ri), fy_MPa=float(fy), E_MPa=float(E),
        geometry_basis='h_flat=h_external-2*(ri+t); same own-rounded-contour binding',
        branch_selection='Exact squared comparisons against (1.08)^2*E*kv/fy and (1.4)^2*E*kv/fy',
        transverse_stiffener_credit=False, nominal_Pierin_resistance_used=False,
        EN_resistance_used=False, whole_member_approved=False)


def build(record, sources, span_mm):
    """Prepare a component from the already authenticated family row/sources.

    Usability requires the caller's qualified own-local component index, not a
    saved self-hash or the presence of a positive capacity alone. The current
    NBR9.4 gate is replayed from individual actions before a component verdict.
    An absent/unqualified gate blocks it unless M is identically zero. This
    never qualifies the whole member or the combined weak/torsional actions.
    """
    own = sources['own_rounded_contour']
    if own.get('schema') != 'nbr_ue_family_components_v2' or own.get('physical_span_mm') != span_mm:
        raise ValueError('Fonte NBR propria atual e mesmo vao fisico requeridos.')
    if record.get('limit_state') != 'ELU' or record['combination'].get('limit_state') != 'ELU':
        raise ValueError('M-V resistente requer combinacao ELU.')
    if record.get('combination_id') != record['combination'].get('id'):
        raise ValueError('Identidade da combinacao divergente.')
    if own.get('sign_convention') != 'Positive My_app compresses web; negative compresses lips; strong signs symmetric':
        raise ValueError('Simetria dos dois sentidos fortes nao qualificada pela fonte.')
    local = own['strong']['local']
    parts = [p for p in record['components'] if p.get('route') == 'own_rounded_contour' and p.get('method') == 'local']
    if len(parts) != 1:
        raise ValueError('Uma unica componente local propria requerida.')
    part = parts[0]; mr = local.get('MRd_Nmm')
    usable = (local.get('eligible') is True and part.get('capacity_Nmm') == mr
              and type(part.get('index')) in (int, float) and math.isfinite(part['index'])
              and part['index'] >= 0 and not part.get('capacity_lower_bound_only', False))
    binding = own['source_binding']
    capacity = web_capacity(binding)
    L, a, fields = _inputs(record['combination'], span_mm)
    strong_zero = fields['q', 'normal'] == 0 and (fields['P', 'normal'] == 0 or a in (0, L))
    calculation = None
    if usable or strong_zero:
        calculation = interaction(record['combination'], span_mm,
            MRd_local_Nmm=mr if usable else None, VRd_squared_exact=capacity['VRd_squared_exact'])
    gate = record.get('shear_lag_applicability')
    if gate is not None:
        from .nbr_ue_shear_lag import validate_saved as validate_gate
        validate_gate(gate, physical_span_mm=span_mm,
            external_dimensions_mm=binding['nominal_identity']['dimensions_mm'],
            actions=record['actions'], member_model='isolated_simply_supported')
    gate_qualified = strong_zero or (gate is not None and gate['axes']['normal']['qualified'] is True)
    missing = ([] if calculation else ['own_rounded_contour:local_9.8.2.1'])
    if not gate_qualified:
        missing.append('NBR9.4:strong_shear_lag_qualification')
    criterion = calculation['criterion_status'] if calculation and gate_qualified else None
    from .ue_catalog_reference import digest
    return dict(schema=SCHEMA, source=SOURCE, scope=SCOPE,
        combination_id=record['combination_id'], physical_span_mm=span_mm,
        source_binding=copy.deepcopy(binding), source_own_packet_sha256=digest(own),
        combination_sha256=digest(record['combination']),
        local_source=copy.deepcopy(local), local_component=copy.deepcopy(part),
        NBR_web_capacity=capacity, arithmetic=calculation,
        web_shear=web_shear(record['combination'], span_mm, VRd_squared_exact=capacity['VRd_squared_exact']),
        status='pending_own_local_resistance' if calculation is None else
            'pending_section94_qualification' if not gate_qualified else
            'boundary_inconclusive' if criterion == 'boundary_inconclusive' else 'component_computed',
        missing=missing, criterion_status=criterion, section94_qualified=gate_qualified,
        shear_lag_applicability=copy.deepcopy(gate),
        section94_not_required_for_identically_zero_moment=strong_zero,
        presentation_gate='Require current authenticated NBR9.4 qualification before design verdict',
        own_contour_only=True, nominal_reference_mixed=False, EN_capacity_used=False,
        FLT_distortional_denominator_used=False, weak_shear_assessed=False,
        primary_torsion_assessed=False, warping_bimoment_assessed=False,
        complete_interaction_qualified=False, whole_member_approved=False)


def validate_arithmetic(saved, combo, span_mm, *, MRd_local_Nmm, VRd_N=None, VRd_squared_exact=None):
    """Replay only exact arithmetic and full cover, not a solver or resistance."""
    expected = interaction(combo, span_mm, MRd_local_Nmm=MRd_local_Nmm,
        VRd_N=VRd_N, VRd_squared_exact=VRd_squared_exact)
    if saved != expected:
        raise ValueError('M-V salvo diverge dos esforcos, denominadores ou cobertura continua.')
    return copy.deepcopy(expected)


def validate_saved(saved, record, sources, span_mm):
    expected = build(record, sources, span_mm)
    if saved != expected:
        raise ValueError('Componente M-V salva difere da fonte NBR autenticada ou aritmetica.')
    return copy.deepcopy(expected)
