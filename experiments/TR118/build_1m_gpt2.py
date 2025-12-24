"""
Build and train a ~1M parameter GPT-2 model for crossover validation.

Target: ~1M parameters (predicted crossover point: 1.2M)
Config: 6 layers, 8 heads, 512 hidden dim
"""

import os

from datasets import load_dataset
import torch
from transformers import GPT2Config, GPT2LMHeadModel, GPT2Tokenizer, Trainer, TrainingArguments


def build_1m_gpt2():
    """Build a ~1M parameter GPT-2 model."""

    # Calculate exact parameter count for different configs
    # Formula: vocab * embed + layers * (4*embed^2 + 4*embed*4*embed) + context*embed + embed
    # Simplified: vocab*embed + layers*(20*embed^2) + context*embed

    # Config targeting ~1M params
    # Formula: vocab*embed + layers*(12*embed^2 + 4*embed*ffn_dim) + context*embed
    # Target: ~1M with tied embeddings
    config = GPT2Config(
        vocab_size=50257,      # Standard GPT-2 tokenizer
        n_positions=1024,      # Max sequence length
        n_embd=192,            # Hidden dimension (much smaller: 192 vs 768)
        n_layer=3,             # 3 transformer blocks (vs 12)
        n_head=3,              # 3 attention heads (must divide n_embd)
        n_inner=768,           # FFN inner dim (4 * n_embd)
        activation_function="gelu_new",
        resid_pdrop=0.0,
        embd_pdrop=0.0,
        attn_pdrop=0.0,
        layer_norm_epsilon=1e-5,
        initializer_range=0.02,
        bos_token_id=50256,
        eos_token_id=50256,
        tie_word_embeddings=True,  # Tie input/output embeddings (saves params)
    )

    print("Building model with config:")
    print(f"  Layers: {config.n_layer}")
    print(f"  Hidden: {config.n_embd}")
    print(f"  Heads: {config.n_head}")
    print(f"  Vocab: {config.vocab_size}")

    # Initialize model
    model = GPT2LMHeadModel(config)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print("\nParameter count:")
    print(f"  Total: {total_params:,} ({total_params/1e6:.2f}M)")
    print(f"  Trainable: {trainable_params:,}")

    return model, config

def quick_train(model, tokenizer, output_dir="models/gpt2-1m"):
    """
    Quick training on WikiText-2 to get non-random weights.
    Not aiming for SOTA, just need coherent weights for benchmark.
    """

    print("\nLoading WikiText-2 dataset...")
    dataset = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=128,  # Short sequences for fast training
            padding="max_length",
            return_tensors="pt",
        )

    print("Tokenizing dataset...")
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
    )
    tokenized_dataset.set_format("torch")

    # Training args - minimal training, just enough to get non-random weights
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=1,         # Just 1 epoch
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        learning_rate=5e-4,
        warmup_steps=100,
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=1,
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=0,   # Windows compatibility
        report_to="none",           # No wandb/tensorboard
    )

    # Simple data collator
    from transformers import DataCollatorForLanguageModeling
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # Causal LM, not masked
    )

    print("\nStarting training (1 epoch, ~5-10 minutes)...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    trainer.train()

    print(f"\nSaving model to {output_dir}...")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print(f"[OK] Model saved to {output_dir}")

    return output_dir

if __name__ == "__main__":
    # Build model
    model, config = build_1m_gpt2()

    # Load tokenizer (use standard GPT-2 tokenizer)
    print("\nLoading GPT-2 tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    # Quick training
    output_dir = "models/gpt2-1m"
    os.makedirs(output_dir, exist_ok=True)

    quick_train(model, tokenizer, output_dir)

    print("\n" + "="*60)
    print("[OK] Model ready for TR118v2 benchmarking!")
    print(f"  Path: {output_dir}")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print("\nNext steps:")
    print(f"  python scripts/tr118/run_tr118v2.py --device cuda --models custom --model-path {output_dir}")
    print("="*60)

