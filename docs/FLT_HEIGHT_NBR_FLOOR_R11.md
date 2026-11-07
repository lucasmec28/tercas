# Sufficient NBR resistance bridge for the declared FLT energy operator

## Status and integration contract

`tercas.flt_height_nbr_floor.qualify_family(data, actions, formula_nu=.3,
gamma=1.1, energy_evidence=None)` consumes the conditional energy floor in
`flt_height_energy_floor.py` and returns a **sufficient pure-strong-bending
local/FLT check**. It does not replace historical evidence or change an
application denominator automatically. The independent NBR provider is
`nbr_ue_family` schema v2 (R11). This change introduces no application/UI/global
hook and changes no previous module.

- `energy_evidence`, if supplied, is fully replayed against the current inputs;
  an integrity hash alone never authorizes its use.
- `MRd_lower_bound_Nmm` is a resistance floor, deliberately not `MRd_Nmm`.
- `component_sufficient=True` / `sufficient_under_declared_operator` means the
  exact physical-span strong moment does not exceed the conditional floor.
- `inconclusive_floor_exceeded` means this sufficient test cannot decide.
  It **never means failure**, and `failure_proven` remains false.
- `pending_resistance_envelope` means the uniform proof is outside its domain;
  no substitute section/critical value or coefficient is inferred.
- `actual_load_capacity_qualified`, `whole_member_approved`,
  `physical_supports_created`, and `demand_span_changed` remain false.
- `resistance_at_floor(index, material=..., Me_lower_bound_Nmm=...)` is the
  lower-level resistance bridge. It does not itself qualify the elastic Me.
- `validate_saved(...)` recomputes every load, source, energy coefficient,
  exact maximum, resistance witness, interval, and sufficient verdict.

An application consumer may place this as a **separate sufficient check** beside its exact
or approximate component references. It must not relabel an exceeded floor as
an exceeded resistance or silently make the conditional operator physical.
Distortion, shear, primary torque/bimoment, biaxial coupling, service and other
member checks remain independent requirements.

## Elastic and length hypotheses are unchanged

See `FLT_HEIGHT_ENERGY_FLOOR_R11.md`. The energy bound assumes end twist zero
and explicit lower Euler energy inequalities Ny and T associated with the
resistance lengths. It does not infer their physical realization. Ly/Lz below
Lphysical do not create supports and do not turn the bound into a lower bound
of the historical full-span free-warping solver. All q/P locations, heights,
normal/parallel action audits and physical-span demand witnesses remain in the
nested energy certificate. No Me is rescaled after a solver.

## 1. A chi floor over every larger elastic Me

Let A=Wc,gross fy, lambda²=A/Me, and m be the supplied positive Me floor.
The NBR rounded FLT function is not globally monotone at lambda=1.336. Define
c=1.11(1−0.278×1.336²). For lambda_m²=A/m:

- lambda_m≤0.6: chi_min=1;
- 0.6<lambda_m<1.336: chi_min=1.11(1−0.278 lambda_m²);
- lambda_m≥1.336: chi_min=min(1/lambda_m²,c).

Then chi(Me_real)≥chi_min for every Me_real≥m. The jump at lambda=0.6 is
upward when Me increases, so it introduces no additional lower limit. The
printed coefficients are stored as exact decimal rationals; no fitted
coefficient or empirical margin is introduced.

## 2. The 62 Table12(b) MSE rows

The existing `direct_roof_envelope.nbr_resistance_floor` remains the source
implementation and is stored verbatim as a witness. Its fixed gamma=1.1 is
explicitly normalized to the bridge's supplied gamma. An independent exact
algebra guard is also applied; the returned floor is the minimum of the two.

For R=Wc fy/Ml, use the capped local curve rho_c=min(1,rho). The reduced-stress
resistance factor f(chi)=chi rho_c(sqrt(chi R)) is increasing:

- in the gross part f=chi;
- in the reduced part f=sqrt(chi/R)−0.22/R, whose derivative is positive;
- capping the slight rounded rho overshoot at 1 prevents material creation and
  removes the local rounded transition issue.

Evaluating f at chi_min therefore provides a floor of every larger-Me MSE
resistance, without changing the original curve or its historical replay.
The same increasing function at chi≤1 also does not exceed the local-only
resistance. Ml is calculated only inside Table12 by the qualified provider;
no Pierin critical is transplanted.

## 3. The four conventional MLE rows outside Table12

For catalog indices 79–82 the bridge does **not** assert that
sigma Wcef(sigma) is monotone. Instead it establishes a single modulus floor
for every 0<sigma≤fy in the scalar NBR/CBCA strong MLE convention. The check is
parameterized and re-proved for the current geometry/material, not authorized
by membership in that list.

### Uniform effective-width limits

Use the provider's flat dimensions b,d,B and NBR §9.2.3 stiffener equations.
Ia(sigma) is nondecreasing. With an upper enclosure of Ia(fy), define
r_min=min(1,Is/Ia_upper). For the required-stiffener branch,
n=max(1/3,0.582−0.122 lambda_p0) lies within [0,1], and r^n≥r≥r_min.
The coefficient c_f is 3.57 for D/b≤0.25 or 4.82−5D/b otherwise. It is positive
in the guarded D/b≤0.8 domain. Thus k≥min(4,c_f r_min+0.43)=k_min.

A square-root upper enclosure of the slenderness at fy/k_min yields a lower
flange width b_min. A corresponding fy/lip enclosure gives d_eff,min, and
retained lip width ds_min=r_min d_eff,min. The stocky branch retains the full
flange and at least these widths. Capped rho is nonincreasing in slenderness.
No noninteger power is evaluated to establish the bound.

### Retained measure and first yield on both sides

Remove from the gross section the maximum omitted top flange width b−b_min
and the lower portion of the compressed straight lip, retaining ds_min next
to its corner. Preserve all corners, web, tension flange and tension lip.

This is a **dominated measure in y**, not a claim that a fixed flange band in
x is contained in every effective cross-section. Every flange contribution
has the same y-coordinate in this scalar convention; its partition between
web and lip does not affect A, Sy or Qy. No 2D tensor or stress operator follows.

All removable material must lie above ce_gross. The retained measure has
centroid ce_core, and adding any admissible material raises its centroid:
ce_core≤ce_eff≤ce_gross. Central inertia satisfies
Icore=min_c integral_core(y−c)² ≤ min_c integral_eff(y−c)²=Ieff.
Both extreme-fibre distances are bounded by
Dmax=max(y_top−ce_core, ce_gross+t/2). Consequently
Wfirst_eff≥Icore/Dmax=W_min, and Wc_eff≥W_min as well. This explicitly includes
first yield of the tension fibre and does not rely on bit-exact gross symmetry.

### Full-web validity throughout the stress interval

The retained-section argument is admitted only after proving the conventional
full-web branch consistently for every sigma≤fy. Require
r<ce_core≤ce_gross<a−r, proving web stress reversal throughout the interval.
The largest compressed web-end stress is
sigma1_upper=fy(a−r−ce_core)/(y_top−ce_core).
Psi(ce)=(r−ce)/(a−r−ce) decreases with ce, so
psi_gross≤psi≤psi_core<0. The NBR Table5 coefficient (AA element; CBCA Table4.2) is increasing as psi decreases;
therefore k_web,min=k(psi_core). This gives lambda_web,upper and bweb,min.

For psi≤−0.236 the partition sum is b_eff[1/(3−psi)+1/2]; for the other branch
it is b_eff. A safe interval lower bound is therefore
bweb,min×min(1,1/(3−psi_gross)+1/2).
It must be at least bc_max=a−r−ce_core, unless lambda_web,upper≤0.673 already
proves full effectiveness. Failure leaves the bridge pending. No sampled
stress grid is used to establish this continuum proof.

Finally MRd_min=chi_min fy W_min/gamma. This bounds both the provider's FLT
component at every greater Me and its local first-yield component. It is not a
bound on distortional or biaxial resistance.

## Numerical certificate and limits

Loads and Mmax are inherited as exact rationals from the energy certificate.
The chi envelope, MLE width/core/web proof, moments and final resistance guard
use exact rational arithmetic, integer-enclosed square roots, and directed
final conversion. A final positive exact floor which underflows floating
output fails closed before any utilization division. Demand comparison uses
its exact fraction, not the rounded moment shown in the UI. Utilization is
rounded upward.

This numerical statement is conditional on the **supplied scalar properties
of the own rounded contour and the documented scalar section convention**.
It does not certify errors in geometry discretization or physical conditions.
The ordinary NBR provider output is retained as an audit witness, not mistaken
for an interval certificate. Source coefficients and every intermediate bound
are preserved for replay.

## Verification

`tests/test_flt_height_nbr_floor.py` covers all 66 rows, the four MLE rows in
fy=250/300/345/350 MPa, independent Decimal core moments, additional stress
sweeps, both rounded chi transitions, actual larger-Me curve comparisons,
explicit gamma, physical-span load cancellation, sufficient/inconclusive
semantics, zero resultant bending, tamper/replay and underflow.

`qa/flt_height_effective/generate_nbr_floor.py` records 264 synthetic family /
material cases with full-span4100mm, independent Ly2050mm/Lz2733mm, top q+P,
P at1410mm, inclination5.71°, and own self-weight separately at the CG. This
matrix is scalar only, no member matrix/eigen solver or physical-bracing test.
The count of sufficient cases is reported as conditional component outcomes,
not approved members.

A separate algebra and static-code review found no blocker within this
restricted scope. This is not professional structural certification or physical
verification. This file is a derivation, not a claim that NBR
prints this derived conservative energy/resistance bridge verbatim.

## Sources

- NBR14762:2010 §§9.2.2,9.2.3,9.8.2.1(a)/(b),9.8.2.2(a)/(b), through the
  versioned NBR provider and its source documentation.
- CBCA2016 §6.3.1.1, conventional scalar strong MLE preserving corners;
  https://www.skylightestruturas.com.br/downloads/101497_manual_lsf_engenharia_2016.pdf
  (source SHA256 and checked pages are recorded in `nbr_ue_family_expansion`).
- Sahraei2017 Eq2, energy starting point;
  https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf
- Existing rounded-curve envelope: `direct_roof_envelope.nbr_resistance_floor`;
  no original formula or historical snapshot is overwritten.
