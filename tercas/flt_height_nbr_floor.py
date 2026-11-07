"""Sufficient NBR strong-FLT check from the declared-operator energy floor.

A failed sufficient check is INCONCLUSIVE, never a member failure. Neither
this bridge nor its resistance algebra establishes the physical Euler bounds,
primary-torsion stability, biaxial stability, or the other resistance checks.
"""
from __future__ import annotations
import copy
from fractions import Fraction
from . import flt_height_energy_floor as energy
from . import nbr_ue_family as provider
from . import nbr_ue_family_expansion as mle
from .direct_roof_envelope import nbr_resistance_floor
from .ue_catalog_reference import digest

SCHEMA = 'flt_height_declared_energy_nbr_floor_v1'
SCOPE = ('Condição suficiente de FLT forte NBR, condicional às desigualdades de '
         'energia dos comprimentos resistentes declarados. Um índice acima de 1 '
         'é inconclusivo, nunca reprovação. Não cobre distorção, interação, '
         'pré-torção, estabilidade biaxial ou aprovação física/global.')
Q = energy._q
C = Fraction


def _sqrt_lower(value):
    if value == 0:
        return C(0)
    return value/energy._sqrt_upper(value)


def _rho_lower(lam_upper):
    """Capped effective-width curve, nonincreasing for lambda >= .673."""
    if lam_upper <= C('0.673'):
        return C(1)
    return min(C(1), (lam_upper-C('0.22'))/lam_upper**2)


def chi_envelope(W, fy, me):
    """Exact lower envelope for all Me_real >= me, including rounded jump."""
    lam2 = Q(W)*Q(fy)/Q(me)
    limit = C('1.11')*(1-C('0.278')*C('1.336')**2)
    if lam2 <= C('0.6')**2:
        chi, branch = C(1), 'stocky'
    elif lam2 < C('1.336')**2:
        chi, branch = C('1.11')*(1-C('0.278')*lam2), 'intermediate'
    else:
        chi, branch = min(1/lam2, limit), 'elastic_with_rounded_transition_envelope'
    return chi, dict(chi_lower_bound=energy._directed(chi,False),
        chi_lower_fraction=str(chi),lambda_squared_at_Me_floor_fraction=str(lam2),
        branch=branch,transition_chi_limit_fraction=str(limit),
        all_Me_at_or_above_floor=True,
        source_coefficients=dict(stocky='0.6',transition='1.336',factor='1.11',quadratic='0.278'),
        monotonic_raw_rounded_curve_assumed=False)


def mle_uniform_modulus_floor(p, props, material):
    """A retained-section proof for every 0 < sigma <= fy, not a grid scan.

    The proof intentionally does not assert monotonicity of sigma*Wcef(sigma).
    Full-web validity is proved uniformly over the centroid/stress interval.
    """
    t,ri,h,bf,D,E,fy = map(Q,(p['t'],p['ri_mm'],p['h'],p['bf'],p['lip'],material['E_MPa'],material['fy_MPa']))
    b,d,B=bf-2*(ri+t),D-ri-t,h-2*(ri+t)
    a,r=h-t,ri+t/2
    if min(b,d,B)<=0 or b/t>60 or d/t>60 or B/t>200:
        raise mle.OutsideMethod('Uniform MLE floor: Table4/flat geometry domain unavailable')
    l0hi=energy._sqrt_upper(fy/E)*b/(t*C('0.623'))
    Is=t*d**3/12
    Ia_hi=min(399*t**4*max(C(0),C('0.487')*l0hi-C('0.328'))**3,
              t**4*(56*l0hi+5))
    ratio=min(C(1),Is/Ia_hi) if Ia_hi else C(1)
    # At stocky stress ratio=1. Beyond it, n=max(1/3,.582-.122*l0)
    # lies in (0,1); hence r^n >= r >= ratio for every r in [ratio,1].
    if l0hi<=C('0.673'):
        kmin=None;be=b
    else:
        if D/b>C('0.8'):
            raise mle.OutsideMethod('Uniform MLE floor: necessary lip has D/b > .8')
        coeff=C('3.57') if D/b<=C('0.25') else C('4.82')-5*D/b
        kmin=min(C(4),coeff*ratio+C('0.43'))
        if kmin<=0:
            raise mle.OutsideMethod('Uniform MLE floor: positive stiffener coefficient unavailable')
        lfhi=energy._sqrt_upper(fy/(E*kmin))*b/(t*C('0.95'))
        be=b*_rho_lower(lfhi)
    llhi=energy._sqrt_upper(fy/(E*C('0.43')))*d/(t*C('0.95'))
    ds=ratio*d*_rho_lower(llhi)
    A=Q(props['A_mm2']);cy=Q(props['centroid_xy_mm'][1]);Ix=Q(props['Ix_strong_mm4'])
    lo=a-r-d;hi=a-r-ds;top=a+t/2
    if not 0<ds<=d or not 0<be<=b or not lo>cy:
        raise mle.OutsideMethod('Uniform MLE floor: all omitted material above gross centroid not proved')
    Ae=A-t*(b-be)-t*(hi-lo)
    S=A*cy-t*(b-be)*a-t*(hi**2-lo**2)/2
    Qy=Ix+A*cy**2-t*(b-be)*a**2-t*(hi**3-lo**3)/3
    ce=S/Ae;Ic=Qy-S*S/Ae
    if not 0<Ae<=A or not 0<Ic<=Ix or not r<ce<=cy<a-r or not top>cy:
        raise mle.OutsideMethod('Uniform MLE floor: retained core/centroid interval unavailable')
    # psi(ce) decreases with ce; sigma1/stress decreases with ce.
    psi_lo=(r-cy)/(a-r-cy);psi_hi=(r-ce)/(a-r-ce)
    sig1_hi=fy*(a-r-ce)/(top-ce)
    kw_lo=4+2*(1-psi_hi)+2*(1-psi_hi)**3
    lw_hi=energy._sqrt_upper(sig1_hi/(E*kw_lo))*B/(t*C('0.95'))
    bw_lo=B*_rho_lower(lw_hi)
    # On psi<=-.236, b1+b2=b_eff*(1/(3-psi)+.5), increasing in psi.
    # Otherwise the sum is b_eff. The lower bound is continuous-safe at
    # the rounded branch switch, using min(1,...) when the interval straddles.
    partition_factor=min(C(1),1/(3-psi_lo)+C('0.5'))
    partition_lo=bw_lo*partition_factor;bc_hi=a-r-ce
    full=lw_hi<=C('0.673') or partition_lo>=bc_hi
    if not full:
        raise mle.OutsideMethod('Uniform MLE floor: full web not proved over all sigma in (0,fy]')
    fibre_distance=max(top-ce,cy+t/2)
    W=Ic/fibre_distance
    exact=dict(l0_upper=l0hi,Is=Is,Ia_upper=Ia_hi,ratio_lower=ratio,
        flange_width_lower=be,lip_width_lower=ds,A_core=Ae,centroid_lower=ce,
        centroid_upper=cy,I_core=Ic,Wc_lower=W,outer_fibre_distance_upper=fibre_distance,
        psi_lower=psi_lo,psi_upper=psi_hi,
        web_sigma1_upper=sig1_hi,web_k_lower=kw_lo,web_lambda_upper=lw_hi,
        web_partition_lower=partition_lo,web_compressed_width_upper=bc_hi)
    return W,dict(method='retained_core_uniform_modulus_floor',source=mle.SOURCE_MLE,
        stress_interval_MPa=[0.,float(fy)],stress_zero_excluded=True,
        Wc_uniform_lower_mm3=energy._directed(W,False),
        Wfirst_uniform_lower_mm3=energy._directed(W,False),
        tension_first_yield_also_bounded=True,
        outer_fibre_distance_upper_mm=energy._directed(fibre_distance,True),
        centroid_interval_mm=[energy._directed(ce,False),energy._directed(cy,True)],
        web_full_for_entire_stress_interval=True,
        web_lambda_upper=energy._directed(lw_hi,True),
        web_partition_lower_mm=energy._directed(partition_lo,False),
        web_compressed_width_upper_mm=energy._directed(bc_hi,True),
        flange_k_lower=None if kmin is None else energy._directed(kmin,False),
        all_omitted_material_above_gross_centroid=True,
        retained_y_measure_dominated_by_every_effective_y_measure=True,
        spatial_flange_subset_or_tensor_claimed=False,
        central_inertia_ordering='min_c integral_core(y-c)^2 <= min_c integral_effective(y-c)^2',
        compression_modulus_ordering='Ieff >= Icore and ytop-ceff <= ytop-ce_core',
        first_yield_ordering='ceff+t/2 <= ce_gross+t/2; both distances <= max(ytop-ce_core, ce_gross+t/2)',
        resistance_monotonicity_assumed=False,local_elastic_critical_inferred=False,
        exact_bounds={k:str(v) for k,v in exact.items()},
        arithmetic_scope='Exact supplied rounded-contour scalar properties and printed coefficients; geometry/property approximation is unchanged')


def resistance_at_floor(index, *, material, Me_lower_bound_Nmm):
    """NBR FLT arithmetic floor, not qualification of the supplied Me."""
    m=provider.material_values(material)
    me=provider.positive(Me_lower_bound_Nmm,'Me floor')
    witness=provider.strong_capacity_at_me(index,material=m,Me_Nmm=me)
    W=witness['Wc_gross_mm3'];fy=m['fy_MPa'];gamma=m['gamma']
    chi,chi_proof=chi_envelope(W,fy,me)
    if witness['method']=='NBR9.8.2.2(b)_MSE':
        ml=witness['effective_section']['Ml_Nmm']
        helper=nbr_resistance_floor(W,fy,ml,me)
        R=Q(W)*Q(fy)/Q(ml)
        reduced_lambda_upper=energy._sqrt_upper(chi*R)
        if reduced_lambda_upper<=C('0.673'):
            resistance_factor=chi
        else:
            # chi*rho(sqrt(chi*R)) = sqrt(chi/R) - .22/R.
            # Capping rho at 1 preserves a monotone function of chi.
            resistance_factor=min(chi,_sqrt_lower(chi/R)-C('0.22')/R)
        exact=Q(W)*Q(fy)/Q(gamma)*resistance_factor
        # Preserve the established implementation as an additional, possibly
        # more conservative cap; its fixed 1.1 is explicitly normalized.
        helper_cap=Q(helper['MRd_flt_Nmm'])*Q(helper['gamma'])/Q(gamma)
        value=min(exact,helper_cap)
        method='T12b_MSE_existing_envelope_with_exact_algebra_guard'
        proof=dict(existing_nbr_resistance_floor=helper,
            exact_uncapped_MRd_fraction=str(exact),helper_normalized_cap_fraction=str(helper_cap),
            local_Ml_Nmm=ml,local_reduced_lambda_upper=energy._directed(reduced_lambda_upper,True),
            local_factor_lower_fraction=str(resistance_factor),
            monotonicity='chi*rho_capped(sqrt(chi*W*fy/Ml)) is increasing; branch derivatives are positive; rounded overshoot capped at gross',
            local_coefficients=dict(transition='0.673',reduction='0.22'),gamma_used=gamma)
    elif witness['method']=='NBR9.8.2.2(a)_MLE':
        p,props=provider._geometry(index)
        wmin,proof=mle_uniform_modulus_floor(p,props,m)
        value=chi*Q(fy)*wmin/Q(gamma)
        method='MLE_uniform_retained_core_floor'
    else:
        raise mle.OutsideMethod('No qualified resistance-envelope bridge for provider method')
    if value<=0:
        raise mle.OutsideMethod('Nonpositive resistance floor')
    floor=energy._directed(value,False)
    if floor<=0:
        raise mle.OutsideMethod('Positive exact resistance floor underflows finite output; no utilization formed')
    return dict(eligible=True,method=method,MRd_lower_bound_Nmm=floor,
        provider_schema=provider.SCHEMA,
        exact_MRd_floor_fraction=str(value),chi_envelope=chi_proof,
        resistance_proof=proof,provider_at_floor_witness=witness,material=m,
        Me_lower_bound_used_Nmm=me,Me_qualified_by_this_helper=False,
        lower_bound_for_all_Me_at_or_above_floor=True,
        local_and_FLT_component_only=True,distortional_resistance_included=False,
        physical_resistance_bound=False,whole_member_approved=False)


def qualify_family(data, actions, *, formula_nu=.3, gamma=1.1, energy_evidence=None):
    """Fresh bridge or fully replayed supplied energy certificate; no cache trust."""
    bound=(energy.qualify_family(data,actions) if energy_evidence is None else
           energy.validate_saved(energy_evidence,data,actions))
    out=dict(schema=SCHEMA,scope=SCOPE,energy_floor=bound,
        catalog_index=data['catalog_index'],physical_span_mm=data['L_mm'],
        energy_hypotheses=copy.deepcopy(bound.get('energy_bound_hypotheses')),
        formula_nu=formula_nu,gamma=gamma,
        resistance_floor_eligible=False,MRd_lower_bound_Nmm=None,
        utilization_upper_bound=None,component_sufficient=False,
        status='pending_energy_floor',failure_proven=False,
        floor_exceeded_means='inconclusive_not_failed',
        physical_supports_created=False,demand_span_changed=False,
        primary_torsion_assessed=False,biaxial_stability_assessed=False,
        actual_load_capacity_qualified=False,whole_member_approved=False)
    if not bound['elastic_reference_eligible']:
        out['reason']=bound['reason']
    else:
        m=dict(bound['source_binding']['material'],nu=formula_nu,gamma=gamma)
        try:
            cap=resistance_at_floor(data['catalog_index'],material=m,
                Me_lower_bound_Nmm=bound['Me_lower_bound_Nmm'])
        except mle.OutsideMethod as exc:
            out.update(status='pending_resistance_envelope',reason=str(exc))
        else:
            demand=C(bound['exact_load_quantities']['Mmax_fraction'])
            capacity=Q(cap['MRd_lower_bound_Nmm'])
            sufficient=demand<=capacity
            out.update(resistance_floor=cap,resistance_floor_eligible=True,
                MRd_lower_bound_Nmm=cap['MRd_lower_bound_Nmm'],
                maximum_reference_moment_Nmm=bound['maximum_reference_moment_Nmm'],
                demand_exact_fraction=str(demand),
                utilization_upper_bound=energy._directed(demand/capacity,True),
                component_sufficient=sufficient,
                status='sufficient_under_declared_operator' if sufficient else 'inconclusive_floor_exceeded',
                reason=('Solicitação forte não excede o piso NBR condicional demonstrado.' if sufficient else
                    'Solicitação acima de um piso suficiente não prova reprovação; requer referência resistente mais precisa.'))
    out['snapshot_sha256']=digest(out)
    return out


def validate_saved(evidence,data,actions,*,formula_nu=.3,gamma=1.1):
    expected=qualify_family(data,actions,formula_nu=formula_nu,gamma=gamma)
    if evidence!=expected:
        raise ValueError('Piso resistente/hipóteses/testemunhas alterados; recalcule explicitamente.')
    return copy.deepcopy(expected)
