#!/usr/bin/env python3
"""Check parameter counts of built models."""

from transformers import GPT2LMHeadModel

models = ['gpt2-5m', 'gpt2-25m', 'gpt2-50m']
for m in models:
    try:
        model = GPT2LMHeadModel.from_pretrained(f"models/{m}")
        params = sum(p.numel() for p in model.parameters())
        print(f"{m}: {params/1e6:.3f}M params")
    except Exception as e:
        print(f"{m}: ERROR - {e}")


