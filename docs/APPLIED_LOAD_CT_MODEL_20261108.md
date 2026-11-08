# Versioned applied-load model

The current input preparation records `load_application_policy = all_actions_at_shear_center_v1_20261108`. The marker is not an option or a checkbox. Existing saved inputs without the marker retain their original mechanics and replay; preparing a new calculation creates a copy.

All supported applied transverse forces, including profile self-weight and the nodal half-shares of bar self-weight, are applied at the shear centre. Forces, combination coefficients, direct self-weight factors 1.25/1.0, P stations, physical span, node geometry, support conditions, effective lengths and material/section properties are preserved. Stored top/manual load-line data remain stored but inactive under the new marker.

The isolated Vlasov adapter changes application coordinates, not torque results. It retains torque about the centroid, calculates torque about the shear centre from the actual force coordinates and leaves the solver intact. In synthetic isolated tests the shear-centre torque, bimoment and twist become exactly zero; the centroid torque generally does not.

The network changes the external-force vector only. Bar weight uses an independent load map at the shear centre; the physical connection map, rigid arms, sectorial coordinates, bar length and direction, axial coupling and stiffness are unchanged. Thus forces transmitted internally by eccentric connections can still generate real torsion. The 6DOF and 7DOF backends both carry the model marker in their saved inputs; readers bind it to the application input.

NBR family results use new schemas v7 (roof) and v2 (isolated girt). Existing NBR equations supply Me with Cb=1 on the strong axis and independent resistance lengths. Current actions are at the shear centre on both axes, so the former height/Ritz/energy-floor alternatives are not executed or selected. Local/distortional, shear-lag and other method limits are unchanged. All historical schemas replay unchanged.

The seven frozen Ue reference contours accept the versioned load model without changing their frozen criticals/materials. Their existing scalar Me expressions remain applicable. Homogeneous U scalar references and catalogue scalar paths use their existing CT model without fabricating a Vlasov contour.

## Verification at checkpoint ceb5a8c

- `tests/test_load_application_policy.py`: 145 passed in 39.14 s. Includes all 66 complete family rows for roof and isolated girt (132 cases), seven frozen Ue sources, exterior/profile-PP/P force identity, eccentric P, independent resistance lengths, historical replay and network load arithmetic.
- Complete synthetic isolated roof/girt calculations: EXTERNAL, PP and P torque about the shear centre equals zero in both ELU and ELS. The torsional result fields are zero without overwrites.
- Complete synthetic 7DOF network: 19 combinations, saved-demand validation passes, external distributed torque and nodal bar-weight torque about SC vanish, total nodal weight balances and internal connection torque remains nonzero.
- Complete synthetic legacy 6DOF network: two combinations; global force residual around 1e-12 N, moment residual around 1.7e-9 Nmm.
- Mechanical smoke test source is added separately in `test_load_application_policy_mechanics.py`; the parent owns the final integrated run and UI tests.

No publication or main-branch change was made. Tests are synthetic regression/consistency evidence, not structural certification.
