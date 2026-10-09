# Export deployment configuration

`chimeraforge deploy` reads a saved plan and writes configuration for one selected
candidate. It checks the artifact's fingerprint, carries its identity into the
output, and reports predictions and unresolved runtime assumptions. It performs
no network calls, package installation, engine startup or infrastructure changes.

```bash
chimeraforge plan --model Qwen/Qwen2.5-1.5B-Instruct --hardware "RTX 4090 24GB" \
  --ttft-slo 500 --tpot-slo 50 \
  --save plan.json
CANDIDATE_INDEX=$(python -c "import json; p=json.load(open('plan.json')); print(next(i for i,c in enumerate(p['result']['candidates']) if c['backend']=='vllm' and c['quant']=='FP16' and c['n_agents']==1 and c['offload_fraction']==0))")
chimeraforge deploy --plan plan.json --candidate-index "$CANDIDATE_INDEX" --format compose \
  --image vllm/vllm-openai:v0.30.0 --out deployment/compose.yaml
```

Create the output directory first. Choose an image matching the **selected
candidate's backend**, with an explicit version tag or SHA256 digest; the exporter
does not infer an image, download it, or inspect its engine version. Version tags
can move; a digest fixes content. Existing main or companion files are refused.
The Bash selection above uses the current artifact's zero-based index, not a
fixed row number. On PowerShell, assign the same selection with
`$CANDIDATE_INDEX = python -c "..."`. Inspect the selected candidate; no match is
an error. A Hugging Face name does not make the first candidate vLLM or prove
that its chosen quantization exists at that checkpoint.
Printed provisioning commands use the chosen output filename, including `-f` for
every Compose command, and shell-quote paths. Library calls to `export_deployment`
can supply `output_path` to bind the instructions to their chosen destination.
The exporter accepts resolved model identities; for an unresolved registry/manual
size class, `--model org/concrete-model` can supply an unquantized HF identity. That
override retains the size-class prediction and an explicit note; resolving and
replanning the actual checkpoint provides its actual geometry.

| Format | Supported target | Required additional input |
| --- | --- | --- |
| `compose` | Linux NVIDIA CUDA, vLLM/SGLang/TGI/Ollama | Explicit engine image tag/digest |
| `systemd` | Linux CUDA per-user vLLM/SGLang/Ollama service | `--executable` absolute installed engine/interpreter path |
| `launchd` | macOS per-user Ollama LaunchAgent | `--executable` absolute installed Ollama binary path |
| `modelfile` | Resolved Ollama checkpoint | A dedicated daemon with the printed environment settings |

```bash
chimeraforge deploy --plan plan.json --candidate-index "$CANDIDATE_INDEX" --format systemd \
  --executable /opt/vllm/bin/vllm --out deployment/chimeraforge.service
```

For SGLang, `--executable` is the Python interpreter containing SGLang. Native
services use the exact supplied executable, argument arrays/escaped `ExecStart`,
and loopback bindings. The systemd template is a **user** service; it does not
declare a root service or invent a service account. Its `CUDA_VISIBLE_DEVICES`
selects GPU indices `0..TP*PP-1`; check that those are the planned hardware before
starting it. Compose reserves the same count of NVIDIA devices and publishes only
on `127.0.0.1`. It does not identify GPU models or provision an NVIDIA runtime.

Ollama exports run `ollama serve`, rather than an interactive `ollama run` client.
Compose/native-unit exports also write `Modelfile` beside the output. Start the
dedicated daemon, then follow the printed `ollama pull` and `ollama create` steps
from that directory. Compose mounts its companion at
`/etc/chimeraforge/Modelfile`. Requests must use the printed
`chimeraforge-<fingerprint-prefix>` model name. The Modelfile sets the planned
context; daemon environment sets concurrency, one loaded model, context and KV
dtype. A standalone Modelfile cannot configure daemon concurrency/KV dtype, so
those required settings are printed separately. The daemon is not automatically
populated or warmed up. Quit an existing Ollama daemon before loading the native
unit to avoid port conflicts.

Exports refuse configurations they cannot express: multiple replicas, CPU
offload, unresolved LoRA adapter paths, unsupported platforms, multi-GPU Ollama,
TGI pipeline parallelism, backend-incompatible GGUF weight formats or q4 KV,
unknown/mismatched quantized checkpoint identity, recurrent-state memory pools
and unsupported chunked-prefill/prefix-cache assumptions. Saved recurrent-state
metadata records whether a dtype was declared, but does not preserve its exact
value. The exporter refuses these models on every backend instead of inferring
FP32 from that flag or relying on an unrecorded engine default. A real
model name alone does not establish its quantization. Replan with resolved model
metadata rather than substituting an arbitrary AWQ/GPTQ/FP8/Ollama checkpoint.
Changing a resolved checkpoint requires replanning it. SGLang/TGI BF16 or
quantized checkpoints with implicit KV dtype are refused for a planned `fp16`
cache; select a compatible explicitly mapped `q8` plan instead. Unmodeled chunked
prefill is explicitly disabled for vLLM and SGLang.

The exporter propagates context, concurrency, TP/PP, weight dtype/native
quantization and compatible KV dtype. The plan's `q8` KV memory scale maps to the
backend's FP8 cache; cache accuracy/scaling-factor requirements need separate
validation. vLLM's GPU memory utilization remains a starting value from the
existing launcher, explicitly labeled as such. A valid config does not establish
that the weights fit, inference succeeds, or a predicted throughput/SLO is met.
Other planner assumptions such as request arrival rate and prefix-hit rate are
workload properties, not deployment guarantees.

Run format validators before installing/starting anything:

```bash
docker compose --file deployment/compose.yaml config
systemd-analyze --user verify deployment/chimeraforge.service
plutil -lint deployment/org.chimeraforge.inference.plist
```

Compose output is JSON, which Compose accepts as a YAML subset. Strings containing
`$` are escaped for Compose interpolation, and commands use argument lists rather
than a shell. systemd arguments separately escape quoting, `%` specifiers and `$`
variables. launchd uses a real XML property list with `ProgramArguments`.

The config syntax and engine switches were checked against the following primary
documentation on **2026-10-05**:

- [Docker GPU device reservations](https://docs.docker.com/compose/how-tos/gpu-support/)
  and [Compose interpolation](https://docs.docker.com/reference/compose-file/interpolation/).
- [systemd command parsing](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
  and [Apple LaunchAgent property lists](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).
- [vLLM v0.30.0 serving arguments](https://docs.vllm.ai/en/v0.30.0/cli/serve/),
  [SGLang serving arguments](https://docs.sglang.io/docs/advanced_features/server_arguments)
  and [TGI launcher arguments](https://huggingface.co/docs/text-generation-inference/en/reference/launcher).
- [Ollama Modelfiles](https://docs.ollama.com/modelfile) and
  [Ollama concurrency, context and KV settings](https://docs.ollama.com/faq).

Tests exercise Docker Compose's real parser, Linux `systemd-analyze verify`, and
macOS `plutil -lint` where those tools are installed. These are config acceptance
checks; they do not run a GPU engine or qualify prediction accuracy.
