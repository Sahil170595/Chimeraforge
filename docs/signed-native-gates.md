# Signed native regression gates

Chimeraforge 0.71.0 adds an offline receiver gate for signed v2
contributions. Install `chimeraforge[sign]` for Ed25519 support.

```bash
chimeraforge contribute gate --baseline baseline.signed.json --candidate candidate.signed.json --trusted-key receiver-trusted.pub --policy policy.json --out decision.json --json
```

Repeat `--baseline`, `--candidate` and `--trusted-key` to preserve the declared
ordered population. Omitting trusted keys yields untrusted evidence, never a
trust pass. Receiver trust is explicit; an envelope's embedded public key does
not establish it. The existing unsigned export/import workflow is unchanged.

```python
from chimeraforge import api

decision = api.gate_signed_contributions(
    ["baseline.signed.json"], ["candidate.signed.json"],
    trusted_keys=("receiver-trusted.pub",), policy="policy.json",
)
decision.save("decision.json")
```

The synchronous API accepts `SignedContribution`, JSON objects or file paths in
each list. Keys accept raw public-key bytes or public PEM/raw32 file paths. The
required policy accepts `RegressionPolicy`, JSON or a file; the actual resolved
policy is reported. The result is a defensive `SignedContributionReceipt` with
`to_dict()`, `exit_code`, `check_output()` and `save()`. Input/key/policy aliases
and planner quarantine are protected output destinations.

Exact domain-separated payload signatures and artifact identities are checked
before comparison. Only valid, explicitly trusted public payloads can contribute
comparisons. Every declared verification result remains visible. Malformed
authenticated native arithmetic is refused, including a supported TTFT/prefill
alias contradiction or generated token count beyond an explicit output cap.

Matching uses public prompt/options commitments, prompt character count, native
profile, concurrency/rate, context, output cap/option, complete populations and
positive actual token lengths. The full options hash is intentionally stricter
than native gates which can remove the output-cap option from private options.
Native metric bases, supported observed controls and cache evidence must meet the
resolved policy. Semantic copies remain inconclusive across both arms even when
re-signed, reformatted, numerically respelled or reordered. This detects copies
of observable evidence; it does not establish independent executions.

The metrics are native completed-token wall rate, decode rate, TTFT and request
duration. Public v2 payloads omit private options/prompts, saved plan/candidate
bindings, original scheduling seeds and per-request queue clocks. The gate does
not reconstruct them or claim prediction accuracy, queue SLOs or serving capacity.
Source fingerprints remain signed commitments rather than validated plan bindings.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Complete, comparable, explicitly trusted conditional pass |
| 1 | Known signature/artifact failure, or comparable metric regression |
| 2 | Malformed input/key/policy/native arithmetic, or unsafe/failed output |
| 3 | Crypto unavailable, untrusted, incomplete, copied or incomparable evidence |

Malformed input takes precedence. Known authentication failure takes precedence
over unavailable evidence; after authentication, inconclusive comparability takes
precedence over metric regression while known valid comparisons remain visible.
Signature validity and trust do not authenticate measurement truth, hardware,
served weights, cache independence, calibration or deployment readiness.
Key files are held and bounded before crypto use, so known read/size failures
remain malformed. PEM/key semantics use the crypto SDK; when it is unavailable,
those semantics remain unvalidated rather than receiving an invented verdict.

Bounds are 1–16 envelopes per arm, 16 MiB per envelope, 8 MiB decoded payload and
32 MiB across declared envelope occurrences, including repeated cached sources.
Policy has a separate 64 KiB budget; at most 16 public keys of 16 KiB each are
accepted, with at most 1,000 samples per payload. The envelope budget is not a
combined transport budget for policy and keys. Original bytes are held once;
declared occurrences are charged separately. Public decisions contain bounded
facts and commitments without raw private provider content.
