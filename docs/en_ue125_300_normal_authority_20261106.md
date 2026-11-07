# Own Ue125×50×17×2, ri2: EN normal authority at fy300

This is an isolated four-signed-moment component authority, not an application
release or approval of a complete member. It does not modify the 83-row fy250
inventory, seven Ue100 certificates, torsion, global stability, first-order
analysis, or any consumer. N must be exactly zero.

## Normative and material basis

- EN 1993-1-3:2006, 3.2.1(5), refers material coefficients to EN 1993-1-1, 3.2.6.
  EN 1993-1-1:2005, 3.2.6 prescribes E=210000 MPa and nu=0.3.
  Public primary copy: https://www.gfos.unios.hr/download/en-1993-1-1-2005.pdf
  (printed page 28). These are **resistance-model** constants. The original
  analysis E=200000/G=77000 is not changed, read, or converted here. There is
  no inference of Poisson ratio from those analysis inputs.
- fyb=fya=300 MPa and gammaM0=1 are the explicitly requested nominal domain,
  not verification of a supplied steel product. No cold-work enhancement.
- EN 1993-1-3:2006, §§5.5 and 6.1.4, defines the local/distortional effective
  section and pure bending basis. Primary copy:
  https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf
- EN 1993-1-5:2006, 4.4(4), Eq4.4 and Note1, supports iteration with the
  effective section's compressive stress. Tables4.1/4.2 supply the internal
  web and free-outstand flange laws. Primary copy:
  https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.5.2006.pdf

## Geometry and signs

134 own rounded-midline nodes, 32 straight chords per corner, uniform t=2,
index26. Integration model is dA=t ds, not a solid-wall model. Curves are the
actual polygon facets; stress extrema include both offset faces of every
facet, including all corner chords.

Own geometry hash: 3814f4cd9fcfa474b6e3fcbd21eedb3fdee38818eca0440abb4408fd506143e2.
A=491.6953270111933 mm²; Ix=1181287.6899091285 mm⁴;
Iy=170444.94310055475 mm⁴; CG=(15.116450045292856,61.5) mm.
No catalogue A/I, omega, Cw, J or critical stress is transplanted.

EN convention: N tension positive, Mx=integral(y sigma)dA,
My=-integral(x sigma)dA. Thus EN My is opposite to the app NBR My.
Coefficients are relative to this own gross centroid and multiply signed
moments. They are not interchangeable with app-NBR coefficients.

## Four operators

Mx± and My+ remain integral at this material in the declared panel/stiffener
model. Their compressed physical stiffeners meet Eq5.17's full-area cap.
The mixed-flange interpretation is the existing bounded EN stiffener-column
model, not a new translating-junction eigenmode certificate.

My− has a uniformly bounded compressed web, k=4, and two retained web edge
bands of width rho*b/2. Reintegration moves CG to x=16.28047450196906 mm and
Iy to 161793.11266633004 mm⁴. Both flanges have a pointwise compression
majorant with Table4.2 psi=0/k=1.70; their lips are tensile and supply no
restraint credit. This bound is rechecked at every iteration and finally.

The first gross-section target rho=0.8847265484119713 is **not** the final
answer. Reintegration converges to rho=0.8550207846169662, with residual
-2.6645352591003757e-14 and final web compression bound 158.44185609912648 MPa.
The c0 coefficient is 7.194524151820977e-6 and cx=-6.180732810687219e-6,
cy=0. Dropping c0 violates N=0 equilibrium.

Conservative integer first-yield floors (Nmm), checked over the complete
physical line and two offset faces, are Mx+=Mx−=5670180,
My+=1509094, My−=1483454. Outward interval arithmetic bounds evaluation of
the supplied binary64 contour/operator; it does not constitute an interval
proof of effective-width derivation or physical geometry uncertainty.

## QA and frozen reader

`tests/test_en_ue125_300_authority.py`: 15 tests, 0.75 s, all passed in the
specified Haswell single-thread environment. Coverage includes independent
Gauss-3 raw-moment quadrature and physical stiffener As/Is; independent
K/sigma_cr/lambda/chi/Eq5.17 recalculation; A/CG/I and N/Mx/My equilibrium; c0 transport;
retained partition and mirror symmetry; multiple initial rho and final
residual; sampled map monotonicity/domain; independent closed-form bisection and
analytical contraction bound on the invariant rho bracket [0.8,0.9]; independent Decimal65 face
first-yield bounds; builder material/contour guards; rehashed material/contour/operator/status mutation
rejection; changed source rejection; read without builder or NumPy; N≠0
rejection; byte preservation of legacy normal authorities and inventory.

The runtime reader hashes the complete frozen JSON against a hard-coded pin
and checks source snapshots. It never imports a builder or solver, enrolls a
new hash, or falls back to gross coefficients. The builder is offline only.
The source copies for the fy300 implementation do not mutate globals in the
fy250 modules. Public nominal geometry only; no private project inputs.

Independent numerical review reproduced rho=0.8550207846169322 with
Decimal60 and an independent web-removal/bisection method, CGx=16.28047450196935,
Iy=161793.11266632784 and My− first yield=1483454.69749614 Nmm.
Independent Gauss-2 also reproduced N=0 and unit pure moments for all four
operators. Final independent normative/scope review accepted qualification of only
these four pure-moment N=0 operators. It verified the primary EN11/EN13
clauses and EN15 Tables4.1/4.2 visually. The JSON records
independently_reviewed_normal_components_only; runtime and whole-member
approval remain false. The material-dependent radius guard is explicitly
rechecked at fy300 (limit56mm, actual2mm). No solver, AppTest, or 83-row regeneration was run.

## Exclusions and integration conditions

Axial force, shear and EN6.27, EN6.1.6 torsion/warping interaction, actual
curling/shear-lag applicability, global/member stability, second order,
connections/net section, and actual product/material/core-thickness
verification are outside this authority. Four pure operators alone do not
approve their combined EN6.1.6 use. A separate integration release must bind
all relevant authorities and preserve these guards. No publication here.
