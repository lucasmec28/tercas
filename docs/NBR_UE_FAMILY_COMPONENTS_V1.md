# NBR Ue family references v1: recovered implementation

This provider and its205-case focused suite were reconstructed from the implementation transcript after the executor replacement at20:39UTC on6November2026. Original commits97166f1 and080f2b0 were stored only in the lost shared workspace. Formatting/docstrings are not byte-identical. The restored files have NOT been tested yet; the prior205-pass receipt must not be treated as a pass of the reconstruction.

## API

`assess(index,L_mm=...,material=...,lengths=...,load_position=...)` admits only the66 complete nominal Ue registry rows. Material contains explicit E_MPa,G_MPa,fy_MPa,nu,gamma. Lengths contain Lx_mm,Ly_mm,Lz_mm and nonempty origin. Absent lengths use a whole-span fork/free-warping reference, not a statement about actual supports. Positions: shear_center,stabilizing,destabilizing,unknown. Classical reference Me does not cover destabilizing height. Physical span and action mechanics are never modified.

Own-rounded strong branch keys are local,distortional,FLT_reference. Each has eligible/status/reason as applicable; numeric capacities use MRd_Nmm. local includes Wc_mm3 and Ml_Nmm; distortion includes elastic.Mdist_Nmm and Lcrd_mm or a Tabela14 exemption. FLT has Me_reference_Nmm, actual_position_supported and height_effect_included=False. Eligibility means component-reference availability, not actual-action approval. Strong signs are symmetric.

Weak keys positive and negative correspond to My_app web and lips compression. Each has local,FLT_reference,distortional; complete_reference_components and pure_weak_reference_MRd_Nmm exist separately. Negative complete reference remains absent. Positive conventional flange-lip distortion is not applicable only where the lips and connecting bends provably remain in tension. Missing local methods have explicit reasons, not gross-property fallback.

`tabulated_reference(index,material=...)` independently applies NBR local/distortional curves to the adopted published Ml/Mdist and Wx. Its strong.local and strong.distortional each have MRd_Nmm; local_distortional_reference_min_Nmm is only a section reference, without FLT. This avoids requiring Tabela12 for a critical already supplied by elastic analysis. It never transfers those criticals into the rounded geometry. The property source is calculistadeaco.com.br, whereas criticals are Pierin INSTAB with sharp corners and unreported centerline conversion. Correspondence by exact nominal row is an explicit adopted-reference hypothesis, not proof of identical contours. E must equal200000MPa; original app G77000 and formula nu0.3 are compatibility detectors, not values attributed to Pierin. fy changes do not rescale criticals. No Mly sign or weak resistance is inferred.

`attach(result,fresh_calculation=True,lengths=...,load_position='unknown',formula_nu=.3)` adds FIELD=nbr_ue_family_reference_components with own_rounded_contour and published_nominal_reference. Without explicit fresh_calculation it returns the existing result unchanged. It checks current nominal dimensions, preserves legacy denominators and height results and requires both reference bases to remain separate. `validate_saved` repeats assess and compares the complete output; a recomputed selfhash alone is not authority.

## Methods and evidence

Local strong: NBR14762:2010§9.8.2.1(b),Tabela12; the existing normative ratio domain is checked per row. Tabela14 only optionally exempts strong distortion. FLT strong uses declared Ly,Lz,Cb=1 and MSE at chi*fy, only as a reference where actual position is unsupported.

Distortion: AISI S100-2024 Appendix2 general elastic simple90-degree lip method, then NBR§9.8.2.3 strength curve. Sharp-midline flange substructure and own-rounded global section modulus are intentionally distinguished. No spring, roof restraint or moment-gradient credit. Lphysical below unrestricted Lcrd is unsupported, not a new normative ban. No exact-eigenvalue or guaranteed-lower-bound claim.

Primary correlation source checked before replacement: Glauz2018 Tables2/4, printedpp48–49/51. The60-channel sample has t1mm; h50/100/150/200mm; b25/50/75/100mm; lips6.25/12.5/25/37.5/50mm in the tabulated combinations; angles45/90degrees. Strong set4 prediction/FSM mean0.966, standard deviation0.096. h/t,b/t,d/t and a bounding-envelope indicator are descriptive, not proof all points in the box were sampled or a normative gate. The Ue125-specific FSM comparison is never assigned to other contours. Source documents retain the existing URLs/hashes.

Weak MLE: CBCA Steel Framing Engenharia2016 pp61–65,73,113, interpreting NBR§§9.2.2,9.2.3,9.8.2.1(a). Generalized restricted uniform-web method rechecks flange/lip uniform-fy majorants, stiffener inertia, tension-first-yield interval, contraction, section-modulus monotonicity and64-step bracketed root. Stocky flange lambda_p0<=.673 requires no stiffener; the D/b<=.8 condition applies to the stiffener-required branch. Unsupported flanges/lips needing reduction remain explicit gaps. Weak AnnexE j uses exact cubic moments of each own contour via two-point Gauss; Lx,Lz are independent. No constant from the pinned Ue125 contour is inherited.

## Prior verified coverage, awaiting reconstruction rerun

Original suite:205 passed in5.80s. At L6000mm: own local/FLT62 of66; own distortion approximation/exemption66 of66; weak local both signs and positive complete reference49 of66 atfy250,43 of66 atfy300. No complete negative weak resistance. Separate adopted tabulated route local66/D66 for both materials. The lost detailed JSON must be regenerated after a coordinated test window; do not recreate individual-row results from assumed counts.

No complete physical member, biaxial interaction, primary torsion, ELS or product approval is implied. New destabilizing-height consumer remains pending until Me authority is authenticated; selfhash is insufficient. No legacy modules or immutable certificates are replaced.
