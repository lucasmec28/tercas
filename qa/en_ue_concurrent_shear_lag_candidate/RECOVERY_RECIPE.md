# Recovered recipe for the four synthetic P fixtures

Status: recipe restored and subsequently executed anew. No recovery of the
lost result bytes is claimed. The fresh generation and five dependent tests
are recorded separately in REGENERATION_RECEIPT.md.

Every case uses catalog index53, L=4100 mm, fy=300 MPa, fu=450 MPa,
`en_ue_test_helpers.inputs` and `run`. The input helper retains its direct-load,
self-weight, top-web load-line and full-span-length declarations. Then the recipe
sets q/P/position, calls `own.activate`, and activates the existing EN declaration
with model origin `Synthetic concurrent candidate point-load application QA`.

Final load recipe, with q in N/mm, P in N, positions in mm and angles in degrees:

- P_interior: q=0.03, P=12, x=1742.5, angle=5.71.
- P_reversed: q=-0.22, P=-12, x=1742.5, angle=-5.71.
- P_near_left: q=0.03, P=12, x=82, angle=5.71.
- P_opposes_uniform: q=0.03, P=-300, x=2050, angle=5.71.

For all four, q_sls=q_uls/1.5, P_sls=P_uls/1.5 and x_sls=x_uls.
The final recipe used 12 N and -300 N, not earlier tiny exploratory values.

The generator creates a complete current-application snapshot and recovers
both adjoining element sides at P. It then disables the member solver while
calculating and replaying the separate candidate. Its JSON payload keys match
the existing five dependent tests: kind, application_snapshot, candidate_check,
receipt. The current R12 dispatcher may already produce v4 in the application
snapshot; no historical v3 source is manufactured or substituted.

Run only in an available calculation window, from the recovered repository:

```sh
export PYTHONPATH=.:tests:/workspace/scratch/200bd23c4a9b/tercas_test_dependencies_r12:/workspace/scratch/200bd23c4a9b/connections_audit/test_dependencies
export OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python qa/en_ue_concurrent_shear_lag_candidate/run_point_application.py \
  > qa/en_ue_concurrent_shear_lag_candidate/point_application.log 2>&1
```

The generator sets single-thread BLAS before numerical imports. It runs serially
and writes only within this QA directory. Existing generated files require
`--overwrite`; that option means a new execution, not restoration of old bytes.
The new summary is marked incomplete until all four runs and replays finish.
It records actual outcomes, execution times, source identity and new file hashes.
It does not force historical eligibility labels or create missing result files
without executing their calculations.

During recipe restoration only, no solver, test runner or application import
was executed; syntax was checked by AST parsing. A later calculation window
performed the fresh generation and five tests described in the new receipt.
