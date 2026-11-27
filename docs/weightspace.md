# Verify a weight-space bundle offline

The installed Python library and CLI check every declared local file before returning a receipt.

```console
python examples/weightspace/build_example.py
chimeraforge weightspace verify examples/weightspace/manifest.json
```

```python
from chimeraforge.weightspace import verify_bundle

receipt = verify_bundle("examples/weightspace/manifest.json")
print([(f.path, f.size_bytes) for f in receipt.files])
```

Use `--root DIRECTORY` to supply files from another local directory. An optional trusted `--expected-sha256 DIGEST` (Python keyword `expected_sha256`) pins the manifest itself. An invalid file, pin or declaration produces an error and CLI exit 1. The verifier compares physical sizes and SHA-256 against the supplied manifest. Its `declared_tensors` and `declared_identities` describe the producer's assertions. Independently decoding the target or executing a recipient requires the corresponding codec or runtime.

## Portable wire format

The [two-file example](../examples/weightspace/manifest.json) can be regenerated independently using only Python's standard library. It includes an unchanged bias and a changed F32 matrix whose base contains 134217728 and negative zero. The XOR payload preserves both the target 1 and its positive zero bit. Its SafeTensors file is 88 bytes with SHA-256 `174c39321b58d063defa58d3ce2a3b4f1c0af2fdfc209bffc63c6d62663ac250`. [SafeTensors format](https://github.com/safetensors/safetensors#format)

| Field | Meaning |
| --- | --- |
| `schema` | Exact string `weightspace-manifest/v1`. Other versions fail verification. |
| `codec` | Object with versioned `id` (e.g. `xor-bytes-v1`), boolean `exact`, and object `parameters`. The byte verifier accepts an unfamiliar versioned codec because it only inventories physical files. An operation interpreting a codec must explicitly support it. |
| `identities` | Named lowercase SHA-256 commitments. `target` is required. Name the decode `base`, training `donor`, runnable `recipient`, `config`, `transform` and ordered `classes` separately when applicable. |
| `files` | Nonempty array. Each entry has unique portable relative `path`, `role`, nonempty distinct `phases`, nonnegative integer `size_bytes`, and physical `sha256`. Paths use forward slashes. No symbolic links or case-only aliases. |
| `tensors` | Array describing the target with unique `name`, a byte-aligned numeric SafeTensors `dtype` or `BOOL`, nonnegative integer `shape` and `sha256` of contiguous little-endian row-major logical bytes. An empty shape denotes a scalar. The v1 numeric types are I8/U8, I16/U16, I32/U32, I64/U64, F16/BF16/F32/F64. |
| `metadata` | Optional object for codec-specific entries and additive extensions. A generic verifier preserves the data and ignores unfamiliar fields. |

File roles are `base`, `payload`, `donor`, `recipient`, `decoder`, `adapter`, `config`, `transform`, `labels`, `tokenizer` and `auxiliary`. Phases are `build`, `decode`, `load` and `inference`. Multiple files with identical physical digest and length can declare different paths or roles. File verification visits each declared path.

For the XOR example the model identity is SHA-256 of a UTF-8 JSON array of tensor records sorted by tensor name. Each record contains only `dtype`, `name`, `sha256`, and `shape`. Serialize with sorted object keys, compact separators, literal Unicode and no trailing newline. Unchanged tensor names in `metadata.unchanged` resolve from the exact base. Each remaining target tensor uses a U8 payload of the same name containing the bytewise XOR over its logical bytes. The checked example uses one SafeTensors file per role. The lowercase logical digest of target `weight` is `04837d177d01fc14e6fce367d3aea3422d71ae5e29c6f57789eed77884cf91f2`.

The sidecar carries provenance commitments without requiring a repository checkout, network service or tensor runtime. Protect writes to the source directory while verifying a bundle.

## Estimate a footprint in bytes

`chimeraforge weightspace footprint MANIFEST` and `estimate_footprint(manifest)` verify the inputs and return a ledger in bytes. Supply `--cached-sha256` once per file already held in a content-addressed cache. Cold transfer counts unique content required in the decode, load or inference phases. Additional transfer removes cached digests. Unique on-disk bytes count all inventory content, including build-only artifacts, once per digest. Physical filesystem overhead and the sidecar are outside these counts.

Materialized weight bytes sum the declared target shapes and dtypes. Optional `metadata.tensor_aliases` maps a tied logical tensor directly to its canonical tensor. The two records must have identical dtype, shape and digest. Merely equal tensors still consume separate memory unless the producer declares a tie. Staging bytes count cold deployment data plus a contiguous logical target when a decode is required. This is a modeled data footprint, excluding allocator overhead, temporary decoder buffers and output container headers.

For an inference-time auxiliary file, including a retained base or decoder, supply `metadata.resident_bytes` as a map from file path to bytes beyond the declared target tensors. Unspecified auxiliaries produce a null total and a list of unresolved paths. `metadata.runtime_workspace_bytes` can declare additional runtime memory. The default is unknown. A smaller download on its own does not establish a runtime-memory saving.
