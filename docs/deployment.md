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

The [checkpoint identity](planning-api.md#checkpoint-identity) feature, available since 0.57.0,
adds the resolved HF commit to vLLM/TGI/SGLang commands through their native
`--revision` option, including their default same-repository tokenizer. Branches
and tags are resolved before planning; exports use the saved commit, with no Hub
call. Config-byte and declared LFS receipts do not verify downloaded or served
weights/tokenizer bytes. Ollama conversion cannot retain an HF pin and is
refused. Older unpinned HF snapshots still export with a missing-binding note;
replan online to bind a commit.

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
declare a root service or invent a service account. By default its `CUDA_VISIBLE_DEVICES`
selects GPU indices `0..TP*PP-1`; check that those are the planned hardware before
starting it. By default Compose reserves the same count of NVIDIA devices and publishes only
on `127.0.0.1`. It does not identify GPU models or provision an NVIDIA runtime.

## Explicit device selection and host ports

These options are an **unreleased 0.73.0 candidate** and require candidate source
or a built candidate wheel. Published 0.71.0 retains default GPU counts and ports;
0.72.0's candidate hardware studies do not select observed deployment devices.

The direct module API (replica keywords introduced by the 0.74.0 candidate) is
`chimeraforge.deploy.export_deployment(artifact, *, format, model=None,
image=None, candidate_index=0, executable=None, output_path=None,
gpu_devices=None, host_port=None, replica_gpu_devices=None, replica_host_ports=None)`. It renders configuration; only the CLI writes
new output files. The two replica keywords are introduced only by the 0.74.0
candidate; the 0.73.0 candidate supports the singular options. All four options
default to `None`, preserving supported legacy
export content byte for byte. Explicit `gpu_devices=[]` is an error.

Repeat `--gpu-device` in caller order once per selected candidate's **TP x PP**,
not once per replica. These singular options support one replica; multi-replica
layouts use the separate 0.74.0 candidate interface below. For example, produce an
offline manual geometry plan, then select its actual one-replica vLLM FP16 row:

```bash
chimeraforge plan --model org/manual-placement --params-b 3 --n-layers 28 \
  --n-kv-heads 8 --d-head 128 --hardware "RTX 4090 24GB" --platform linux \
  --tensor-parallel 2 --request-rate 0.01 --quality-target 0 --budget 100000 \
  --no-network --save placement-plan.json --json
CANDIDATE_INDEX=$(python -c "import json; p=json.load(open('placement-plan.json')); print(next(i for i,c in enumerate(p['result']['candidates']) if c['backend']=='vllm' and c['quant']=='FP16' and c['n_agents']==1 and c['tensor_parallel']==2 and c['pipeline_parallel']==1 and c['offload_fraction']==0))")
mkdir placement
chimeraforge deploy --plan placement-plan.json --candidate-index "$CANDIDATE_INDEX" \
  --model org/manual-placement --format compose --image example/engine:1 \
  --gpu-device 7 --gpu-device 3 --host-port 9001 --out placement/compose.json
chimeraforge deploy --plan placement-plan.json --candidate-index "$CANDIDATE_INDEX" \
  --model org/manual-placement --format systemd --executable /opt/vllm/bin/vllm \
  --gpu-device 7 --gpu-device 3 --out placement/inference.service
```

The manual identity and image above are explicit illustrative assumptions, not
verified model weights or a qualified engine image. Resolve a concrete checkpoint
and supply your matching installed engine/image for an actual deployment.
The saved platform, model geometry, context, dtype, KV settings, TP/PP and all
native fidelity gates remain enforced; these options cannot enable an otherwise
unsupported backend, platform, recurrent state, LoRA, offload or replica layout.

```python
from chimeraforge.api import load_plan
from chimeraforge.deploy import export_deployment

saved = load_plan("placement-plan.json")
index = next(i for i, c in enumerate(saved.to_dict()["result"]["candidates"])
    if c["backend"] == "vllm" and c["quant"] == "FP16" and c["n_agents"] == 1
    and c["tensor_parallel"] == 2 and c["pipeline_parallel"] == 1
    and c["offload_fraction"] == 0)
config = export_deployment(saved, format="compose", candidate_index=index,
    model="org/manual-placement", image="example/engine:1",
    gpu_devices=["7", "3"], host_port=9001)
print(config.content)  # no file write, host probe, engine start or inference
```

Device selection is supported only for **Linux NVIDIA CUDA Compose and systemd**.
Use either ASCII canonical decimal ordinals (`"0"`, `"7"`, `"3"`) or full GPU UUIDs,
for example `GPU-ad2367dd-a40e-6b86-6fc3-c44a2cc92c7e`. To select UUIDs, replace both
CLI values or pass a list of full UUIDs in Python. UUID casing is canonicalized to
`GPU-` plus lowercase hex; input order is retained. No host ordinal bound is
inferred from the number of selected GPUs: `['7', '3']` is valid for TP=2.

The API requires an actual list of strings, not a comma-separated string, tuple,
generator or custom list subtype. Selections refuse leading-zero/negative/signed/
whitespace/Unicode-digit aliases, abbreviated UUIDs, MIG IDs, duplicate IDs
(including case aliases), mixed UUID/ordinal namespaces and incorrect cardinality.
Each identifier is bounded to 40 characters. A named **64 GPUs per replica export
admission limit** bounds validation/output work, including default systemd lists;
saved candidates above that bound are refused even without explicit placement.
It is not a native planner limit, topology observation or physical host ceiling.

Compose emits the ordered `device_ids` declaration **instead of `count`**, retains
`capabilities: [gpu]`, and does not copy host ordinals into container
`CUDA_VISIBLE_DEVICES`. Container visibility and CUDA enumeration/remapping are
different controls. The declared list order is not observed CUDA rank mapping;
verify the actual runtime separately. systemd emits `CUDA_VISIBLE_DEVICES` in the
requested application order. Numeric selectors depend on each runtime's device
enumeration; full UUIDs avoid relying on a host index remaining stable.

`--host-port` / `host_port` is Compose-only and must be an integer 1..65535 (Python
booleans are refused). Publishing remains bound to `127.0.0.1`. The override
changes only the host port; native container ports remain vLLM 8000, SGLang 30000,
TGI 80, and Ollama 11434. Default host ports remain 8000, 30000, 8080 and 11434
respectively. Unsupported option/format combinations refuse before output rather
than being ignored. Existing main/companion output files and the source plan stay
protected by the existing exclusive-create contract.

These are **offline declarations**: no device existence, accessibility, CUDA rank,
GPU model/topology, weights, engine availability or measured serving performance
is verified. Installed CPU CLI/API and actual `docker compose config` acceptance
validate declarations and syntax only. Device/runtime semantics were rechecked on
**2026-10-22** against [Docker GPU support](https://docs.docker.com/compose/how-tos/gpu-support/),
[Compose device reservations](https://docs.docker.com/reference/compose-file/deploy/),
[NVIDIA container visibility](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html),
[CUDA environment variables](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html)
and [NVIDIA device ordering](https://docs.nvidia.com/deploy/topics/topic_5_2_1.html).

## Homogeneous Compose replicas

The **unreleased 0.74.0 candidate** renders an original selected multi-replica
candidate as independent named Compose services. It supports **online-mode,
Linux NVIDIA CUDA vLLM and SGLang only**. Here, homogeneous means the saved model,
revision, backend, quantization, context and per-replica geometry/settings remain
the same. It does not attest physical GPU-model equality or independent capacity.
The native batch planner can produce multi-replica candidates; those remain
outside this deliberately narrower export scope.

Every original replica requires both an explicit ordered GPU group and a distinct
loopback host port. API options are keyword-only
`replica_gpu_devices: list[list[str]] | None` and
`replica_host_ports: list[int] | None`. The CLI repeats
`--replica-devices ID,ID` and `--replica-port PORT` in corresponding replica order.
Do not mix these with singular `gpu_devices`/`host_port` or
`--gpu-device`/`--host-port`, even if the values agree. A one-replica candidate
must use the singular interface; replica matrices are refused for N=1.

For a complete offline example, produce an actual native three-replica candidate
using explicit illustrative geometry, then select its own vLLM FP16 row:

```bash
chimeraforge plan --model ci/manual-fleet --params-b 3 --n-layers 28 \
  --n-kv-heads 8 --d-head 128 --hardware "RTX 4090 24GB" --platform linux \
  --tensor-parallel 2 --request-rate 128 --latency-slo 10000 \
  --quality-target 0 --budget 100000 --no-network --save fleet-plan.json --json
FLEET_INDEX=$(python -c "import json; p=json.load(open('fleet-plan.json')); print(next(i for i,c in enumerate(p['result']['candidates']) if c['backend']=='vllm' and c['quant']=='FP16' and c['n_agents']==3 and c['tensor_parallel']==2 and c['pipeline_parallel']==1 and c['offload_fraction']==0))")
mkdir fleet
chimeraforge deploy --plan fleet-plan.json --candidate-index "$FLEET_INDEX" \
  --model org/manual-fleet --format compose --image example/engine:1 \
  --replica-devices 7,3 --replica-port 9001 \
  --replica-devices 9,2 --replica-port 9002 \
  --replica-devices 8,4 --replica-port 9003 --out fleet/compose.json
docker compose --file fleet/compose.json config
```

The sample model/image are explicit illustrative assumptions, not provisioned
weights or an available engine image. Resolve your real checkpoint and supply its
matching image for actual use. The exporter preserves that saved HF revision
through every service's native `--revision`; manual size-class overrides retain
their existing geometry warning. It does not install/start the image or inference.

```python
from chimeraforge.api import load_plan
from chimeraforge.deploy import export_deployment

saved = load_plan("fleet-plan.json")
index = next(i for i, c in enumerate(saved.to_dict()["result"]["candidates"])
    if c["backend"] == "vllm" and c["quant"] == "FP16" and c["n_agents"] == 3
    and c["tensor_parallel"] == 2 and c["pipeline_parallel"] == 1
    and c["offload_fraction"] == 0)
exported = export_deployment(saved, format="compose", candidate_index=index,
    model="org/manual-fleet", image="example/engine:1",
    replica_gpu_devices=[["7", "3"], ["9", "2"], ["8", "4"]],
    replica_host_ports=[9001, 9002, 9003])
print(exported.content)  # rendering only; the saved plan/candidate remain unchanged
```

The saved N=3 and total GPU count=6 remain intact. The output services are
`inference-1`, `inference-2`, `inference-3`, each with TP=2 and the **original
per-replica batch**, not batch multiplied by N. They share the model/revision and
serving controls; every service records the original plan fingerprint, replica
index and total replica count. There is no `deploy.replicas` shortcut hiding an
unplaced population. No router or scaler is supplied. After your separately
verified setup/startup, manually target the endpoints:

| Service | Host endpoint | Container port (vLLM) | Declared GPU IDs |
| --- | --- | --- | --- |
| `inference-1` | `http://127.0.0.1:9001` | 8000 | `7,3` |
| `inference-2` | `http://127.0.0.1:9002` | 8000 | `9,2` |
| `inference-3` | `http://127.0.0.1:9003` | 8000 | `8,4` |

For SGLang, select the actual SGLang candidate and matching image; its native
container port remains 30000. Loopback ports are explicit rather than invented
by arithmetic. Their availability is not probed. The printed Compose start command
is an operator instruction, not an action performed by export.

Population is bounded by the native `MAX_REPLICAS=16`; TP x PP is bounded to 64
GPUs **per replica**. The original total must equal N x TP x PP, so a valid grand
total can exceed 64 (for example, 16 replicas x 8 GPUs = 128). The renderer admits and
uses the original candidate throughout; it does not copy it as a one-agent plan.
Native model/checkpoint/quant/KV/platform/PP/offload/LoRA/recurrent-state and other
fidelity refusals stay active. TGI, Ollama, native-unit formats and batch-mode
multi-replica plans are refused.

API matrices must be actual lists: exactly N groups of exactly TP x PP strings
and N integer ports 1..65535, excluding booleans. IDs retain the singular interface's
canonical ASCII ordinal/full-UUID grammar and 40-character bound. Use one namespace
across the entire fleet, and globally disjoint canonical IDs; case-normalized UUID
aliases also collide. All ports must be distinct. Missing/empty/incomplete layouts,
wrong totals, mixed singular/matrix options, invalid names/aliases, overlap and
unsupported modes/formats refuse before output. CLI group strings are bounded
before splitting; whitespace, empty tokens and abbreviated UUID/MIG names are not
silently normalized. Entire groups and their IDs retain caller order.

Compose reserves each service's `device_ids` instead of `count`. It does not copy
numeric host IDs into container CUDA visibility or verify CUDA rank mapping.
The same Docker/NVIDIA visibility semantics linked above apply. No physical GPU
existence/type/topology, independent capacity, model-weight access, engine
compatibility or serving performance is verified. Actual installed CPU CLI/API
and Compose-parser acceptance establish declaration/transport syntax only.

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

Exports refuse configurations they cannot express: unsupported multi-replica
formats/backends/modes/layouts, CPU
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


## Offline declaration drift verification

The **unreleased 0.75.0 candidate** adds a separate read-only `deploy-verify`
command and typed `deployment_verify.verify_deployment` API. Retain the saved plan,
selected candidate and full rendering options independently; verify generated JSON
Compose plus only required fixed sibling bytes. See [the complete contract,
CLI/API examples and bounds](deployment-verification.md). This checks consistency
with the current renderer; it does not validate runtime state or authenticate a producer.
