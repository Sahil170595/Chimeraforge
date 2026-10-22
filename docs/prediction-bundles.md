# Private prediction evidence bundles

Available since **Chimeraforge 0.70.0**.
A bundle preserves original plan inputs, policy and benchmark receipts for
offline receiving and scoring. It does not rerun inference, replan, replace
coefficients, remove unfavorable rows or refit predictions.

**Review every original file before sharing.** Benchmark and harness bytes may
contain prompts, options, provider diagnostics, paths or other private data that
the scorecard omits. The directory is a private handoff, not a sanitized public
report. Metadata and scorecards expose digest receipts and bounded outcomes;
they do not include the raw private originals. No upload occurs.

## CLI and Python

Use the explicit [prediction score policy](prediction-scorecards.md). Every
`--benchmark` is one original file in declared order, including repeated paths.
Omit the flag for a zero-received population; the policy still declares the
expected evidence.

```bash
chimeraforge bundle prediction-create plan.json --policy score-policy.json --benchmark first.json --benchmark second.json --out private-evidence --json
# Move the entire directory; keep score outputs outside the closed inventory.
chimeraforge bundle prediction-verify private-evidence --json
chimeraforge bundle prediction-score private-evidence --out scorecard.json --json
```

```python
from chimeraforge import api

bundle = api.create_prediction_bundle(
    "plan.json",
    ["first.json", "second.json"],
    policy="score-policy.json",
    outdir="private-evidence",
)
metadata = bundle.to_dict()
held = api.verify_prediction_bundle("private-evidence")
scorecard = api.score_prediction_bundle(held)
scorecard.save("scorecard.json")
```

The create API accepts an original saved plan file, a verified plan-bundle
directory or held `PlanBundle`. Receipt inputs are paths so their original bytes
remain available. Policy accepts `PredictionScorePolicy`, a JSON object or a
path. Typed/object policies receive newly captured JSON bytes; file policies
retain their original bytes. Create/verify return defensive `PredictionBundle`;
score accepts that held object or a directory and returns `PredictionScorecard`.

Held metadata and scoring use verified bytes without filesystem reads, including
after relocation or source removal. Saving a score still checks protected paths
and aliases before writing. Original pretty JSON and whitespace retain their
own raw hashes and sizes in `inputs.receipts`; parsing does not replace those
bytes with a reserialized equivalent.

## Fixed inventory and receiving

```text
manifest.json
policy.json
plan/
  manifest.json
  plan.json
  corpus.json
  quality.json           # only when the saved plan requires it
receipts/
  0000.json
  0001.json              # contiguous original order, at most 0255.json
```

`plan/` and `receipts/` exist even with no received receipts. Incoming plan-bundle
manifest and member bytes remain unchanged. A bare saved plan captures its
original bound corpus and optional quality inputs using the existing plan-bundle
semantics. Unsupported legacy or unavailable bindings are refused before writes.

The closed outer manifest contains `schema_version: 1`,
`kind: "chimeraforge.prediction-bundle"`, `plan_fingerprint`, `policy_sha256`, and
ordered `files` rows containing only fixed logical `path`, `sha256`, `size_bytes`.
The receiver validates both inventories, sizes, hashes and producing plan-input
bindings. There are no extra files, recursive discovery, links, hardlinks,
reparse points or special-device members. Unsafe paths and missing or reordered
receipt indices are invalid. A self-consistent edited manifest cannot bypass
native receipt or policy validation.

All original receipts stay ordered, including valid negative, extra, ineligible
and duplicate evidence. A known mismatch is retained; malformed native arithmetic
is refused. Zero receipts is valid incomplete evidence, with missing rows derived
from the policy. The existing scorer recomputes sample populations, serving
bindings and conditional server-decode comparison. Bundling grants no additional
GPU eligibility, source trust, physical authentication, independence or
calibration qualification.

The full transport is at most 32 MiB: outer manifest, inner manifest, original
plan/corpus/optional quality, policy and every receipt occurrence. Existing
per-member limits and at most 256 receipts also apply. A repeated cached source
is held once but every occurrence is charged before cloning it. Transport bytes
are distinct from the existing scorer's input accounting, which excludes the
outer manifest. Public metadata exposes only logical inventory/digests,
fingerprints, counts, byte totals and explicit private-handoff limits, without
producer/local relocation paths.

## Publication and outcomes

All content is held and validated before writing. The creator exclusively claims
a new destination; its parent must exist. Existing destinations, including empty
directories, are refused without replacement. Members are created exclusively,
with the outer manifest written last as the readiness marker. Partial directories
are visible during publication: no atomic-directory or crash-durability guarantee
is made. Verification still checks every member after the marker appears.

Owner-only directory/file mode bits are used where supported; Windows follows
inherited ACLs. These mode bits do not establish universal access control. On
failure, cleanup removes only unchanged owned entries under the original root
identity. Unknown members, replacements or uncertain writes leave an incomplete
destination for inspection. Portable identity checks do not eliminate hostile
concurrent rename races. Every received bundle protects its receiving root and
members, including output aliases. The held object returned by creation also
remembers and protects the original paths it consumed. Directory verification or
directory-based scoring cannot reconstruct unavailable producer paths; that
private protection list is not part of the transport. No existing unrelated
directory is recursively removed.

| Operation | Exit |
| --- | --- |
| Create/verify | 0 valid content; 2 malformed/unavailable/unsafe input or publication |
| Score | 0 complete within band; 1 comparable breach; 2 invalid; 3 incomplete |

Valid content can contain breached or incomplete measurements. As in ordinary
prediction scoring, a known comparable breach retains exit 1 even if other rows
are incomplete. A successfully verified bundle is not a passed prediction,
deployment approval, calibrated model or scientific GO.
