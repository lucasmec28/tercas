# Roof release UI policy comparison, R22

## Finding

The original real-UI test expected the historical roof-top/height component
immediately after a **new calculation** click. That expectation was already
obsolete in the unmodified R21 base; the R22 shear-lag and EN-integrity changes
were not the origin of this failure. This patch changes tests only.

The explicit current calculation boundary was introduced by
`0b05cb15678b7b7fd4db000c51ea1007d408bb15`, with the applied-load policy from
`5c1750bd47602a4b9f95e144f72e0b6254ef037e`:

1. `ue_family_ui.render` calls `current_calculation_inputs.begin_calculation`.
2. `prepare` adopts the versioned CT load model and end-support scope, preserving
   the opening input in history.
3. `roof_top_load.attach` deliberately emits no roof-top sidecar when CT is active.
4. Consequently `roof_top_nbr.preserved` returns `None`: the old height component
   is absent, not corrupt. Current NBR checks use the authenticated frozen
   seven-profile Ue family. This is not the newer 66-section consumer.

The same test also expected optional combined ELS to remain pending, and its
corresponding inconclusive banner. The declared local uniaxial objective already
records combined ELS as `not_applicable`, without approving complete ELS or the
member. No production behavior was changed to restore that obsolete expectation.

## Controls

- Baseline: untouched R21 `332e478cd1b26323974475dfa1fcf14327ccd216`, in the existing
  R21 checkout. The original test failed in **8.99 s**, at
  `ev['records'][0]` because `roof_top_nbr.preserved(result)` returned `None`.
  `app.exception` was empty. Baseline tracked files remain unchanged.
- Integration candidate before this test patch:
  `f548345142c5439042b0fd206887ed1701ea594b`. Its previously recorded failure was
  the same expression and reason, without an app exception.
- The compared test and the three routing files listed above have no diff
  between those two commits.
- Original control artifacts are `r22_shear_ui_baseline.log/.xml`; the integration
  run is `r22_joint_qa_20261108/ui_joint.log/.xml`, outside the repository.

## Coverage retained and added

The formerly single UI case now has two explicit lanes, both with synthetic
5-degree inputs, the same t=2 mm source, and the same imported declarations:

- **Historical top-load producer/replay:** calculate through the unmarked
  producer, place that saved result in the real UI without clicking the current
  calculate button, and prove unchanged rerender/export. The original FLT index
  `0.2637128303218076` and biaxial index `0.2703624348153767` remain pinned to this
  lane. Its EN sectional torsion/cortant sufficiency remains separate from NBR.
  This is a newly produced unmarked snapshot, not an archived cross-version
  fixture; no old result or old panorama is reclassified.
- **Current CT calculation:** click the real calculate control, verify the exact
  prepared input, preserved inactive roof declaration and input history, the
  frozen family identity/criticals/signed capacities, nonzero parallel demand,
  unchanged PP values and factors 1.25/1.0, and CT application for all forces.
  NBR FLT/biaxial indices must be positive and bound to their raw results; EN
  sectional shear remains a separate condition. Torsion must be exact-zero-demand
  applicability with no resistance index, not a blanket exemption.
- **Both lanes:** declared local effective-inertia ELS remains evaluated and
  positive; optional combined ELS is outside this objective, not pending. All
  whole-member/checklist/combined-ELS approval flags stay false. JSON and Word
  exports contain the same result and truthful scope. A further UI rerender must
  retain inputs/results with the structural calculation/attachment entry points
  replaced by failing stubs.

## Validation of this patch

On a separate clone of the integration candidate, one numerical thread:

`python -m pytest -q tests/test_roof_release_composition.py::test_real_app_own_five_degrees_combines_all_scopes_and_replays`

**2 passed in 21.51 s**. Logs/XML: `r22_roof_release_qa_20261108/lanes.log/.xml`,
outside the repository. `git diff --check` passed.

`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1` and
`OPENBLAS_CORETYPE=Haswell` were set, with the existing test dependency paths.
The CPU window was explicitly coordinated before/after the run.

The two unchanged catalog cases in this module, unrelated UI cases and the full
suite were not rerun by this patch. The pre-patch original failure and the two
post-patch lanes are different executions, not three passed tests. No source
PDF, user project, production file or published checkout was modified.
