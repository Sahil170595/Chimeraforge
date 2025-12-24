#!/usr/bin/env python3
"""
Build 4 additional GPT-2 models for TR118v2.1 crossover validation.

Target sizes:
- 0.5M (between 0.103M and 11M)
- 2M (between 0.5M and 11M)
- 5M (between 2M and 11M)
- 50M (between 11M and 124M)

These will fill gaps in the crossover analysis.
"""

import os
from pathlib import Path
import sys

from datasets import load_dataset
import torch
from transformers import GPT2Config, GPT2LMHeadModel, GPT2Tokenizer, Trainer, TrainingArguments

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def estimate_params(n_layer: int, n_embd: int, n_inner: int, vocab_size: int = 50257, n_head: int = 1) -> int:
    """Estimate parameter count for GPT-2 config."""
    # More accurate formula based on actual GPT2LMHeadModel structure
    # Embeddings (tied): vocab_size * n_embd
    # Position embeddings: n_positions * n_embd (typically 1024)
    # Layers: n_layer * (
    #   attention: 
    #     - QKV projection: 3 * n_embd * n_embd (or 3 * n_embd * (n_embd // n_head) * n_head)
    #     - Output projection: n_embd * n_embd
    #   MLP: 
    #     - Up projection: n_embd * n_inner
    #     - Down projection: n_inner * n_embd
    #   Layer norms: 2 * n_embd (pre-attn + pre-mlp)
    # )
    # Final layer norm: n_embd
    
    embed_params = vocab_size * n_embd  # Tied embeddings (wte = lm_head)
    pos_params = 1024 * n_embd  # Position embeddings
    
    # Attention: QKV (3 * n_embd^2) + output (n_embd^2) = 4 * n_embd^2
    # MLP: up (n_embd * n_inner) + down (n_inner * n_embd) = 2 * n_embd * n_inner
    # Layer norms: 2 * n_embd (pre-attn + pre-mlp)
    per_layer = (
        4 * n_embd * n_embd +  # Attention QKV + output
        2 * n_embd * n_inner +  # MLP up + down
        2 * n_embd  # Layer norms (pre-attn + pre-mlp)
    )
    layer_params = n_layer * per_layer
    final_ln = n_embd  # Final layer norm
    
    total = embed_params + pos_params + layer_params + final_ln
    return total


def find_config_for_target(target_params: float, tolerance: float = 0.2) -> GPT2Config:
    """Find GPT-2 config that matches target parameter count."""
    vocab_size = 50257
    n_positions = 1024
    
    # Try different layer/embed combinations
    best_config = None
    best_diff = float('inf')
    
    # Expanded search space for smaller models
    n_embd_options = [48, 64, 80, 96, 112, 128, 144, 160, 192, 256, 320, 384, 448, 512, 640, 768]
    n_layer_options = [1, 2, 3, 4, 5, 6, 8, 10, 12]
    
    for n_layer in n_layer_options:
        for n_embd in n_embd_options:
            # n_embd must be divisible by n_head
            for n_head in [2, 4, 8, 12, 16]:
                if n_embd % n_head != 0:
                    continue
                
                n_inner = 4 * n_embd  # Standard FFN size
                
                try:
                    params = estimate_params(n_layer, n_embd, n_inner, vocab_size, n_head)
                    diff = abs(params / 1e6 - target_params)
                    
                    if diff < best_diff and diff < target_params * tolerance:
                        best_diff = diff
                        best_config = GPT2Config(
                            vocab_size=vocab_size,
                            n_positions=n_positions,
                            n_ctx=n_positions,
                            n_embd=n_embd,
                            n_layer=n_layer,
                            n_head=n_head,
                            n_inner=n_inner,
                            activation_function="gelu_new",
                            resid_pdrop=0.0,
                            embd_pdrop=0.0,
                            attn_pdrop=0.0,
                            layer_norm_epsilon=1e-5,
                            initializer_range=0.02,
                            bos_token_id=50256,
                            eos_token_id=50256,
                            tie_word_embeddings=True,
                        )
                except Exception:
                    continue
    
    if best_config is None:
        raise ValueError(f"Could not find config for {target_params}M params (tried tolerance {tolerance*100}%)")
    
    return best_config


def build_model(target_params: float, model_name: str) -> tuple[GPT2LMHeadModel, GPT2Config, Path]:
    """Build a GPT-2 model with target parameter count."""
    print(f"\n{'='*60}")
    print(f"Building {model_name} (~{target_params}M params)")
    print(f"{'='*60}")
    
    config = find_config_for_target(target_params)
    model = GPT2LMHeadModel(config)
    
    # Count actual parameters
    total_params = sum(p.numel() for p in model.parameters())
    actual_M = total_params / 1e6
    
    print(f"Config:")
    print(f"  Layers: {config.n_layer}")
    print(f"  Hidden: {config.n_embd}")
    print(f"  Heads: {config.n_head}")
    print(f"  FFN inner: {config.n_inner}")
    print(f"  Vocab: {config.vocab_size}")
    print(f"\nActual parameters: {total_params:,} ({actual_M:.3f}M)")
    print(f"Target: {target_params:.3f}M")
    print(f"Difference: {abs(actual_M - target_params):.3f}M")
    
    return model, config, Path(f"models/{model_name}")


def quick_train(model: GPT2LMHeadModel, tokenizer: GPT2Tokenizer, output_dir: Path):
    """Quick training to get non-random weights."""
    print(f"\nTraining {output_dir.name}...")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load dataset
    print("Loading WikiText-2...")
    dataset = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
    
    def tokenize_function(examples):
        # For language modeling, we need to create labels (shifted input_ids)
        tokenized = tokenizer(
            examples["text"],
            truncation=True,
            max_length=128,
            padding="max_length",
            return_tensors="pt",
        )
        # Labels are same as input_ids for language modeling
        tokenized["labels"] = tokenized["input_ids"].clone()
        return tokenized
    
    print("Tokenizing...")
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
    )
    tokenized_dataset.set_format("torch")
    
    # Training args
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=1,
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        learning_rate=5e-4,
        warmup_steps=100,
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=1,
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=0,
        report_to=[],
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
    )
    
    print("Training (1 epoch)...")
    trainer.train()
    
    # Save final model
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"[OK] Model saved to {output_dir}")
    return output_dir


def main():
    """Build all 4 models."""
    # Target sizes - adjust based on what we can actually build
    # We already have: 0.103M, 11M, 124.4M
    # Need: fill gaps between them
    targets = [
        (5.0, "gpt2-5m"),   # Between 0.103M and 11M (already built)
        (25.0, "gpt2-25m"), # Between 11M and 124M (already built)
        (50.0, "gpt2-50m"), # Between 11M and 124M (already built)
        (75.0, "gpt2-75m"), # Between 50M and 124M - NEW
        (100.0, "gpt2-100m"), # Between 75M and 124M - NEW
    ]
    
    # Load tokenizer once
    print("Loading GPT-2 tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token
    
    models_built = []
    
    for target_params, model_name in targets:
        output_dir = Path(f"models/{model_name}")
        
        # Check if model already exists
        if output_dir.exists() and (output_dir / "config.json").exists() and (output_dir / "model.safetensors").exists():
            print(f"\n{'='*60}")
            print(f"Skipping {model_name} - already exists at {output_dir}")
            print(f"{'='*60}")
            models_built.append((model_name, output_dir))
            continue
        
        try:
            model, config, output_dir = build_model(target_params, model_name)
            quick_train(model, tokenizer, output_dir)
            models_built.append((model_name, output_dir))
        except Exception as e:
            print(f"[ERROR] Failed to build {model_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Built {len(models_built)}/{len(targets)} models:")
    for model_name, output_dir in models_built:
        print(f"  {model_name}: {output_dir}")
    
    if len(models_built) == len(targets):
        print("\n[OK] All models built successfully!")
        print("\nNext steps:")
        print("  Run benchmarks for each model:")
        for model_name, output_dir in models_built:
            print(f"    python scripts/tr118/run_tr118v2.py --device cuda --models custom --model-path {output_dir}")
    else:
        print(f"\n[WARN] Only {len(models_built)}/{len(targets)} models built")


if __name__ == "__main__":
    main()

