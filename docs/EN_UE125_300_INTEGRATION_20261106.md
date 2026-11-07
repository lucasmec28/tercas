# Isolated EN components for own Ue 125x 50x 17x 2 / ri 2 / nominal fy 300

This new opt-in schema is limited to catalogue index 26, the exact 134-node rounded nominal contour, and app material fy 300/fu 400 with analysis E 200000/G 77000. Resistance uses independent EN E 210000, nu 0.3, fyb=fya 300, gammaM 0=1. Nothing converts stiffness, actions, legacy certificates, or the original Vlasov method. No sheet-restraint credit, N=0, no member/global/ELS/first-order physical approval.

## Sources and equations

The original normal snapshot is authenticated by the pinned normal authority BEFORE the independently qualified shear snapshot is bound to it. Four signed normal floors are 5670180/5670180Nmm (Mx),1509094/1483454Nmm (EN My). Shear floors are 42804/33408N. These are the reviewed source integers, not scaled 250 or nominal floats. Source documentation is in the two provider reports accompanying this integration.

EN My has the same convention as the Vlasov physical My: minus the app NBR My. No second sign conversion occurs. Effective operators retain their c 0 and cross coefficients. B uses gross omega/Cw; transverse and warping shear use the original primitives; Tsv uses opposite exterior faces. All terms share longitudinal and wall coordinates. The original signed-operator union/tensor-Bernstein sufficient bounds are reused unchanged. Above-one upper bounds remain inconclusive and are not physical failure witnesses. Exact zero is recognized only from exact rational equilibrium fields and exact zero torsional coefficients, never from a tolerance.

EN 6.1.10 Eq 6.27 uses the existing rational Bernstein/gauge arithmetic, only the four independent 300 normal floors and the two 300 shear floors. N=0 and Mf=0 are explicit. There is no T→V conversion or T=0 prerequisite. Applicability uses physical zones between actual moment zeros, not mesh lengths or arbitrary point splits. Strong Le>2450mm and weak Le>3075mm are strict where the axis is active. Curling is bounded at absolute panel stress 300MPa and the minimum panel distance over all four effective centroids, avoiding the invalid gross-centroid scaling of the old 250 proof. Pure-component curling is not presented as an extra combined N/M/B rule.

## Source and read integrity

A new fixed section snapshot pins the ENTIRE original section, including gross CG/properties, omega and static primitives. Runtime validation never builds another section. The complete original dense demand is retained for the narrow new schema, and the ordinary compact demand summary is reproduced exactly from it. This increases saved-file size intentionally to preserve the source.

The saved-reader arithmetic audit reconstructs K*u−f from saved nodal displacements and original loads, without solving any system. It verifies element end actions, all recovered polynomials, source load torques, fixed degrees of freedom, energy/work, reactions, original numerical diagnostics at their unchanged 1e−6 qualification tolerance, original critical states, support-limit prefix, and rotation witness/warning. This is not an error estimator, new solver, or physical validation. The saved EN bounds are replayed from that checked source and independent provider snapshots.

A bounded 128-entry read cache admits only a full successful replay. Its key is the canonical content of the entire check (including dense source), summary and original normal snapshot plus source hash and model origin. Only finite native JSON values are accepted. Both authorities are checked before any cache hit. Changing/resealing content cannot obtain a hit from an earlier result. Errors are never cached.

## QA status

All inputs and fields used in this work are synthetic. The first focused kernel suite passed 24 tests; after independent review hardening the kernel suite passed 30 tests in 6.35s. Tests cover direct independent concurrent stress sampling at both faces/interior coordinates; signed reversal and high bounds; pure torsion without V; exact zero; actual moment-zero zones; material/geometry/N/ELS/gap rejection; rehashed section/normal/shear/source corruption; read-only replay with solver/builders blocked; native-type cache guards and authority rejection on a warm cache. See qa/en_ue 125_300_integration/core.txt. UI/pipeline and independent review are tracked separately; this checkpoint is not a release claim.

## Final focused kernel receipt

The final kernel suite passed 37 tests in 9.26 seconds (exit 0), superseding the earlier 30-test checkpoint. It additionally covers the original finite-point L/100 numerical guard and six independently prescribed stress-operator basis fields (B, Tsv, Tw, Vx, Vy and a signed mixed field) at interior wall/longitudinal coordinates and both faces. These algebraic basis tests do not claim to be physical solved members. Cache operations use a lock for concurrent Streamlit sessions, and the entire pinned section authority is authenticated even before a warm-cache hit.

The final pipeline/UI/legacy-focused selection is a separate set: 188 passed, 3 deselected in 114.74 seconds. Its command, the deliberately interrupted earlier broad selection, exclusions and performance measurements are recorded in hooks_receipt.json and application_performance.json alongside the logs. Do not add the earlier 11/30-test checkpoints to final totals.

One synthetic direct case plus ELS produced a 473040-byte result, with 194697 bytes of retained dense source per ELU. Full calculation was 3.296 seconds; cold preserved-read validation was 0.805 seconds and warm validation 0.0464 seconds. This is not a measured full 40-case batch performance claim.
