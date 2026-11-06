# Positive pure weak reference: conventional D applicability

Isolated module `ue_catalog_nbr_weak_positive`, based on the reviewed local MLE
and Annex E reference components. No production consumer is changed here.

API: `qualify_reference(data, sign='positive', axial_force_N=0.)`, with sign and
axial force required keyword arguments. Only positive pure My_app/N0 is accepted.
Zero My in a combination means no weak demand, not a separate D exemption.
The mathematical section remains the exact pinned Ue125x50x17x2 ri2, fy300,
fu400, E200000, G77000, smooth unperforated web and simple lips.

## Basis and limits

AISI RP21-01 (2021), Example I, printed p5/PDF10 shows a conventional symmetric
lipped C with smooth web and rounded corners. Printed p10/PDF15 explicitly says:
“The potential limit states are yielding and global buckling (Mne), local buckling
(Mnl), since lips are in tension (no distortional buckling).” The following
sentence separately excludes global buckling because that example is braced.
Printed p11/PDF16 takes only min(Mne,Mnl).

This is technical evidence for susceptibility, NOT NBR normative text, not
imported DSM resistance, not evidence of roof-sheet restraint, and not a
universal law for all sections whose lips are in tension. NBR14762:2010 §§9.3,
9.8.2.3 and CBCA2016 p76 condition distortional verification on susceptible
sections. No Table14 exemption is claimed. In particular, a stiffened web,
complex returns, openings, different section or compressive lip stress is not
covered by this decision.

Source: https://www.buildusingsteel.org/wp-content/uploads/2021/03/AISI-RP21-01-Development-of-Design-Tables-for-the-Cold-Formed-Steel-Cross-Sections-in-AISI-D100.pdf
CBCA: https://www.skylightestruturas.com.br/downloads/101497_manual_lsf_engenharia_2016.pdf

## Geometric proof and typed result

Compression-positive stress is -My_app*(x-CG)/Iy. Under positive pure My, both
lips are therefore in tension if all their exterior fibers have x>CG. The lowest
certified effective web width, obtained at uniform fy, bounds all effective
centroids used by local MLE and Wcef(chi*fy): CG<=17.793314mm. Lip exterior
fibers have x>=47mm; adjoining bend exterior fibers have x>=44mm. Both strict
inequalities are checked. This proof includes finite thickness rather than only
midsurface coordinates, and does not change the global analysis centroid.

The result records `not_applicable_to_positive_pure_weak_reference` for the
conventional flange-lip distortional mechanism, with contour hash, material,
source pages and proof. Mdist_Nmm and MRdD_Nmm are None, never zero, infinity or
an invented critical. D strong, negative weak, and distortion under the actual
combined stress/torsion state are not altered or assessed.

The positive pure reference capacity is min(local-first-yield, FLT-reference).
The nonapplicable D component is explicitly excluded, not inserted numerically.
Annex E physical span, fork/free-warping, no intermediate restraint, Cm1 and
shear-center-reference conditions remain. Actual actions still need the separate
verified per-action position classifier; this module never approves a real
combination, §9.9, ELS, torsion, physical section or whole member.

The saved reader replays scalar arithmetic and compares the entire canonical
certificate, rejecting rehashed alterations, changed material/geometry/span,
source/proof/scope edits and bool-for-number substitutions. Inputs are preserved.

Final independent static review accepted. Combined 88 focused scalar tests passed
in 0.73 seconds; see qa/ue125_weak_positive/receipt.json. No member solver or UI
was run, and no release was published.
