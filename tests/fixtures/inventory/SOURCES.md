# Legacy native plan fixture

Captured at 2026-11-01T13:48:17.925118+00:00 by the unchanged published 0.86.0 native
`api.plan` -> `PlanArtifact.save` -> `api.load_plan` positive control in
`tests/test_inventory_selected_batch.py` before product edits. Producer source:
`d029641ec310490f70c18e9dcac6b323581bca48`. The complete original candidate population
is retained. SHA256: `33dd39c068be999b66566f336677c489a6af183fc99c3c2d3b0e24035ed57212` (73582 bytes).
The per-file `.gitattributes -text` rule preserves these exact captured native
bytes, including 1939 Windows CRLF sequences, on every checkout. The earlier
working snapshot's normalized Git representation was not this raw byte image.

This is declared manual `params_b=1.5` and archived Qwen geometry (28 layers,
2 KV heads, head dimension 128), not resolved model weights, a resolved Hub commit,
or measured memory. The geometry archive and dated source are
`../hybrid_configs/Qwen_Qwen2.5-1.5B-Instruct.json` and its `MANIFEST.json` (2026-09-05,
upstream URL used `main`). No model, inventory query, GPU or remote call produced it.

Used to prove default B1 compatibility and refusal to invent a selected-batch
calculator declaration for old saved plans. It remains a historical 0.86 fixture;
new producer declarations and fingerprints legitimately differ.
