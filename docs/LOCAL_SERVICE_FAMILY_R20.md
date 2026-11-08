# R20: local strong-axis service deflection for the complete Ue family

This update connects the requested one-direction service deflection to the
own-contour catalogue route. It does not change the member actions, profile
self-weight, physical span, effective lengths, deflection limit, ELU/FLT
denominators, torsion checks, or support-contact checks.

## Method coverage

The documentary registry contains 83 Ue rows, of which 66 meet the existing
complete-source selection policy. The fresh local service route now offers:

- 62 rows: an own-contour local elastic moment from NBR 14762:2010 Table 12(b),
  consumed as a separate `Ml_SLS` by the existing sectionwise MSE inertia law
  of §9.8.5(b). No published critical from a different contour is transferred.
- Four rows, Ue300×100×25 with t=3.35, 3.75, 4.25 and 4.75 mm: Table 12(b)
  does not cover D/bw=25/300. The service calculation instead uses §9.8.5(a)
  MLE, with the effective compression stress found by successive scalar
  compatibility iterations (§9.2.2.2), and integrates M/(E Ixef) pointwise.
  It does not manufacture an elastic critical from a resistance or inertia.

The MLE branch reuses conventional NBR/CBCA strong-axis effective widths with
reduced flange/lip and a checked full-effective web. It checks the actual
service compression and tension against fy. It does not require the section
at fy to remain in the implemented web branch when the service stress is lower.
If the actual service section needs an unsupported web branch or the numerical
compatibility/integration does not converge, it reports that specific pending
state without a conclusive limit index. Availability of a method for all 66
rows is not a claim that every load or material satisfies its domain or limit.

## Signed actions and preservation

The new qualified local service path accepts opposing uniform and point loads.
Moment zeros partition intervals of monotone slope; all stationary deflections
and physical endpoints are compared. MSE quadrature also splits at both signed
inertia transitions. Same-sign MSE calculations retain the original numerical
path. Legacy inputs/results and the old single-maximum protocol are unchanged.

The complete physical span and already-combined SLS loads are used. Profile
self-weight is not added again. Effective lengths remain resistance inputs;
no intermediate displacement support is invented. The own-contour catalogue
activation remains restricted to isolated purlins. Existing wall-girt and
three-girt routes have not been expanded to this catalogue by this update.

The selected objective is the local strong-direction flexural deflection,
not a combined bending/warping/torsional service displacement. No new torsion
or rotation limit is introduced. Imported inputs retain their historical
choice until the local objective is explicitly selected for a new calculation.

## Traceability and validation

The new service inputs and calculated evidence are frozen in the consumed
snapshot. Geometry, material, formula arithmetic and application domain are
checked before the fresh calculation. MLE consumers also compare the catalogue
index with its canonical own contour, preventing a rehashed snapshot from
using another thickness. Reports read saved evidence without rerunning solvers.

Regression receipts distinguish author tests, independent review and the final
integrated run. Test counts are not added when suites overlap. Synthetic cases
and numerical comparisons validate the implementation; they are not structural
homologation, validation of a private project, or proof of a hosted deployment.

Primary source: ABNT NBR 14762:2010, §§9.2.2.2, 9.2.3 and 9.8.5, Table 12.
Source PDF SHA256:
`c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
The source PDF is not redistributed in this update.
