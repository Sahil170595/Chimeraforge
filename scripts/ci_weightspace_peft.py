"""Native CPU PEFT interoperability. Run against the installed Chimeraforge candidate."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from peft import LoraConfig, PeftModel, get_peft_model
from safetensors.torch import save_file
import torch

from chimeraforge.weightspace import admit_adapter


class Classifier(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = torch.nn.Linear(5, 3, bias=False)

    def forward(self, x):
        return self.proj(x)


def main():
    torch.manual_seed(31)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source, fresh = Classifier().cpu(), Classifier().cpu()
        fresh.load_state_dict(source.state_dict())
        checkpoint = root / "weights.safetensors"
        save_file(source.state_dict(), checkpoint)
        data = torch.tensor([[1.0, -1.0, 2.0, 3.0, 1.0]])
        before = fresh(data).detach()
        model = get_peft_model(source, LoraConfig(target_modules=["proj"], r=2, lora_alpha=4))
        with torch.no_grad():
            model.base_model.model.proj.lora_A.default.weight.fill_(0.25)
            model.base_model.model.proj.lora_B.default.weight.fill_(0.5)
        model.peft_config["default"].base_model_name_or_path = "example/local-linear"
        model.peft_config["default"].revision = "a" * 40
        output = root / "adapter"
        model.save_pretrained(output)
        receipt = admit_adapter(
            checkpoint,
            output,
            base_repo="example/local-linear",
            base_revision="a" * 40,
            base_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        )
        restored = PeftModel.from_pretrained(fresh, str(output)).eval()
        expected = before + 0.5 * data.sum()
        torch.testing.assert_close(restored(data), expected)
        torch.testing.assert_close(restored.merge_and_unload()(data), expected)
        assert receipt.tensor_bytes == 4 * (2 * 5 + 3 * 2)
        print(f"Native PEFT CPU round-trip passed. {receipt.tensor_bytes} adapter tensor bytes.")


if __name__ == "__main__":
    main()
