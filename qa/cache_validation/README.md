# EN application validation cache QA

Base: aa25378. Only synthetic inputs were used. No large UI or private project benchmark was run.

Final focused command: `python -m pytest -q -s tests/test_en_family_application_validation_cache.py tests/test_isolated_en_ue_family.py`, with BLAS1/Haswell and the recovered dependency paths.

Result: 38 passed in 27.26 seconds. This is test-suite duration, not an application speed claim.

Counter evidence: the freshly calculated LIVE synthetic result contained only strict native JSON types, without serialization/normalization. Three successive reads (full detached snapshot, lightweight presentation, global context) executed one complete application validation. Current provider/geometry authentication still runs on warm reads. Independently deserialized objects share content tokens. Output mutation does not change the source result.

Tests cover cold/warm validation; input/case/source/proof/count/unrelated-field changes; resealed proof corruption; current authority-file and canonical-geometry changes; validation-source changes; failure non-admission; bounded LRU; tuple/NumPy aliases including an alias inside the checked certificate; and mutation during warm authority authentication. Legacy results without the family component keep the existing no-hash fast path.

The cache holds at most 16 success tokens, no snapshots or caller-supplied trust flags. Tokens use actual canonical bytes of the entire result after an exact built-in-type check. Non-native aliases bypass the cache and use the unchanged full validator. Pending-only and absent components are not cached. A second content hash after warm authority authentication detects mutation during that step.
