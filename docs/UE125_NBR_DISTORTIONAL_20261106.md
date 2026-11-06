# Own Ue125 approximate strong-axis distortion

This qualification is limited to the explicitly adopted public nominal rounded
Ue125×50×17×2 contour, inner radius 2 mm, E=200000 MPa, G=77000 MPa,
fy=300 MPa and fu=400 MPa. Nominal identity, source nodes, properties and material
remain pinned to the same own-contour marker. No private project actions,
identifiers, or imported criticals are used in the implementation or tests.

## Normative route and limits

NBR14762:2010 §9.3 permits elastic stability theory or a direct approximate
formulation adequately correlated with theoretical results. The general
elastic flange-enrijecedor formulation in ANSI/SDI/AISI S100-2024 Appendix 2
is used here as an approximate Mdist under that route. Only the NBR14762
§9.8.2.3 resistance curve and γ=1.1 follow it. No AISI resistance or safety
factor is transplanted into the NBR calculation.

The implementation uses Table 2.3.3-1 and Eqs. 2.3.3.1-3,
2.3.3.2-1/2/4/5/6/7, visually verified in the current source. The general route
includes the 90° lip. The short preliminary commentary formula, whose stated
angle range excludes 90°, is not used. Current signs and definitions of xo,
xh and yo govern; the historical uncorrected notation is not reused.

This is a scalar reference capacity for pure symmetric strong-axis bending,
one web with edge-stiffened flanges to the same side, ideal nominal section
without holes, linear elastic stability and small rotations. Its two strong
bending senses are equivalent by symmetry. It does not qualify weak-axis
resistance, a combined stress buckling pattern, NBR §9.9, primary torsion,
bimoment, or physical adequacy of a first-order model at large rotations.
Physical holes, restraints and small-rotation applicability are not verified.

## Geometry and elastic parameters

Global Ix=1181287.6899091285 mm⁴ remains the own rounded contour value.
Sfc=Ix/(h/2)=18900.603038546056 mm³ is referenced to the exterior compressed
flange/web junction, at h/2=62.5 mm. It is not the midline extreme, lip tip,
or the flange-lip substructure's centroidal modulus.

The separate flange-lip substructure uses the sharp midline dimensions of
Table 2.3.3-1: b=bf−t=48 mm, d=D−t/2=16 mm, t=2 mm. These are not the flat
plate widths between tangent points. That table neglects corner radius and
retains its printed t³ contribution to Ixf. This approximation does not replace
the rounded global properties. Substructure axes pass through its centroid,
with x toward the lip and y downward:

- Af=128 mm², Jf=170.6666666667 mm⁴, Cwf=0.
- Ixf=2250.6666666667 mm⁴, Iyf=32256 mm⁴, Ixyf=4608 mm⁴.
- xo=18 mm, xh=−30 mm, yo=yh=−2 mm; xo−xh=b.

The explicit web-formula ν=0.3 is not inferred from rounded G=77000 MPa.
G is preserved in the flange torsional stiffness and in project demand.
Pure strong-axis reference uses ξweb=2, β=1 and kφ=0. There is no moment
gradient, roof, screw, finite-span or intermediate restraint credit.
Ld=Lcrd=377.7364353270835 mm is the unrestricted analytical half-wave, not a
new member span, physical restraint spacing or exact finite-member eigenmode.
This release requires the declared physical member length L_mm to be at least
Lcrd, in both fresh calculation and saved-evidence validation. The general
source defines Ld=min(Lm,Lcrd); this implementation does not claim its fixed
unrestricted result remains a qualified lower bound for shorter members, and
does not infer Lm from Ly/Lz. A shorter physical member keeps the local MSE
component in a partial v2 certificate, with D absent and the length limitation
explicit. This is a limit of the qualification, not a normative ban on short
members or a change to their input span.

## Results and independent correlation

The analytical stiffnesses are kφfe=4419.773305494531 N,
kφwe=4028.9334195601155 N, kφfg=10.633574352686908 mm² and
kφwg=0.7726481332734496 mm². They give Fcrd=740.7103215331766 MPa and
Mdist=13999871.753852382 Nmm. NBR λdist=0.6364091705693438 is below 0.673,
so ρdist=1 and MRd,dist=5154709.919603469 Nmm. Table 14 still does not exempt
the section; the new calculation resolves distortion rather than declaring
an exemption. No lower-bound or exact-eigenvalue claim is made.

Glauz (2018), Table 4, equation set 4, is the published correlation matching
the current strong-axis formula: 60 symmetric channels, prediction/FSM mean
0.966 and standard deviation 0.096. This is a family correlation, not a
guarantee that every prediction is conservative. The paper does not supply
this exact rounded contour or individual corner-radius qualification.

A bounded six-solve comparison supplements that source for the exact public
rounded contour. At half-waves 300, 377.7364353270835 and 480 mm, two levels of
flat subdivision preserve A/Ix/Iy to approximately 1.7e−15 relative. The refined
first eigenvalues are respectively 16.872366068209, 15.453308232180 and
16.505879077291 kNm. Central refinement changes the first value by about 0.106%.
All relative residuals are below 1e−6. The central mode exhibits nearly rigid
compressed flange-lip rotation and web flexure; this is not a constrained
pure-mode classification or proof of the continuous minimum.

FSM uses E=200000 MPa and ν=0.3, hence G=76923.076923 MPa. For an equal-material
comparison, the analytical result is 13.998367014889 kNm, or 0.905849207469 of
the central refined FSM value. The production result uses unchanged G=77000.
The approximation is about 9.4% below that sampled eigenvalue, not a universal
floor. The immutable research receipt is
`qa/UE125_DISTORTIONAL_CORRELATION_20261106.json`; its research-only flags are
preserved as historical evidence. The separate production certificate records
the subsequent narrow technical adoption, rather than rewriting that receipt.

The external worked benchmark RP07-2 pp.11.108–11.111 was replayed separately
with its historical corrected equations: Lcr=13.6388335178 in,
Fcrd=115.803474287 ksi and Mcrd=110.360710995 kip·in, matching the printed
13.639, 115.803 and 110.361. The same benchmark geometry under current 2024
equations gives 119.980585009 ksi; that is independently checked arithmetic,
not a published 2024 golden value. The current kfg drops the historical extra
q²Af(xo−xh)²(Ixyf/Iyf)² term; the expanded kwe coefficient changes from
19/60 to 2/5; the pure-strong kwg u⁴ coefficient changes from 50/56 to 1.
The historical benchmark's rotational spring is never used for this section.

## Saved contracts and separation of conclusions

`ue_catalog_nbr_distortional.qualify(data)` returns the exact-scope approximate
elastic/strength evidence. `validate_saved(evidence, data)` checks its complete
scalar reconstruction, scope, source identity and flags without catalog reads,
mesh construction, solver calls or migration.

`ue_catalog_nbr_bending_v2` embeds it and marks the strong scalar capabilities
available. Its local/FLT/distortional minimum is assembled separately per
combination by the roof adapter. `strong_bending_complete=True` is distinct
from `biaxial_qualified=False`: both weak-side resistances remain absent, so
§9.9 remains pending. Complete all-axis bending, combined stresses and whole
member approval remain false. The approximate critical does not resolve the
separate large-rotation/first-order applicability warning.

Historical `ue_catalog_nbr_bending_v1` snapshots retain missing D and their
partial status exactly. Reading them never invokes fresh qualification.
Only an explicit new calculation produces v2. Original input Ml/Mdist and
load data are untouched; old criticals remain audit-only. Scalar readers
reject edited capacities, sources, flags, geometry or material even if an
outer snapshot hash has been recomputed.

## Public sources

- [AISI S100-2024 and Commentary](https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf), PDF pp.217–220.
- [Glauz (2018)](https://scholarsmine.mst.edu/isccss/24iccfss/session1/3/), printed pp.49, 51–52.
- [RP07-2](https://www.cfsei.org/assets/docs/research_report/RP07-2.pdf), PDF pp.111–114.
- [2009 errata](https://buildusingsteel.org/wp-content/uploads/2020/12/CFSD-Pub-Errata-to-S100-v1-Amended-6-4-09-High-FINAL.pdf).

Source document hashes and roles are recorded in the certificate. Copyrighted
PDF copies are not committed. Tests use public nominal geometry and synthetic
actions only. No additional eigenvalue sweep is run at application runtime.
