#!/usr/bin/env python3
"""
Create a custom GPT-2 model with ~45M parameters for TR118 crossover validation.

Target Architecture:
- Layers: 6
- Hidden Size: 512
- Heads: 8
- Vocab: 50257

Estimated Params:
- Embeddings: 50257 * 512 = 25,731,584
- Blocks: 6 * (12 * 512^2) ≈ 18.8M (approx)
- Total: ~44.5M
"""

from pathlib import Path

from transformers import GPT2Config, GPT2LMHeadModel, GPT2Tokenizer


def main():
    repo_root = Path(__file__).resolve().parents[2]
    models_dir = repo_root / "models"
    models_dir.mkdir(exist_ok=True)

    model_name = "gpt2-45m"
    output_dir = models_dir / model_name

    print(f"Creating {model_name} at {output_dir}...")

    config = GPT2Config(
        vocab_size=50257,
        n_positions=1024,
        n_ctx=1024,
        n_embd=512,
        n_layer=6,
        n_head=8,
        activation_function="gelu_new",
        resid_pdrop=0.1,
        embd_pdrop=0.1,
        attn_pdrop=0.1,
        layer_norm_epsilon=1e-5,
        initializer_range=0.02,
    )

    model = GPT2LMHeadModel(config)
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    # Save
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Count params
    params = sum(p.numel() for p in model.parameters())
    print("Model created successfully.")
    print(f"Parameter count: {params:,} ({params/1e6:.2f}M)")
    print(f"Saved to: {output_dir}")

if __name__ == "__main__":
    main()
