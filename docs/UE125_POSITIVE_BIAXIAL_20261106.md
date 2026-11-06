# Ue125 positive weak-axis integration, restricted scope

New source kind: `own_catalog_Ue125_positive_bending_components_v3`.
The pre-existing v1/v2 saved readers remain unchanged in meaning; opening a saved
record never promotes it to v3. Fresh calculation can use the independently
reviewed own-contour positive reference provider. No Ue100 capacities are used.

## Resistance and physical boundary

The strong resistance remains the per-combination r8 minimum of own local,
load-height FLT and approximate distortional components. The positive weak
resistance is the provider's minimum of local first yield and Annex E at the
physical span, Cm=1, N=0, fork ends/free warping. The provider's typed conventional
flange/lip D nonapplicability is confined to positive pure weak bending of the
pinned smooth-web/simple-lip contour. It does not waive strong D, negative weak
D, torsion or first-order applicability. The separate-axis §9.9 criterion uses
these uniaxial reference capacities; this does not introduce an additional
combined distortional verification. Manual lengths do not
create supports. No panel restraint is credited.

Actual load applicability continues to require the existing independently
preserved classifier for every parallel action, `Fparallel*(x-CT)>=0`. Net
cancellation and a positive net moment do not replace that classifier.

## Continuous mathematical certificate

For every piece on either side of the prescribed P position, all coefficients,
interval endpoints and the interior quadratic vertex are recorded. Minimum My
at these candidates proves the sign over the complete physical span. Negative
My anywhere yields `weak_negative` pending and no interaction index. No negative
capacity is fabricated. Identically zero My reduces to the strong term without
requiring Ry or fabricating Me.

When My is nonnegative, the envelope consists of exactly two quadratics per
piece, `+Mx/Rx+My/Ry` and `-Mx/Rx+My/Ry`. Endpoints and interior vertices of each
suffice for the maximum. The saved governing moments are concomitant.

The exact simply-supported identities M(0)=M(L)=0 are applied at physical
supports. This avoids cancellation errors at L becoming a fictitious negative
My. There is no tolerance clamp or sign suppression in the interior.

The saved reader independently derives coefficients from saved loads, checks
all proof rows and candidate coverage, and compares the governing witness
against every required candidate. Canonical JSON equality distinguishes booleans
from numbers and rejects extra keys in certificates/consumer records. Nonfinite
inputs and intermediate/output values fail. Rehashing the container does not
make an altered witness or incomplete certificate valid.

## Presentation and global limits

A mixed inventory with positive evaluated cases and negative pending cases is
explicitly partial. The specific §9.9 checklist line may use the valid component;
torsion, linear-response applicability, combined ELS and global approval are not
promoted. Existing small-rotation warnings stay intact. Word and JSON exports
use the saved certificates without calling the structural solver.

## Focused QA

All fixtures are synthetic. No real project was read/copied. BLAS threads=1.

- 139 scalar/provider/consumer tests initially passed (0.82s).
- 46 reader/history/consumer tests passed (2.56s), including v1/v2 preservation
  and v3 roundtrip, report, removed proof, changed witness and rehashed tampering.
- Three fresh direct synthetic solves (positive/negative/zero parallel) passed
  (3.07s).
- Area tests passed (8.09s): 40 ELU and 2 ELS, center/support-limit P positions,
  exact inventory/source binding and separate ELS-only selection.

These are focused checks, not the entire application regression suite and not
experimental or physical design approval. No publication is performed here.
- Final scalar/provider/read selection after all endpoint hardening: 178 passed,
  7 excluded (2.45s). Excluded cases are the separately executed fresh/area solves
  and two old solver-specific tests, not failures.
- New real AppTest: 1 passed (18.66s), including calculation, JSON/Word export,
  expected linear/rotation warnings and rerun with structural solver blocked.

The area fixture originally exposed endpoint cancellation and was corrected by
an analytical support identity, then rerun. An initial mutation test accidentally
replaced an already-zero polynomial by zero and was corrected to a genuinely
changed coefficient. The UI fixture was made internally consistent by selecting
custom steel for fy=300 MPa; expected first-order warnings are asserted rather
than treated as computation failures.

Final independent static review accepted consumer, saved reader, UI and panorama.
The final numeric-station guard rejects False as x=0 in an all-zero case.
The reviewer did not execute tests or solvers.
