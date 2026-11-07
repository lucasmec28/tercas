# A source-bound normal-stress observation in the recovered linear field

This separate v2 delta preserves every previous Bernstein upper bound and all capacities, actions, stiffnesses, source fields, applicability guards and tolerances. It does not refine a bound or claim a maximum physical stress.

When the governing normal Bernstein control is a true endpoint in both coordinates (longitudinal control 0/3 and wall control 0/2, or its original before-P state), it may supply only a candidate location. The union branch and its sigma are discarded. The code independently reevaluates the original source polynomial at that point with directed intervals, proves the signs of the actual Mx/My (or exact zero by rational identity), selects the corresponding own effective operators, and includes their c0 and gross B*omega/Cw on the actual wall face. A genuinely ambiguous sign produces no witness.

Only abs(sigma).lo strictly greater than 300 MPa sets observed_exceedance and criterion observed_exceedance_under_linear_model for the normal criterion. Without this proof, an upper bound above one remains inconclusive. Interior controls cannot be witnesses. The other two stress criteria retain their original classification.

The witness saves the case/member/source identities, element/side/longitudinal coordinate, wall/face coordinate, interval face location, selected actual operators, concomitant action intervals, sigma/tau intervals and strict absolute-sigma lower bound. It explicitly denies a physical maximum, first-order physical qualification and whole-member approval. The v2 reader recreates the witness from its authenticated source; changing and resealing any saved witness cannot substitute a proof. The existing full-content cache keys remain in force.

Only the inner check and stress schemas are versioned to v2. Existing v1 snapshots replay their original no-witness path and are never reclassified merely by reading. Injection of a witness or flag into a v1 snapshot is rejected.

UI and Word report the observed normal excess specifically as a point in the linear field. Applicability pending, first-order/high-rotation warnings and global false flags remain visible. Threshold-aware number formatting avoids displaying a small strict excess as 300.00 > 300. The raw interval remains available.

## Synthetic verification and independent review

The final focused selection passed 89 tests in 44.93 seconds, exit 0:

    python -m pytest -q tests/test_en_ue125_300_normal_witness.py tests/test_isolated_en_ue125_300.py tests/test_en_ue125_300_fresh_cache.py tests/test_isolated_en_ue125_300_application.py tests/test_isolated_en_ue125_300_area_source.py tests/test_ui_isolated_en_ue125_300.py

All inputs were synthetic. Coverage includes independent Decimal70 evaluation, opposite moment signs, c0+B, both faces, fictitious/interior/boolean controls, exact threshold and ambiguous sign, source/control/coordinate/sign/interval/flag rehash tampering, cold v2 replay, v1 nonmigration, unchanged upper bounds, applicability pending, Word and AppTest. Counts overlap prior suites and must not be added as unique tests.

A separate compatibility comparison loaded the actual previous implementation at commit 351b178e5fa75904f04c13484227d725c005a467 and supplied it and the new v1 path with the identical synthetic point-source object, solved once. Their 152059 canonical output bytes were identical, SHA256 764b9e125c6559b6e204c58cfa6348a72766500906b981f383ba4b357b59c9bd. See normal_witness_v1_compatibility.json and normal_witness_tests.txt in qa/en_ue125_300_integration.

Independent static review of the final witness, versioning, saved-reader behavior, UI and test receipt found no technical blocker. Acceptance remains restricted to the recovered-field observation, not validity of first-order mechanics, global stability or project approval. No private project inputs were read or copied into tests or records.
