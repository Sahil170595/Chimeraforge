# TR139: Multi-Turn Jailbreak Susceptibility Under Quantization

## Research Question

Does quantization make models more susceptible to multi-turn conversational jailbreaks? Do quantized models "give in" faster across turns?

## Background

Multi-turn jailbreaks (Foot-in-the-Door EMNLP 2025, Crescendo 98% ASR on GPT-4, Attention Shifting AAAI 2025) are the most effective attack class against aligned LLMs. Separately, quantization is known to degrade single-turn safety (HarmLevelBench 2024, Q-resafe ICML 2025, TR134-137). **Nobody has combined these two axes.** All multi-turn papers test full-precision or closed-weight models. All quant-safety papers use single-turn attacks.

If quantization makes multi-turn attacks more effective — or makes models comply at earlier turns — every quantized deployment has an unmeasured compound safety deficit.

## Hypotheses

- **H1:** Multi-turn ASR is independent of quantization level (quant affects single-turn and multi-turn equally)
- **H2:** Quantization amplifies multi-turn attack effectiveness (lower quant = higher ASR or earlier compliance)
- **H3:** Refusal persistence (number of turns before compliance) decreases with quantization

## Scope

### Phase 1: Multi-Turn Attack Effectiveness x Quantization
- 3 models x 6 quant levels x 4 attack strategies x 30 behaviors = 2,160 conversations
- Attack strategies: direct (1 turn), foot-in-door (5 turns), crescendo (5 turns), attention shift (5 turns)
- Measure ASR, turn-of-first-compliance, per-turn safety trajectory

### Phase 2: Refusal Persistence Under Pressure
- 3 models x 3 quant levels x 30 behaviors x 5 pressure turns = 270 conversations
- After direct refusal, apply 5 follow-up pressure turns
- Measure persistence: how many pressure turns before compliance?

**Total: ~2,430 conversations, ~14,000 inference calls**

## Key Deliverables

1. ASR by attack strategy x quant level (main result matrix)
2. Turn-of-first-compliance curves per quant level
3. ASR slope vs BPW per attack strategy
4. Refusal persistence score vs quant level
5. Per-behavior-category vulnerability breakdown
6. Cross-strategy correlation (do same behaviors fail across strategies?)
7. Critical quant threshold for multi-turn safety degradation

## Dependencies

- TR134: Safety classifiers (RefusalDetector), LLM judge
- TR125: find_latest_run utility
- Ollama with GPU access

## Prior Art

- Foot-in-the-Door (EMNLP 2025): multi-turn escalation, full-precision only
- Crescendo (Microsoft, 2024): 98% ASR on GPT-4, closed-weight only
- Attention Shifting (AAAI 2025): context distraction, full-precision only
- Multi-Turn Jailbreaks Simpler Than They Seem (May 2025): strategy analysis
- HarmLevelBench (Nov 2024): quant x safety, single-turn only
- Q-resafe (ICML 2025): quant x safety, single-turn only
- **Multi-turn x quantization intersection: zero prior art**

## Run

```bash
python research/tr139/run.py -v
python research/tr139/run.py -v --phases 1      # Phase 1 only
python research/tr139/run.py -v --skip-prep      # Skip benchmark prep
```

## Folder Structure

```
research/tr139/
├── README.md
├── config.yaml
├── shared/
│   ├── __init__.py
│   └── utils.py
├── tasks/
│   └── multi_turn_behaviors.yaml
├── prepare_benchmarks.py
├── run.py
├── judge_analysis.py
├── analyze.py
└── generate_report.py
```
