"""Analytical lower bound of a declared resistance energy operator.

NOT the eigenvalue of the historical full-span free-warping solver when shorter
resistance lengths are declared. Ly/Lz are explicitly assumed Euler energy
bounds, not inferred physical supports. The proof is in
 docs/FLT_HEIGHT_ENERGY_FLOOR_R11.md. No empirical C1/C2 is introduced.
"""
from __future__ import annotations
import copy
import math
from fractions import Fraction
from .ltb_load_height import finite, action_terms
from .ue_catalog_reference import digest

SCHEMA = 'flt_height_declared_energy_floor_v1'
SCHEMA_V2 = 'flt_height_declared_energy_floor_v2'
POLICY_V2 = 'moment_product_energy_bound_v2'
SCHEMA_V3 = 'flt_height_declared_energy_floor_v3'
POLICY_V3 = 'direct_curvature_energy_bound_v3'

METHOD = 'Sahraei2017_energy_Cauchy_Poincare_declared_Euler_bounds'
SCOPE = ('Piso analítico do operador resistente declarado: alturas por ação, q+P e '
         'posições reais no vão físico. Ly/Lz são hipóteses de limites inferiores '
         'de energia Euler, não apoios físicos inferidos. Torção nula nas duas '
         'extremidades no espaço admitido. Não é autovalor do solver histórico '
         'de garfo livre quando os comprimentos são menores. Não inclui '
         'pré-deformação por torção, acoplamento biaxial ou aprovação global.')
SOURCE = 'https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf'


# Exact rational enclosure of pi, not a fitted resistance coefficient.
PI_LO = Fraction(314159265358979323846264338327950288419716939937510, 10**50)
PI_HI = Fraction(314159265358979323846264338327950288419716939937511, 10**50)


def _q(value):
    return Fraction(value) if isinstance(value, (int, Fraction)) else Fraction.from_float(float(value))


def _directed(value, upward):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Energy bound outside finite output range')
    actual = Fraction.from_float(result)
    if (actual < value if upward else actual > value):
        result = math.nextafter(result, math.inf if upward else -math.inf)
    return finite(result, 'directed bound')


def _sqrt_upper(value):
    """Enclosing square root by integer arithmetic, >128 significant bits."""
    if value < 0:
        raise ValueError('Negative square-root argument')
    if not value:
        return Fraction(0)
    exponent = (value.numerator.bit_length()-value.denominator.bit_length())//2
    quantum = Fraction(2)**(exponent-128)
    scaled = value/(quantum*quantum)
    integer = math.isqrt(scaled.numerator//scaled.denominator)
    upper = (integer+1)*quantum
    assert upper*upper >= value
    return upper


def _exact_load_quantities(L, loads):
    """No rounded per-action force-height products or moment summations."""
    L = _q(L)
    uniform = [a for a in loads if a['station'] is None]
    q = sum((_q(a['q_down_N_mm']) for a in uniform), Fraction(0))
    qh = sum((_q(a['q_down_N_mm'])*_q(a['height_above_SC_mm']) for a in uniform), Fraction(0))
    points = {}; heights = {}
    for a in loads:
        if a['station'] is None:
            continue
        station = _q(a['s_mm']); force = _q(a['P_down_N'])
        if not 0 <= station <= L:
            raise ValueError('Point outside exact physical span')
        points[station] = points.get(station, Fraction(0))+force
        heights[station] = heights.get(station, Fraction(0))+force*_q(a['height_above_SC_mm'])
    internal = {a:p for a,p in points.items() if 0<a<L}
    cuts = sorted({Fraction(0),L}|set(internal))
    reaction = q*L/2+sum((p*(L-a)/L for a,p in internal.items()),Fraction(0))
    stations = set(cuts); shear_states = []
    for left,right in zip(cuts[:-1],cuts[1:]):
        offset = reaction-sum((p for a,p in internal.items() if a<=left),Fraction(0))
        shear_states.extend([(left,'right',offset-q*left),(right,'left',offset-q*right)])
        if q:
            stationary = offset/q
            if left<stationary<right:
                stations.add(stationary)
    def moment(x):
        return q*x*(L-x)/2+sum((p*min((L-a)*x/L,a*(L-x)/L) for a,p in internal.items()),Fraction(0))
    moments = [(x,moment(x)) for x in sorted(stations)]
    witness = max(moments,key=lambda pair:abs(pair[1]))
    v_witness = max(shear_states,key=lambda record:abs(record[2]))
    return dict(L=L,q=q,qh=qh,point_heights=heights,M=abs(witness[1]),V=abs(v_witness[2]),
        moment_witness=witness,shear_witness=v_witness,shear_states=shear_states)


def maximum_shear(L, loads):
    """Exact rational extrema, reported with outward magnitude conversion."""
    values = _exact_load_quantities(L,loads)
    def record(state):
        return dict(x_mm=float(state[0]),side=state[1],V_N=float(state[2]))
    return dict(maximum_abs_V_N=_directed(values['V'],True),
                witness=record(values['shear_witness']),
                candidates=[record(state) for state in values['shear_states']],
                rational_extrema=True)


def _moment_product_bound(exact, loads):
    """Distributional integration-by-parts bound, on the physical interval.

    ||(M phi)'||² = integral(M² phi'² + q M phi²)
                      + sum_a P_a M(a) phi(a)².
    Opposite coincident forces are summed before taking positive parts.
    The maxima of q*M occur at the same stations as M (q is constant).
    """
    L = exact['L']; q = exact['q']
    points = {}
    for load in loads:
        if load['station'] is not None:
            a = _q(load['s_mm'])
            if 0 < a < L:
                points[a] = points.get(a, Fraction(0)) + _q(load['P_down_N'])
    def moment(x):
        return q*x*(L-x)/2 + sum((p*min((L-a)*x/L, a*(L-x)/L)
                                  for a,p in points.items()), Fraction(0))
    cuts = sorted({Fraction(0), L} | set(points))
    stations = set(cuts)
    reaction = q*L/2 + sum((p*(L-a)/L for a,p in points.items()), Fraction(0))
    if q:
        for left,right in zip(cuts[:-1], cuts[1:]):
            stationary = (reaction-sum((p for a,p in points.items() if a<=left),Fraction(0)))/q
            if left < stationary < right:
                stations.add(stationary)
    qm_upper = max([Fraction(0)] + [q*moment(x) for x in stations])
    uniform = qm_upper*(L/PI_LO)**2
    point_rows = [(a,p,moment(a),max(p*moment(a),0)*a*(L-a)/L)
                  for a,p in sorted(points.items())]
    square = exact['M']**2 + uniform + sum((row[3] for row in point_rows),Fraction(0))
    upper = _sqrt_upper(square)
    return upper, dict(
        identity='integral((M phi)_prime^2) = integral(M^2 phi_prime^2 + q M phi^2) + sum(Pa M(a) phi(a)^2)',
        moment_square_fraction=str(exact['M']**2),
        uniform_qM_max_positive_fraction=str(qm_upper),
        uniform_bound_fraction=str(uniform),
        point_bounds=[dict(station_fraction=str(a),force_fraction=str(p),moment_fraction=str(m),
                           bound_fraction=str(b)) for a,p,m,b in point_rows],
        B_squared_upper_fraction=str(square),B_upper_fraction=str(upper),
        physical_span_fraction=str(L),method='derived_sufficient_bound_not_normative_coefficient')


def solve_floor(*, L_mm, Ly_mm, Lz_mm, E_MPa, G_MPa, Iweak_mm4, J_mm4, Cw_mm6, actions, method=None):
    """Conditional analytical bound, using the whole physical load diagram.

    Assume EIy int(u''²)>=Ny int(u'²) and
    ECw int(phi''²)>=ECw(pi/Lz)² int(phi'²), with phi(0)=phi(L)=0.
    Any positive end-restraint energies are included in the declared bounds;
    they are not reconstructed or inserted into the historical physical model.
    """
    if method not in (None, POLICY_V2, POLICY_V3):
        raise ValueError('Unknown declared energy floor policy')
    L, ly, lz, E, G, I, J, Cw = [finite(v,k,True) for k,v in (
        ('L',L_mm),('Ly',Ly_mm),('Lz',Lz_mm),('E',E_MPa),('G',G_MPa),
        ('Iweak',Iweak_mm4),('J',J_mm4),('Cw',Cw_mm6))]
    loads = action_terms(actions,L)
    exact = _exact_load_quantities(L_mm,loads)
    Lq, Mq, Vq = exact['L'], exact['M'], exact['V']
    E_q,G_q,I_q,J_q,Cw_q,ly_q,lz_q=map(_q,(E_MPa,G_MPa,Iweak_mm4,J_mm4,Cw_mm6,Ly_mm,Lz_mm))
    Ny_q = E_q*I_q*(PI_LO/ly_q)**2
    T_q = G_q*J_q+E_q*Cw_q*(PI_LO/lz_q)**2
    B_q = Mq+Lq/PI_LO*Vq
    product_witness = None
    if method in (POLICY_V2, POLICY_V3):
        product_B, product_witness = _moment_product_bound(exact, loads)
        product_witness['legacy_B_upper_fraction'] = str(B_q)
        B_q = min(B_q, product_B)
    direct_witness = None
    if method == POLICY_V3:
        # Udirect=(Ly/pi)||u''||, rather than U=||u'||. Both majorants
        # separately bound the ORIGINAL energy; select one, never add them.
        # Bdirect=Mmax*L/Ly implies Bdirect²/Ny=Mmax² L²/(pi² EIy).
        direct_B = Mq*Lq/ly_q
        direct_witness = dict(
            direct_B_upper_fraction=str(direct_B),
            product_B_upper_fraction=str(B_q),
            selected='direct_curvature' if direct_B < B_q else 'moment_product',
            direct_coordinate='Udirect=(Ly/pi)*norm(u_second_derivative)',
            direct_lateral_hypothesis='K_lateral >= EIy integral(u_second_derivative^2); nonnegative added restraint energy',
            inequality='abs(integral(M u_second_derivative phi)) <= Mmax*(Lphysical/pi)*norm(u_second_derivative)*norm(phi_prime)',
            origin='Derived Cauchy/Poincare bound on Sahraei2017 Eq2; not a published normative coefficient')
        B_q = min(B_q, direct_B)
    uniform_D_q = max(exact['qh'],0)*(Lq/PI_LO)**2
    point_D_q = [(station,height,station*(Lq-station)/Lq,
                  max(height,0)*station*(Lq-station)/Lq)
                 for station,height in sorted(exact['point_heights'].items())]
    D_q = uniform_D_q+sum((row[3] for row in point_D_q),Fraction(0))
    # Keep the coefficients exposed in JSON themselves outward bounds. The
    # exact root below uses these same binary values, interpreted as rationals.
    Ny,T = _directed(Ny_q,False),_directed(T_q,False)
    B,D = _directed(B_q,True),_directed(D_q,True)
    finite(Ny,'Ny',True);finite(T,'T',True)
    Ny_q,T_q,B_q,D_q=map(_q,(Ny,T,B,D))
    M=float(Mq);shear=maximum_shear(L_mm,loads)
    point_D = [dict(s_mm=float(a),signed_force_height_Nmm=float(h),
                    trace_constant_mm=_directed(c,True),D_Nmm2=_directed(value,True))
               for a,h,c,value in point_D_q]
    result = dict(schema=SCHEMA, method=METHOD, scope=SCOPE,
        physical_span_mm=L,Ly_used_mm=ly,Lz_used_mm=lz,
        maximum_reference_moment_Nmm=M, shear_extremum=shear,
        Ny_assumed_lower_N=Ny,T_assumed_lower_Nmm2=T,
        B_upper_Nmm=B,D_upper_Nmm2=D,
        uniform_height_sum_N=float(exact['qh']),uniform_D_Nmm2=_directed(uniform_D_q,True),point_height_bounds=point_D,
        exact_load_quantities=dict(Mmax_fraction=str(Mq),Vmax_fraction=str(Vq),
            q_height_fraction=str(exact['qh']),moment_witness_x_fraction=str(exact['moment_witness'][0]),
            pi_lower_fraction=str(PI_LO),pi_upper_fraction=str(PI_HI)),
        energy_bound_hypotheses=dict(
            end_twist='phi(0)=phi(Lphysical)=0',
            lateral_Euler_bound='EIy integral(u_second_derivative^2) plus admitted end energies >= Ny integral(u_first_derivative^2)',
            warping_Euler_bound='ECw integral(phi_second_derivative^2) plus admitted end energies >= ECw(pi/Lz)^2 integral(phi_first_derivative^2)',
            positive_restraint_energy_may_be_in_declared_bounds=True,
            origin='Declared resistance lengths, not inferred supports',
            physical_realization_verified=False),
        bound_type='analytical_lower_bound_conditional_on_declared_energy_inequalities',
        mathematical_lower_bound_of_declared_operator=True,
        historical_physical_solver_lower_bound_claimed=False,
        floating_point_interval_certified=True,
        interval_scope='Exact supplied numeric loads/properties, rational extrema and products, pi enclosure, integer square-root enclosure, directed output conversion; not physical geometry uncertainty',
        numerical_roundoff_relative_margin=0.,
        elastic_reference_eligible=False,Me_lower_bound_Nmm=None,lambda_lower_bound=None,
        stabilizing_height_credit_used=False,empirical_coefficients_used=False,
        eigenvalue_rescaled_after_solver=False,physical_supports_created=False,
        physical_restraints_verified=False,demand_span_changed=False,
        primary_torsion_assessed=False,biaxial_stability_assessed=False,
        actual_load_capacity_qualified=False,whole_member_approved=False,
        sources=[dict(url=SOURCE,location='Eq2 energy; analytical inequalities derived in this implementation')])
    if method in (POLICY_V2, POLICY_V3):
        result.update(schema=SCHEMA_V2, method=POLICY_V2,
                      moment_product_bound=product_witness,
                      historical_floor_preserved_without_explicit_method=True)
    if method == POLICY_V3:
        result.update(schema=SCHEMA_V3, method=POLICY_V3,
                      direct_curvature_bound=direct_witness)
    if B==0 and D==0:
        return dict(result,status='no_reference_bending_or_destabilizing_height',
            reason='Nenhuma perda de positividade por estes termos; não se declara capacidade infinita nem Me=0.')
    # Rational enclosing root. No heuristic epsilon protects cancellation.
    if B_q==0:
        lam_q = T_q/D_q
    else:
        root_upper = _sqrt_upper(D_q*D_q+4*B_q*B_q*T_q/Ny_q)
        lam_q = 2*T_q/(D_q+root_upper)
    lam = finite(_directed(lam_q,False),'lambda floor',True)
    lam_q = _q(lam)
    determinant = Ny_q*(T_q-lam_q*D_q)-lam_q*lam_q*B_q*B_q
    if determinant < 0:
        raise ArithmeticError('Directed energy bound lost positive semidefiniteness')
    result['lambda_lower_bound'] = lam
    result['determinant_exact_nonnegative'] = True
    result['determinant_relative_residual'] = float(determinant/(Ny_q*T_q))
    if not M:
        return dict(result,status='rotational_energy_bound_without_reference_bending',
            reason='Piso do fator de perda de positividade com momento resultante nulo; Me por flexão não definido.')
    return dict(result,status='computed_declared_energy_floor',elastic_reference_eligible=True,
        Me_lower_bound_Nmm=finite(_directed(lam_q*Mq,False),'Me floor',True),
        reason='Piso analítico no operador condicionado às hipóteses de energia dos comprimentos resistentes; não é aprovação física nem autovalor do solver antigo.')


def qualify_family(data, actions, *, method=None):
    """Bind the bound to the own contour without invoking a Me approximation."""
    from . import pierin_ue_registry as registry, ue_catalog_reference as own
    from . import roof_top_load as roof
    from .resistance_effective_lengths import configuration
    from .flt_height_effective import symmetry_proof
    if method not in (None, POLICY_V2, POLICY_V3):
        raise ValueError('Unknown declared energy floor policy')
    registry.select_new_study(data['catalog_index'],include_routes=False)
    section=own.section_for(data);p=section['properties']
    symmetry=symmetry_proof(section);lengths=configuration(data)
    L=finite(data['L_mm'],'physical span',True)
    ly=L if lengths is None else lengths['Ly_mm']
    lz=L if lengths is None else lengths['Lz_mm']
    m={k:data['properties'][k] for k in ('E_MPa','G_MPa','fy_MPa')}
    for key,value in m.items():finite(value,key,True)
    bound=dict(schema=SCHEMA,method=METHOD,scope=SCOPE,status='pending_energy_scope',
        elastic_reference_eligible=False,Me_lower_bound_Nmm=None,lambda_lower_bound=None,
        physical_span_mm=L,Ly_used_mm=ly,Lz_used_mm=lz,
        resistance_lengths=copy.deepcopy(lengths),manual_effective_lengths_used=lengths is not None,
        source_binding=dict(catalog_index=data['catalog_index'],nodes_sha256=section['nodes_sha256'],
            section_profile_id=section['profile_id'],property_basis='same own rounded contour',material=m),
        section_properties={k:p[k] for k in ('Ix_strong_mm4','Iy_weak_mm4','J_mm4','Cw_mm6')},
        strong_symmetry=symmetry,actions=copy.deepcopy(actions),whole_member_approved=False)
    reason=None
    from .girt_flt_adapter import is_girt, qualify as qualify_girt_actions
    if is_girt(data):
        bound['girt_action_binding']=qualify_girt_actions(data,actions)
        if not bound['girt_action_binding']['eligible']:
            reason=bound['girt_action_binding']['reason']
    elif not roof.enabled(data):
        reason='Posição de carga não adotada: esquema de cobertura ausente ou desabilitado.'
    if reason is None and not symmetry['qualified']:
        reason='Simetria forte/zj=0 não demonstrados no contorno próprio.'
    if reason is None:
        try:
            loads=action_terms(actions,L)
            for a in loads:
                key='q_parallel_N_mm' if a['station'] is None else 'P_parallel_N'
                a['parallel_force']=finite(a.get(key,0.),key)
        except (ValueError,TypeError) as exc:
            reason='Ações não qualificadas: '+str(exc)
    if reason is not None:
        bound['reason']=reason
    else:
        bound.update(
            normal_projection_primary_torque_by_action=[dict(name=a['name'],kind=a['kind'],
                value=a['primary_torque'],units='N' if a['station'] is None else 'Nmm') for a in loads],
            primary_torque_by_action=[dict(name=a['name'],kind=a['kind'],
                value=None if a['primary_torque'] is None else a['primary_torque']-a['height_above_SC_mm']*a['parallel_force'],
                units='N' if a['station'] is None else 'Nmm') for a in loads],
            primary_torque_report_includes_parallel_actions=True,
            height_tangent_by_action=[dict(name=a['name'],value=a['height_tangent_term']) for a in loads],
            normal_projection_only=True,
            individual_parallel_actions_present=any(a['parallel_force']!=0 for a in loads))
        bound.update(solve_floor(L_mm=data['L_mm'],Ly_mm=ly,Lz_mm=lz,
            E_MPa=m['E_MPa'],G_MPa=m['G_MPa'],Iweak_mm4=p['Iy_weak_mm4'],
            J_mm4=p['J_mm4'],Cw_mm6=p['Cw_mm6'],actions=actions,method=method))
        bound['energy_bound_hypotheses']['declared_origin']=(
            lengths['origin'] if lengths else 'Full-span fork/free-warping reference')
    if method in (POLICY_V2, POLICY_V3):
        bound['schema'] = SCHEMA_V3 if method == POLICY_V3 else SCHEMA_V2
        bound['method'] = method
    bound['snapshot_sha256']=digest(bound)
    return bound


def validate_saved(evidence,data,actions):
    method = {SCHEMA_V2: POLICY_V2, SCHEMA_V3: POLICY_V3}.get(evidence.get('schema'))
    expected=qualify_family(data,actions,method=method)
    if evidence!=expected:
        raise ValueError('Piso de energia FLT alterado ou fora das hipóteses salvas; recalcule explicitamente.')
    return copy.deepcopy(expected)
