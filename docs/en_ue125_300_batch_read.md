# EN300 batch authentication and lightweight presentation

This delta changes readers, not section calculations, tolerances, load combinations, witness proofs or saved-result schemas. Both v1 and v2 checks retain their original replay path. The public `preserved(result)` still returns a complete detached snapshot.

`validate_saved_many` is a closed batch operation. Every call authenticates the supplied frozen normal snapshot, its derivation source files, the current frozen normal JSON, the current section JSON and the current shear source/inventory JSON files. It groups shear certificates only by their actual canonical content after checking native JSON types. It retains every complete per-row proof token and independent replay on a miss. There is no caller-provided trusted/skip flag, object-ID/stat cache, new result cache or cache epoch. Existing independently verified row proofs remain the only reusable proofs.

The application binds every row to the original input, combination, load arithmetic, source hash, support hypotheses, small-rotation warning and summary before batch verification. Counts and inventory remain mandatory. Only then may its internal presentation reader copy a lightweight view without dense source arrays or per-piece replay controls. UI, panorama and Word receive a newly allocated, detached view. This view is not an archival snapshot and cannot pass the complete saved reader. JSON export continues to use the original complete result.

## Synthetic measurement

One authentic synthetic area run selected `ELU normal`, producing 40 ELU cases, with each of four area loads set to 1 kgf/m². No real project inputs were read or copied.

- Full result calculation: 46.842 s.
- Sequential full reader using the same guard policy: 1.896 s.
- Batch full reader: 1.469 s.
- Batch presentation reader: 0.765 s.
- Complete component: 11,487,895 JSON bytes; presentation: 589,913 bytes.
- Word generation: 5.727 s.
- Complete saved snapshot and original result remained byte-identical through all reads.

The sequential comparison is forty singleton validations using the same authority guard policy, not a rerun of an older release. The additional frozen-normal-JSON file guard was added after this one 40-case measurement; its final implementation was measured separately over 50 calls (mean 0.00279 s, maximum 0.01860 s). The final focal checks include that guard. No second 40-case solve was run. These measurements do not certify the private project's complete UI under 60 seconds; that remains a separate acceptance check. No timeout was increased.
