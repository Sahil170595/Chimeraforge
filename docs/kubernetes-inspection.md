# Read-only Kubernetes inspection (unreleased 0.85.0)

Public installation remains 0.81.0. This source candidate depends on the
unreleased 0.82, 0.83 and 0.84 candidates. Keep the original saved plan, candidate
index, concrete model override (when required), image and Kubernetes options
independently from the cluster being inspected.

```bash
chimeraforge deploy-inspect --plan plan.json --candidate-index "$CANDIDATE_INDEX" \
  --image vllm/vllm-openai:v0.30.0 --kubeconfig /private/cluster.conf \
  --context operator-selected --namespace serving --name-prefix original \
  --node-selector operator.example/accelerator=declared \
  --out inspection.json --junit inspection.xml --json
```

Every invocation declares the namespace explicitly; the default is `default`,
not the namespace in the selected context. No context or intent is recovered
from observed resources. The existing native Kubernetes exporter admits online
Linux CUDA vLLM/SGLang plans, original N/TP/PP, model/revision, context, effective
batch, quantization and GPU declarations before starting a native process.
Existing unsupported modes and host-specific options remain refused.

```python
from pathlib import Path
from chimeraforge import api

result = await api.inspect_kubernetes_deployment(
    Path("plan.json"), image="vllm/vllm-openai:v0.30.0",
    candidate_index=selected_index,
    kubeconfig=Path("/private/cluster.conf"), context="operator-selected",
    kubernetes=api.KubernetesOptions(namespace="serving", name_prefix="original"),
    kubectl="kubectl", timeout_s=30, request_timeout_s=10,
    concurrency=4, cleanup_timeout_s=2,
)
api.write_kubernetes_inspection(result, out=Path("inspection.json"),
                               junit=Path("inspection.xml"))
```

`KubernetesInspection` retains all ordered 2N original Deployment/Service rows,
including missing, unavailable and unstarted rows. Deployment rollout is a
separate result; Services have no requested rollout assessment. Native exit 5
for a known missing resource or intent drift takes precedence over unavailable
or pending evidence (4). Exit 0 requires all intent to match and every native
Deployment controller rollout to complete. Invalid independent intent is CLI 1;
native Typer usage errors remain 2. JSON/JUnit publication refusal is CLI 2 and
does not change the typed native outcome. Direct task cancellation propagates
after owned children and streams are joined; `stop_event` instead retains a
stopped report, including completed observations.

The supported native profile is kubectl 1.37.1 and Kubernetes server 1.37.0.
Other/malformed versions and tools remain unavailable, with no fallback. A
client-only version check precedes three selected-context config projections.
An owned, enabled minimal kuberc sets `credentialPluginPolicy: DenyAll`; ambient
aliases/defaults and feature-disable settings cannot bypass that policy.
Any selected legacy `auth-provider`, including OIDC refresh, is refused before
server contact. The product never parses or exports a complete kubeconfig,
copies credentials, runs a credential helper or retries with unrestricted auth.

The three private projections establish provider absence and enumerate only CA,
client certificate/key and token-file paths. Relative paths use the lexical
absolute supplied kubeconfig's parent, including a symlink's parent, matching
the pinned native loader. Runtime config/context/path identities remain outside
serialized dataclass fields, `asdict`, JSON and JUnit; copy/replace retains those
guards. Config and actual source identities are frozen before the first await.
Passing an in-memory plan cannot recover the filename it once came from.

Filesystem publication fails closed when the complete config-referenced path inventory
could not be verified, even if the typed unavailable report or bounded stdout
is inspectable. Known CLI outputs are guarded before contact and again after
private path discovery, before server queries. Later API saves recheck all
retained input identities, resolved aliases and same-file hard links. These
checks do not promise filesystem race exclusion. Both complete requested
encodings and their mutual aliases are admitted before either file write;
individual files use native atomic replacement, not a two-file transaction.
A later filesystem error can leave an earlier file written.

Child-only HOME/USERPROFILE, an owned cache directory and the owned kuberc
confine native migration/cache/policy writes. Parent environment and credential
files are unchanged by this profile. This is GET-only Kubernetes resource
inspection with owned local runtime writes, not a zero-write filesystem claim.
Version/config calls, discovery and resource queries share the observation
deadline. At most 37 native processes (five preflight plus 2N GETs), concurrency
1-4, stdout 1 MiB/process, stderr 16 KiB/process and shared 8 MiB captured-stream
budget are admitted. Readers charge chunks before append; cleanup may discard
remaining pipe data. Request timeouts are positive native durations, clipped
after admission; values below 1 ms are unsupported. The observation deadline
bounds admission/signalling, not a hard return or HTTP byte count. One separate
cleanup allowance starts before final cancellations; overrun/errors remain
reported while cooperative joins continue. Killing one process is not proof
that every possible descendant closed. Owned runtime files close after joins.

`json_bytes()`, `to_dict()` and saves refuse the complete JSON when it exceeds
1 MiB; JUnit refuses above 64 KiB. No row/path truncation or partial normal
receipt is substituted. The bound concerns new encoded buffers/traversal, not
earlier native construction, HTTP responses, heap size or one escaped scalar
chunk. Stdout uses admitted bytes, preserving LF/UTF-8 on Windows too. Typed
`resources` and `exit_code` remain available after export refusal.

All 3N+1 JUnit cases remain: one population, 2N intent and N Deployment rollout
cases. Known drift/missing intent is a failure; unavailable/pending evidence is
an error. Known paths/categories/counts omit actual values and unknown live
keys. Operator map changes use constant parent paths. A complete successful
named GET with empty `--ignore-not-found` output establishes missing; failures,
overflow, malformed/wrong-identity data and forbidden-looking stderr only
establish unavailable. Raw config/resource bodies, native diagnostics, status
messages, runtime context and credential paths are not persisted. Object hashes
bind observed response bytes; they do not authenticate a cluster or producer.

Only pinned conditional server defaults are normalized. Sidecars, env, probes,
volumes, service accounts, selectors, traffic/headless behavior and nondefault
annotations remain observable. Offline `verify_deployment` stays exact and
unchanged. Deployment controller completion follows the pinned native viewer:
observed generation, no progress-deadline failure, updated replicas, retired old
replicas and available replicas. It is not a separate readyReplicas, endpoint,
GPU/plugin, running weights, SLO or capacity check, and no atomic cluster snapshot
is claimed. Saved plan/image/namespace intent can still be private; treat these
reports like their input plans when sharing.

The native client is selected with the supported platform `shutil.which` rules
and held as an absolute path before the first await. Every launch uses that
same selection; output guards protect it alongside the plan/config/referenced
private files, including samefile aliases. Unresolved clients remain unavailable.
This does not freeze executable bytes against concurrent filesystem changes.

Provided condition type, status, reason and message fields must be strings.
Generation fields must fit nonnegative int64 and replica counters nonnegative
int32; omitted optional conditions/counters keep their native defaults. These
are conservative checks of the used native field domains, not a general
OpenAPI validator or a claim that every Go numeric conversion rejects overflow.
Malformed or out-of-domain observations remain unavailable, never controller
completion.

The existing hosted kind job first preserves its original dry-run admission
and nonpersistence controls, then creates and deletes a separate owned live
fixture. Genuine original GPU requests stay intact, so matching intent with
pending rollout/exit 4 is the real positive control. Pure controlled status
fixtures prove classifier 0 separately. Native drift, missing Service,
restricted-service-account denial, plugin/OIDC zero contact and selected-context
and relative/symlink/hardlink guards are additional qualification requirements.
The fixture does not execute inference images or qualify GPU readiness.
Its owned TLS exec-marker positive control runs outside the product's DenyAll
policy; denial then requires no marker or HTTP request. An owned legacy-home
positive control demonstrates native migration, while separate API/CLI caller
home canaries must remain unchanged with no migration target created.

See the [regenerable aggregate protocol evidence](../validation/2026-10-31-kubernetes-inspection/README.md)
and [pinned native implementation sources](#native-profile-sources).

## Native profile sources

- [kuberc policy and supported enable controls](https://kubernetes.io/docs/reference/kubectl/kuberc/)
- [kubectl 1.37.1 preferences application](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/kubectl/pkg/cmd/cmd.go)
- [native config view and minification](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/kubectl/pkg/cmd/config/view.go)
- [native config loading and lexical file origin](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/client-go/tools/clientcmd/loader.go)
- [client-go 0.37.1 TLS-only authentication setup](https://github.com/kubernetes/client-go/blob/v0.37.1/tools/clientcmd/client_config.go)
- [server 1.37.0 core defaults](https://github.com/kubernetes/kubernetes/blob/v1.37.0/pkg/apis/core/v1/defaults.go)
- [server 1.37.0 Deployment defaults](https://github.com/kubernetes/kubernetes/blob/v1.37.0/pkg/apis/apps/v1/defaults.go)
- [kubectl 1.37.1 Deployment rollout viewer](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/kubectl/pkg/polymorphichelpers/rollout_status.go)
- [native Deployment condition and counter types](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/api/apps/v1/types.go)

Sources inspected 2026-10-30 and 2026-10-31. Hosted pinned-tool execution is distinct from
source-supported syntax and controlled local protocol/process evidence.
