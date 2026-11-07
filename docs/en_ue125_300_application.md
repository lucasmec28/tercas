# Explicit application and saved-reader contract: own Ue125 / fy300

This route is separate from both the seven own Ue100 profiles and the 83-profile fy250 catalogue component. Their declarations explicitly require fy250 and are not promoted to fy300. Opening an old study never activates or recalculates the new route.

## Activation

`tercas.isolated_en_ue125_300_application.activate(data, model_origin=...)` returns a deep copy of **inputs**, adding only `isolated_en_ue125_300_model`. The UI uses this same helper after the user checks the new option, declares the nominal intact section and supplies its origin. It changes no loads, section properties, self-weight, material or stiffness. It does not accept or requalify a results object.

The explicit contract is own `ue_catalog_reference` index 26, Ue125x50x17x2 with ri=2, nominal fy=300/fu=400 MPa, analysis E=200000/G=77000 MPa, isolated purlin, original roof loading and free-warping fork hypotheses. Resistance remains independently EN E=210000 MPa, nu=0.3, fyb=fya=300 MPa, gammaM0=1. The original frozen normal and shear authorities are authenticated independently.

A profile/material/application identity change withdraws the declaration and origin. Input and choice changes invalidate the saved result. An existing fy250 option is retained as historical information, not converted.

## Calculation and persistence

The hook runs on the original dense Vlasov ELU fields, before their existing compaction. It saves the original normal authority, original catalogue source, dense-demand hashes and the kernel's full saved source. ELS combinations are counted and excluded; an ELS-only inventory cannot qualify a section.

The saved reader authenticates the input fingerprint, choices, inventory, source bindings and hashes. It replays original load arithmetic and the original roof lines, no extra free couples, both fork supports, and the unchanged 0.05 rad non-normative rotation warning. It calls the independent kernel's source replay and section checks. It does not invoke an analysis solver or rebuild normal/geometric sections. The application's **input preview widgets** may still prepare their existing catalogue geometry; that is separate from result reading.

## Presentation and scope

The new UI and Word section show resistance versus analysis material, the three independent EN 6.1.6 limits, EN 6.1.5 shear and EN 6.1.10 / Eq. 6.27 M–V, signed bending/shear denominators, governing cases and numerical controls. Conservative bounds above one are inconclusive, never physical failure witnesses. Applicability guards remain distinct from genuine observed failure.

The panorama may recognize a sufficient **listed sectional condition** only for a complete, source-bound ELU inventory satisfying stress, shear and M–V together. No EN index is imported into NBR/AISI formulas. Whole-member, first-order physical suitability, complete EN design, combined ELS and global approval remain false. Existing high-rotation and small-rotation warnings stay ahead of indices through the original application and Word warning flow.

All tests for this change use synthetic inputs. No real project results or inputs were copied into this repository.
