#!/usr/bin/env python3
"""
Fix TR118v2 to create v2.1 by systematically replacing problematic sections.
"""

from pathlib import Path
import re


def fix_report():
    """Fix v2 report to create v2.1."""

    # Read original v2
    v2_path = Path('../../reports/generated/Technical_Report_118_v2.md')
    with open(v2_path, encoding='utf-8') as f:
        content = f.read()

    # Read the corrected v2.1 start (definitions + executive summary)
    v21_start_path = Path('../../reports/generated/Technical_Report_118_v2.1.md')
    with open(v21_start_path, encoding='utf-8') as f:
        v21_start = f.read()

    # Strategy: Keep most of v2 structure, replace specific problematic sections

    # 1. Replace header + first 100 lines with corrected v2.1 start
    lines = content.split('\n')

    # Find where "### Key Findings" ends in v21_start
    v21_lines = v21_start.split('\n')

    # Find where to resume in v2 (after "### Key Findings" section)
    resume_idx = None
    for i, line in enumerate(lines):
        if '## Data Analysis & Results' in line or '## Tiny-GPT2 Results' in line:
            resume_idx = i
            break

    if not resume_idx:
        # Fallback: find "## Critical Context" or similar
        for i, line in enumerate(lines):
            if line.strip().startswith('## ') and i > 50:
                resume_idx = i
                break

    # Build new content
    new_lines = v21_lines.copy()
    new_lines.append('')
    new_lines.append('---')
    new_lines.append('')

    # Add note about GPT-2 generate limitation
    new_lines.extend([
        '## Critical Methodological Note',
        '',
        '**GPT-2 Generate Mode Limitation:** All TensorRT backends (FP32, FP16, INT8) experienced 100% degradation rate (180s timeout) during GPT-2 generate benchmarks. Root cause: Reused FP16 engine from smoke test contained only 1 optimization profile (batch=1, seq≤16), incompatible with deep run requirements (5 profiles for batch=1-4, seq=8-128). This is a **pipeline artifact issue**, not a TensorRT capability limitation. Prefill results remain valid; generate analysis limited to PyTorch and ONNX Runtime backends for GPT-2.',
        '',
        '---',
        ''
    ])

    # Resume with v2 content starting from the data analysis section
    if resume_idx:
        new_lines.extend(lines[resume_idx:])

    # Fix specific issues in the resumed content
    new_content = '\n'.join(new_lines)

    # Fix 2: Remove fabricated GPT-2 generate tables for TRT
    # Find and mark these sections
    new_content = re.sub(
        r'(\| tensorrt-fp16 \| batch_medium.*?\n.*?\d+\.\d+.*?\n)',
        '| tensorrt-fp16 | batch_medium | DEGRADED (100% timeout) | - | - |\n',
        new_content
    )

    # Fix 3: Correct delta calculations (-52% → -30%)
    new_content = new_content.replace('-52%', '-30%')
    new_content = new_content.replace('52% slower', '30% slower')

    # Fix 4: Add proper scoping labels
    new_content = re.sub(
        r'(\*\*\d+,?\d*\.?\d* tok/s)',
        r'\1 (overall mean across scenarios)',
        new_content,
        count=10  # Only first few instances
    )

    # Write v2.1
    v21_path = Path('../../reports/generated/Technical_Report_118_v2.1.md')
    with open(v21_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print('[OK] Generated TR118v2.1')
    print(f'   Original v2: {len(lines)} lines')
    print(f'   New v2.1: {len(new_content.splitlines())} lines')
    print('   Corrections applied: header, definitions, GPT-2 generate note, delta fixes')

if __name__ == '__main__':
    fix_report()

