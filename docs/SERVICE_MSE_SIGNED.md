# Optional signed local MSE deflection

`tercas.nbr_service_strong_mse_signed.peak_deflection` extends the numerical
maximum search to opposing signed uniform and point service loads on a simply
supported physical span. It was initially delivered as a pure, isolated module.
The R20 integration now connects it only to the qualified local service path
for opposing q/P actions. Same-sign actions retain the existing numerical path.
It leaves `core.protocolo_ief` and its same-sign validation unchanged.

Inputs use N, mm and MPa. Supply a qualified positive `Ml_Nmm`; this module does
not calculate or infer an elastic critical moment. It calls the existing
NBR 14762:2010 9.8.5(b) stiffness law, including the disclosed conservative
`min(Ig, Ief_literal)` implementation envelope. There is no load-factor,
self-weight, limit, biaxial, torsional, FLT or ELU change.

The unit-load integral supplies signed deflection and slope. Between a point
load and roots of M, curvature has one sign and slope is monotone. All isolated
stationary points are therefore bracketed on these intervals, and the absolute
values at them and at physical interval endpoints are compared. Identically
zero moment intervals are affine; their endpoint values suffice even if slope
is zero throughout. Quadrature additionally splits at M = ±Mthreshold, with
Mthreshold = ((1 + sqrt(1 - 4 × 0.22))/2)² Ml, the actual onset of stiffness
reduction under the clamp. Quadrature uses the existing ULP breakpoint
coalescence only, not a physical load-patch tolerance.

Focused tests compare unchanged same-sign legacy results, independent Simpson
integration and a constant-stiffness closed form. They include three stationary
points, a noncentral global peak, sign reversal/reflection, stiffness transition
crossings of both signs, minima of Ief, zero actions and support/ULP positions.
