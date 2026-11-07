# Weak-negative local resistance: bounded review of simplified alternatives

Base: aa1eef2887b1177b270c5990e5434c5bf3162134. Review date: 2026-11-07.
No runtime, application, UI, global property, or frozen source changed.

## Finding

Neither investigated shortcut has a sufficient demonstrated basis to qualify
new weak-negative local resistance. This is a limitation of the demonstrated
method, not a proof that the sections fail or that no valid method exists.
The existing pending state must remain. In particular, a stress selected below
fy is not a replacement yield stress.

## Source checked visually

User-supplied ABNT NBR 14762:2010 PDF, SHA256
`c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
PDF pages are one-based; printed page = PDF page minus six.

- PDF33/printed27, 9.2.2.1(a): compression stress for the local yielding limit
  state is calculated on the effective section when it reaches first yield.
  Where maximum stress is tensile, the section is obtained by successive
  approximations. Paragraph (b) instead uses chi times fy for instability.
- PDF36–37/printed30–31, 9.2.3: edge-stiffened **uniformly compressed** elements;
  stress explicitly refers back to 9.2.2.1. The stocky branch lambda_p0<=0.673
  needs no edge stiffener. The other branch includes Is/Ia and the corresponding
  reduced lip width and unequal allocation of flange effective widths.
- PDF51/printed45, 9.8.2.1: MRd=Wef*fy/gamma. Its MLE option explicitly
  requires the first-yield stress. Its MSE option permits a local critical
  moment from elastic stability analysis, not an unidentified borrowed value.
- PDF52/printed46, Table12 title: formulas apply to bending about the axis of
  greatest inertia. They are not a weak-axis formula.
- PDF38/printed32, 9.3 continuation: approximate elastic formulas are discussed
  for distortion. This is not a general license for a local-resistance formula.

## Route 1: fully effective section below fy

It is possible to calculate a sufficiently low stress sigma0 for which plate
slenderness and edge-support tests show full effectiveness. That arithmetic
alone proves neither the first-yield effective section nor the inequality

    fy * Wef(first yield) >= sigma0 * Wgross.

The missing step is a valid comparison theorem for the *complete* weak-axis
MLE section under the actual gradient, including centroid migration, partial
edge restraint, lip-width reduction, and the governing extreme fibre. There
is no qualified reduced-section mapping for that gradient in this branch, so
monotonicity of a single plate's rho(sigma) cannot establish the inequality.
An admissible lower bound of the local elastic critical moment, with its own
qualified mechanical operator and sign-specific stress field, could instead
feed 9.8.2.1(b). A full-effectiveness threshold is not automatically that bound.
Do not store sigma0*Wgross/gamma as a qualified resistance floor.

## Route 2: disregard edge stiffener and use AA/AL plates

Tables5/6 supply effective widths for their boundary-condition cases. They do
not by themselves authorize replacing this Ue by a U while retaining the Ue
stress field, centroid, section modulus or lip resistance. A valid route would
need a cited normative substitution or a demonstrated conservative comparison
of the complete sections. Treating the flange as AA without adequate edge
support is precisely the missing proof; treating it as AL and simply deleting
lip material is a different section and is not yet a demonstrated bound for
the original member. Distortional qualification cannot repair this local gap.

## Reproduced scalar coverage

Executed `nbr_ue_family.assess` for all `pierin_ue_registry.new_study_indices()`
at physical span 6000 mm, unchanged default material except fy. No new solver.
For fy250/300/345/350 MPa, complete weak-negative references = 55/51/45/44 of66.
Missing local references = 11/15/21/22. Their union is:
20,32,40,41,47,48,49,50,51,53,54,55,56,57,62,63,64,65,66,79,80,81.
These are existing-coverage regression observations, not tests validating a
new method. No runtime module or resistance test was added because there is
no qualified new resistance to exercise.

## Exact next input needed

One of:
1. A sourced MLE treatment for an edge-stiffened flange with Is<Ia under this
   weak-axis stress reversal, including effective-width locations and lip
   reduction, sufficient to solve the effective section at first yield; or
2. A qualified, sign-specific local elastic critical moment (or proven lower
   bound thereof) for each own contour/stress field under 9.8.2.1(b); or
3. A cited and applicable conservative replacement theorem for the complete
   section, not just a plate coefficient or a reduced material fy.

No research expansion or new FSM solver is initiated by this review.
