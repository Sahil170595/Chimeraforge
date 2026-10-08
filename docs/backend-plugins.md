# Installed backend plugins

ChimeraForge can select a locally installed serving adapter for `bench`, `measure`,
and `safety`. Install the adapter in the same Python environment as ChimeraForge,
then select its entry-point name:

```sh
chimeraforge bench --list-backends
chimeraforge bench --list-backends --json
chimeraforge bench --model my-served-model --backend my-engine --base-url http://localhost:9000
chimeraforge measure --model my-served-model --backend my-engine --quant FP16
chimeraforge safety --model my-served-model --backend my-engine --prompts probes.txt
```

Listing reads installed distribution metadata and does not import or construct
plugin adapters. Selecting a plugin loads **trusted local Python code**. Plugins
are not sandboxed; install packages whose code and dependencies you trust.
ChimeraForge does not download or install adapters during discovery or selection.

The package declares a Python packaging entry point:

```toml
[project.entry-points."chimeraforge.backends"]
my-engine = "my_adapter.backend:MyEngineBackend"
```

The exported object must be a concrete subclass of
`chimeraforge.bench.backends.base.Backend`, with `name = "my-engine"`. Names start
with a lowercase ASCII letter and contain only lowercase letters, digits,
hyphens, or underscores. The constructor must accept no arguments; it should
also accept `base_url` if it supports the CLI URL override. Construction should
not start task-owned processes or perform network I/O: resources acquired before
a constructor raises cannot be closed by the caller.

Implement these async methods using the actual serving engine's API:

| Method | Contract |
| --- | --- |
| `health_check()` | Return `(bool, message)`; verify engine identity, rather than treating any HTTP 200 as healthy. |
| `check_model(model)` | Return `(bool, message)`; verify the requested model is actually available. |
| `get_version()` | Return an engine version string, or `None` when unknown. |
| `generate(model, prompt, options=None)` | Return `RunMetrics` from observed timing and server token counts; raise with context if required measurements are unavailable. |
| `generate_text(model, prompt, options=None)` | Optional; return generated text for safety screening. The inherited implementation raises `NotImplementedError`. |
| `close()` | Optional; release clients and resources. The inherited implementation does nothing for stateless adapters. |

All methods must remain async, including optional overrides. Benchmark and safety
runners close an adapter after success, preflight or generation failure, and
cancellation. A cleanup failure is logged with context; it fails an otherwise
successful operation and preserves an earlier operation's exception. Adapters
must make their own cleanup safe when generation is cancelled.

Duplicate entry-point names and collisions with `ollama`, `vllm`, `tgi`, or
`sglang` fail deterministically during plugin discovery. Invalid or abstract
classes, mismatched `name`, sync methods, imports, and initialization failures
are reported with entry-point and distribution context. Only the explicitly
selected plugin is loaded: an unrelated plugin with a broken import cannot
prevent another valid adapter from loading. Built-in selection bypasses plugin
discovery entirely, so malformed plugin metadata cannot disable built-in engines.

Plugin measurement rows retain their own backend name in the corpus. Installing
a plugin does not copy another engine's calibrated coefficients or add the engine
to the capacity planner's supported engine/platform matrix. `measure` records
observations under the selected name; planner enumeration remains limited to its
documented engines. Quality and safety calibration are separate from functional
adapter acceptance. A plugin context sweep is conservatively labelled as a
context label that was not applied; the generic runner has no plugin-specific
per-request context contract. Quant sweeps remain labels rather than switches to
different served checkpoints.

The installed-package acceptance test builds and installs an independent fixture
wheel, checks metadata listing before import, and exercises selection, CPU work,
benchmark JSON, measurement corpus keys, safety scoring, and cleanup. Its fixture
tokenizer and replies test integration; they make no claim about LLM inference
performance, GPU behavior, or safety accuracy.

This interface uses Python's supported
[importlib.metadata entry-point discovery and loading API](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
and the [PyPA entry-point specification](https://packaging.python.org/en/latest/specifications/entry-points/),
checked on 2026-10-05. Python 3.10 and later support discovery by `group`;
`EntryPoint.load()` resolves the adapter only after selection.
