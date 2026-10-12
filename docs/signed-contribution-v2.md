# Signed contributions and private replay

This is an unpublished **0.65.0 candidate** feature. The published CLI is 0.61.0.
Install `pip install ".[sign]"` from the candidate checkout, or install its wheel
with the `sign` extra. The core package and unsigned v1 workflows remain usable
without cryptography. The `all` extra includes signing.

## Create and verify a signed artifact

Signing consumes a current saved `PlanBenchmark` receipt produced by the public
`benchmark_plan` API or `bench --plan`. A raw benchmark or unsigned v1 contribution
does not contain the required bindings and cannot be upgraded by signing it.

Create Ed25519 raw32 key files with the installed SDK. These examples create new
files exclusively; keep `producer.key` private and give receivers `producer.pub`
through a channel they trust independently of the artifact.

```python
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key = Ed25519PrivateKey.generate()
with Path("producer.key").open("xb") as stream:
    stream.write(key.private_bytes_raw())
with Path("producer.pub").open("xb") as stream:
    stream.write(key.public_key().public_bytes_raw())
```

Unencrypted Ed25519 PKCS8 private PEM and public PEM are also accepted. Other key
types, malformed lengths and encrypted private PEM are refused.

```bash
chimeraforge contribute sign plan-benchmark.json --private-key producer.key --out signed.json --json
chimeraforge contribute verify signed.json --format v2 --trusted-key producer.pub --out verified.json --json
```

Verification checks the exact signature before parsing the public payload. A valid
embedded key remains untrusted without a receiver-supplied matching key. Repeat
`--trusted-key` to supply up to 16 keys. Signer authentication means possession of
that trusted private key; it does not authenticate a person's name or measurements.

The closed public payload retains native sample populations, recalculated
aggregates, requested/successful/failed counts, timing bases, declared workload,
observed controls, source-byte hash and source fingerprint. Private prompt and
recorded options are represented by hashes; prompt character count and explicit
output cap remain visible. It excludes prompts, completions, raw options,
endpoints, arbitrary metadata, warnings and provider messages. A source hash
commits bytes; it does not prove those bytes describe a truthful execution.

## Replay with private inputs

The receiver needs the exact private prompt and recorded adapter map. Save a JSON
file with exactly `prompt` and `options`. Its prompt must reproduce the original
prompt hash/character count, and its options must reproduce the recorded-map hash.
Use the original receipt's `execution.request.options`, not guessed wire defaults.
Private files must not be shared with the public signed artifact.

```bash
chimeraforge contribute replay signed.json --format v2 --trusted-key producer.pub --private-workload private-workload.json --base-url http://localhost:11434 --out replay.json --json
```

Trust and private-input mismatches are resolved before endpoint contact. V2 uses
the recorded model, backend, request count, workload, concurrency, configured
arrival rate, context and cap. Only the receiving endpoint may be overridden;
v1 prompt/count/model/backend/workload override flags are refused for v2.

Replay uses the current supported runner and records fresh native observations.
Supported Ollama default-tag and context-option injection are normalized only in
comparison views; signed bytes and raw original controls remain intact. The exact
recorded map does not establish original applied wire values, ignored options or
defaults. A configured Poisson rate does not reproduce an original schedule/seed.

Every declared native population is retained. Partial executions and unknown
timing/cache facts make comparison unavailable; known controls, cache contradictions
and workload differences remain mismatches. Missing or inconsistent postcontact
counters retain known components with unavailable derived totals. Actual native
failures remain categorical with known counts, without fabricated sample receipts.
Metrics are descriptive current-profile comparisons, not hardware, served-weight,
independence, calibration or reproduction qualification.

## Python API

```python
from chimeraforge.api import (
    sign_contribution, verify_signed_contribution, replay_signed_contribution,
)

signed = sign_contribution("plan-benchmark.json", "producer.key")
signed.save("signed.json")
checked = verify_signed_contribution(signed, trusted_keys=("producer.pub",))
# Inside an async function:
# replayed = await replay_signed_contribution(
#     signed, "private-workload.json", trusted_keys=("producer.pub",),
#     base_url="http://localhost:11434",
# )
```

`sign_contribution(receipt, private_key)` accepts a current `PlanBenchmark`, dict
or JSON path, and a raw32 byte seed or key path. Verification and async replay
accept a `SignedContribution`, dict or JSON path. The private workload accepts a
dict or JSON path. Trusted keys accept explicit raw32 public bytes or file paths.
Defensive results expose `to_dict()`, `check_output()`, atomic `save()` and
`exit_code`; they retain no private key or private workload.

CLI outputs are checked before replay contact. Saved results protect consumed
receipt, private/trusted-key and workload paths, including hardlink aliases.
Signature artifacts and receiving receipts cannot overwrite inputs or enter the
planner contribution quarantine. Existing v1 import rejects v2; a signature never
promotes a contribution into planner aggregation.

| Exit | Meaning |
|---|---|
| 0 | Artifact signed, signature valid with explicit trust, or completed current-profile replay without known mismatch or unavailable required comparison facts |
| 1 | Known signature/id, private-input or observed replay mismatch |
| 2 | Malformed/unsupported input, unsafe output, or I/O/output failure |
| 3 | Optional crypto/platform unavailable, valid but untrusted signer, incomplete/unavailable replay facts, or native replay failure |

Missing crypto raises `SigningUnavailable` with exit 3 for signing; verification
and replay return unavailable receipts. Structured CLI failures remain bounded JSON
with their native exit code. Existing v1 human defaults and exit semantics remain
unchanged; use `--format v1` or `--format v2` to select explicitly.

## Exact-byte protocol and bounds

The schema2 envelope stores canonical base64 public key, payload and signature.
The payload is strict UTF-8 JSON produced for signing; verification authenticates
its exact decoded bytes before any parsing, without sanitizer rewrites. Outer JSON
whitespace/key order is not signed, and no external canonical-JSON equivalence is
claimed. Duplicate keys, nonfinite values and unsupported public fields are refused.

The signed message concatenates:

1. `b"chimeraforge/signed-contribution/v2\x00ed25519\x00"`;
2. the exact 32-byte public key;
3. the payload byte length as an unsigned eight-byte big-endian integer;
4. the exact payload bytes.

The artifact id is SHA256 of that message followed by the exact 64-byte signature.
Payloads are bounded to 8 MiB, envelopes to 16 MiB, key files to 16 KiB and native
sample populations to 1,000. These are representation/population bounds, not a
deadline or provider-termination guarantee. SDK interfaces and public test vectors
follow [cryptography 50.0.2](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/)
and [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032#section-7.1).
