"""Native SafeTensors header admission with asymmetric linear layers."""

import hashlib
import json

import pytest

from chimeraforge.weightspace import ManifestError, admit_adapter

np = pytest.importorskip("numpy")
save_file = pytest.importorskip("safetensors.numpy").save_file

REVISION = "a" * 40


def fixture(root, *, wrong_shape=False, missing=False, config=None):
    base = root / "base.safetensors"
    save_file({"proj.weight": np.zeros((3, 5), dtype=np.float32)}, base)
    name = "base_model.model." + ("missing" if missing else "proj")
    save_file(
        {
            name + ".lora_A.weight": np.zeros((2, 5), dtype=np.float16),
            name + ".lora_B.weight": np.ones((4 if wrong_shape else 3, 2), dtype=np.float16),
        },
        root / "adapter_model.safetensors",
    )
    (root / "adapter_config.json").write_text(
        json.dumps(
            {
                "peft_type": "LORA",
                "base_model_name_or_path": "example/model",
                "revision": REVISION,
                "r": 2,
                "lora_alpha": 4,
                "target_modules": ["proj"],
                "bias": "none",
                **(config or {}),
            }
        )
    )
    return base, hashlib.sha256(base.read_bytes()).hexdigest()


def admit(path, root, pin):
    return admit_adapter(
        path, root, base_repo="example/model", base_revision=REVISION, base_sha256=pin
    )


def test_actual_dimensions_and_dtype_bytes(tmp_path):
    path, pin = fixture(tmp_path)
    result = admit(path, tmp_path, pin)
    assert result.tensor_bytes == 2 * (2 * 5 + 3 * 2)
    assert result.targets == ("proj",)
    assert result.scale == 2
    assert result.base_sha256 == pin
    assert (
        result.adapter_sha256
        == hashlib.sha256((tmp_path / "adapter_model.safetensors").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"wrong_shape": True},
        {"missing": True},
        {"config": {"revision": "main"}},
        {"config": {"use_dora": True}},
        {"config": {"layers_to_transform": 0}},
        {"config": {"arrow_config": {}}},
        {"config": {"init_lora_weights": "mica"}},
        {"config": {"lora_dropout": 1.1}},
        {"config": {"lora_dropout": "0.0"}},
        {"config": {"rank_pattern": {"proj": 1}}},
        {"config": {"target_modules": ["proj", "absent"]}},
    ],
)
def test_reject_incompatible(tmp_path, kwargs):
    path, pin = fixture(tmp_path, **kwargs)
    with pytest.raises(ManifestError):
        admit(path, tmp_path, pin)


def test_wrong_base_digest(tmp_path):
    path, _ = fixture(tmp_path)
    with pytest.raises(ManifestError, match="SHA-256"):
        admit(path, tmp_path, "0" * 64)
