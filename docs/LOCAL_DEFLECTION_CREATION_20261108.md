# Local deflection objective for new studies

User direction: check the purlin's local vertical (normal to roof, strong axis),
and the wall girt's horizontal (profile vertical, normal to cladding). Neither
an inclined purlin's global vertical nor a resultant is selected.

## Change boundary

- Explicit UI creation actions and an empty session now adopt the existing
  `local_uniaxial_component_v1` contract through `for_new_study` for supported Ue
  studies. The separate creation-compatibility integration preserves plain U
  homogeneous references on their existing scalar route without this new token: the
  current development scope is stiffened Ue, not a new validation of plain U.
- Source factories, imported inputs, partial/existing sessions and historical
  results are not migrated. An explicit scope edit invalidates the current UI
  calculation before the next calculation.
- Fresh local-component panoramas classify an unrequested combined ELS model
  as outside the requested objective. An explicit optional combined-service
  request retains its independent coverage checks.
- Completion inventory and Word explain this optional scope. Saved historical
  inventories retain their original messages and data; readers do not solve.
- No norm limits, torsion, ELU, FLT, load-vector components or solvers changed.
  Existing direct self-weight and effective resistance-length policies remain.

## Mechanical and normative boundaries

The supplied NBR14762:2010 printed pp.51–52, section 9.8.5, were inspected from
its rendered primary-source pages. The scalar MSE implementation remains
unchanged: effective inertia from service bending, using the full physical
span. The existing gross M/W <= fy check remains a method-consistency guard,
not a new normative rule and not proof of effective-section elastic stress.
The declared project/Table A.1 limits and their action rules are unchanged.
This component does not certify the whole member or all physical service effects.

Three-girt horizontal service remains the existing full-network result at the
gross centroid, referenced to its end chord. It is not replaced with the isolated
scalar solver or a newly chosen torsional point. Its normal-stress/MLE consistency
check still depends on concomitant N, strong/weak moments and bimoment. Central
member verification continues to retain upper/lower members as model context.

## Verification

- 117 focused creation/import/UI/local mechanics/self-weight/elastic-guard tests passed.
- 153 additional inventory/Word/UI/horizontal-network preservation tests passed.
- After review hardening, 153 scalar/scope/inventory tests passed, including malformed
  configuration and incomplete-evidence checks. No network solver was changed.
- Rendering/import/Word tests preserve input/result JSON and saved history.

## Integration note

On the supplied base, calculating an own-Ue1.20 reference after the pre-existing
`for_new_study` FLT activation fails the protected-field check for
`flt_combined_height_method`. This predates the local-deflection change and is
corrected in this release by the creation-contract change described in
`OWN_CREATION_FLT_CONTRACT_20261108.md`. The numerical FLT method and its
protected source contracts remain unchanged.
