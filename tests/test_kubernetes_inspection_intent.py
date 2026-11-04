"""Pinned default/rollout controls never represent a live cluster qualification."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from chimeraforge import api, deploy
from chimeraforge.kubernetes_inspection_intent import compare_intent, rollout, _complete_changes
from test_kubernetes_export import native_plans as native_plans


@pytest.fixture(scope="module")
def objects(native_plans):
    saved, indices = native_plans[3]
    return json.loads(
        deploy.export_deployment(
            saved,
            format="kubernetes",
            image="example/engine:1",
            model="org/manual-fleet",
            candidate_index=indices["vllm"],
            kubernetes=api.KubernetesOptions(namespace="inspection", name_prefix="original"),
        ).content
    )["items"]


def defaulted(expected):
    actual = deepcopy(expected)
    actual["metadata"].update(
        uid="fixture",
        resourceVersion="123",
        generation=1,
        creationTimestamp="2026-10-30T00:00:00Z",
        managedFields=[],
    )
    if actual["kind"] == "Deployment":
        actual["spec"].update(revisionHistoryLimit=10, progressDeadlineSeconds=600)
        actual["spec"]["template"]["metadata"]["creationTimestamp"] = None
        pod = actual["spec"]["template"]["spec"]
        pod.update(
            restartPolicy="Always",
            dnsPolicy="ClusterFirst",
            schedulerName="default-scheduler",
            securityContext={},
            terminationGracePeriodSeconds=30,
        )
        container = pod["containers"][0]
        container.update(
            imagePullPolicy="IfNotPresent",
            terminationMessagePath="/dev/termination-log",
            terminationMessagePolicy="File",
        )
        container["ports"][0]["protocol"] = "TCP"
        actual["metadata"]["annotations"]["deployment.kubernetes.io/revision"] = "1"
        actual["status"] = {
            "observedGeneration": 1,
            "replicas": 1,
            "updatedReplicas": 1,
            "availableReplicas": 1,
        }
    else:
        actual["spec"].update(
            clusterIP="10.0.0.10",
            clusterIPs=["10.0.0.10"],
            ipFamilies=["IPv4"],
            ipFamilyPolicy="SingleStack",
            sessionAffinity="None",
            internalTrafficPolicy="Cluster",
        )
    return actual


@pytest.mark.parametrize("index", range(6))
def test_full_pinned_defaults_match_but_do_not_establish_gpu_readiness(objects, index):
    actual = defaulted(objects[index])
    assert compare_intent(objects[index], actual)["state"] == "match"
    assert rollout(actual)["state"] == ("complete" if index % 2 == 0 else "not_requested")


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("observedGeneration", 0, "generation_unobserved"),
        ("updatedReplicas", 0, "updated_replicas_pending"),
        ("replicas", 2, "old_replicas_pending"),
        ("availableReplicas", 0, "available_replicas_pending"),
        (
            "conditions",
            [{"type": "Progressing", "reason": "ProgressDeadlineExceeded", "message": "private"}],
            "progress_deadline_exceeded",
        ),
    ],
)
def test_native_rollout_is_separate_from_matching_intent(objects, field, value, reason):
    actual = defaulted(objects[0])
    actual["status"][field] = value
    assert compare_intent(objects[0], actual)["state"] == "match"
    assert rollout(actual)["state"] == "pending"
    assert rollout(actual)["reason"] == reason
    assert "private" not in json.dumps(rollout(actual))


def test_native_viewer_does_not_require_ready_replicas(objects):
    actual = defaulted(objects[0])
    actual["status"]["readyReplicas"] = 0
    assert rollout(actual)["state"] == "complete"


@pytest.mark.parametrize(
    "edit",
    [
        "image",
        "argv",
        "selector",
        "sidecar",
        "env",
        "probe",
        "service_account",
        "annotation",
        "strategy",
    ],
)
def test_behavior_additions_are_drift_without_live_key_or_value_echo(objects, edit):
    actual = defaulted(objects[0])
    pod = actual["spec"]["template"]["spec"]
    container = pod["containers"][0]
    secret = "private-live-canary"
    if edit == "image":
        container["image"] = secret
    elif edit == "argv":
        container["args"].append(secret)
    elif edit == "selector":
        pod["nodeSelector"][secret] = secret
    elif edit == "sidecar":
        pod["containers"].append({"name": secret, "image": secret})
    elif edit == "env":
        container["env"] = [{"name": secret, "value": secret}]
    elif edit == "probe":
        container["readinessProbe"] = {"exec": {"command": [secret]}}
    elif edit == "service_account":
        pod["serviceAccountName"] = secret
    elif edit == "annotation":
        actual["metadata"]["annotations"][secret] = secret
    else:
        actual["spec"]["strategy"] = {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
        }
    result = compare_intent(objects[0], actual)
    assert result["state"] == "drift"
    assert secret not in json.dumps(result)


@pytest.mark.parametrize("edit", ["headless", "traffic", "family", "port", "annotations"])
def test_service_changes_remain_observable(objects, edit):
    actual = defaulted(objects[1])
    if edit == "headless":
        actual["spec"]["clusterIP"] = "None"
    elif edit == "traffic":
        actual["spec"]["internalTrafficPolicy"] = "Local"
    elif edit == "family":
        actual["spec"]["ipFamilyPolicy"] = "RequireDualStack"
    elif edit == "port":
        actual["spec"]["ports"][0]["targetPort"] += 1
    else:
        actual["metadata"]["annotations"]["private-key"] = "private-value"
    assert compare_intent(objects[1], actual)["state"] == "drift"


@pytest.mark.parametrize("value", [True, 1.0, "1", -1])
def test_rollout_counts_do_not_accept_boolean_or_numeric_spelling(objects, value):
    actual = defaulted(objects[0])
    actual["status"]["availableReplicas"] = value
    assert rollout(actual)["state"] == "unknown"


def test_complete_changes_do_not_inherit_offline_path_truncation():
    expected = {"spec": {"args": [f"expected-{i}" for i in range(128)]}}
    actual = {"spec": {"args": ["private" for _ in range(128)], "private-key": "private"}}
    changes = _complete_changes(expected, actual)
    assert len(changes) == 129 and sum(row["count"] for row in changes) == 129
    assert "private" not in json.dumps(changes)
    assert {row["path"] for row in changes} == {"/spec", *(f"/spec/args/{i}" for i in range(128))}


@pytest.mark.parametrize("key,value", [("name", "other"), ("namespace", "other")])
def test_successful_wrong_identity_is_unavailable_not_known_drift(objects, key, value):
    actual = defaulted(objects[0])
    actual["metadata"][key] = value
    with pytest.raises(ValueError):
        compare_intent(objects[0], actual)


@pytest.mark.parametrize("kind,index", [("Deployment", 0), ("Service", 1)])
def test_malformed_status_is_not_a_matching_resource(objects, kind, index):
    actual = defaulted(objects[index])
    actual["status"] = "private-invalid-status"
    with pytest.raises(ValueError):
        compare_intent(objects[index], actual)


def test_independent_label_names_do_not_become_public_change_paths(objects):
    expected = deepcopy(objects[0])
    expected["spec"]["template"]["spec"]["nodeSelector"]["private-operator-label"] = "expected"
    actual = defaulted(expected)
    actual["spec"]["template"]["spec"]["nodeSelector"]["private-operator-label"] = "changed"
    result = compare_intent(expected, actual)
    assert result["state"] == "drift"
    assert "private-operator-label" not in json.dumps(result)
    assert result["changes"][0]["path"] == "/spec/template/spec/nodeSelector"
