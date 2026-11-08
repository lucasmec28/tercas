# Synthetic QA: G8.1 contribution and H4 lower bound

Presentation-only change on the R15 saved-reader route. No calculation, snapshot
schema, loads, section, stiffness, capacity, result or verification status changes.
The new explanation applies only to explicitly saved N=0, first-order ELU records
with a recognized first-yield G8.1 capacity and a consistent B/Ba ratio above one.
It explains H4 >= |B|/Ba for nonnegative interaction terms, while retaining missing
flexural capacities, physical applicability limits and the distinction from an
independently qualified inelastic option. It never marks H4 as computed.

Historical records lacking those explicit domain/capacity fields retain their
existing presentation. Readout first uses the existing snapshot validator. Newly
consumed first-yield algebra and B/Ba data are checked before publishing the extra
conclusion. Inconsistent data fails closed without rewriting the saved result.

Focused verification: 44 tests passed in 4.91 s in
`tests/test_torsion_applicability.py`. This includes existing-reader preservation,
new explanation in screen and Word paths, absent/nonzero/boolean N, absent order
or option, at/below-threshold ratios, and stale or self-contradictory saved evidence.
Solvers and global-verification rebuilding are blocked by the autouse test fixture.
Serial execution, BLAS one thread, no pytest cache, no bytecode writes.
`results.log` and `results.xml` contain the synthetic run. `git diff --check` passed.
This focal check is not the complete application suite. No project case data is
included in this directory or in the change.
