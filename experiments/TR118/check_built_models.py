#!/usr/bin/env python3
"""Check which models are built and their parameter counts."""

from pathlib import Path
from transformers import GPT2LMHeadModel

# All target models
target_models = [
    'tiny-gpt2',
    'gpt2-5m',
    'gpt2-1m',  # The 11M model
    'gpt2-25m',
    'gpt2-50m',
    'gpt2-75m',
    'gpt2-100m',
    'gpt2',  # The 124M model
]

print("=" * 60)
print("MODEL BUILD STATUS")
print("=" * 60)
print()

built_models = []
missing_models = []

for model_name in target_models:
    model_path = Path(f"models/{model_name}")
    
    # Check if model exists
    if model_path.exists() and (model_path / "config.json").exists():
        # Try to load and count params
        try:
            model = GPT2LMHeadModel.from_pretrained(str(model_path))
            params = sum(p.numel() for p in model.parameters())
            params_M = params / 1e6
            
            # Check if safetensors or pytorch_model.bin exists
            has_weights = (
                (model_path / "model.safetensors").exists() or
                (model_path / "pytorch_model.bin").exists()
            )
            
            status = "OK" if has_weights else "CONFIG ONLY"
            
            print(f"{model_name:15} | {params_M:8.3f}M params | {status}")
            built_models.append((model_name, params_M))
        except Exception as e:
            print(f"{model_name:15} | ERROR: {e}")
            missing_models.append(model_name)
    else:
        print(f"{model_name:15} | NOT FOUND")
        missing_models.append(model_name)

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Built: {len(built_models)}/{len(target_models)}")
print(f"Missing: {len(missing_models)}/{len(target_models)}")

if built_models:
    print()
    print("Built models (sorted by size):")
    for name, params_M in sorted(built_models, key=lambda x: x[1]):
        print(f"  {name:15} {params_M:8.3f}M")

if missing_models:
    print()
    print("Missing models:")
    for name in missing_models:
        print(f"  {name}")


