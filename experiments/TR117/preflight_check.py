"""Pre-flight check for TR117 Tier 3 benchmark."""

from pathlib import Path
import sys

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

print("=" * 70)
print("TR117 TIER 3 PRE-FLIGHT CHECK")
print("=" * 70)
print()

errors = []
warnings = []

# Check 1: Python dependencies
print("1. Checking Python dependencies...")
required_packages = [
    "pandas",
    "numpy",
    "scipy",
    "yaml",
    "torch",
    "transformers",
    "psutil",
    "matplotlib",
]

for pkg in required_packages:
    try:
        __import__(pkg)
        print(f"  ✓ {pkg}")
    except ImportError:
        errors.append(f"Missing package: {pkg}")
        print(f"  ✗ {pkg} - MISSING")

# Check 2: Optional packages
print("\n2. Checking optional dependencies...")
optional_packages = {
    "onnxruntime": "ONNXRuntime backend",
    "tensorrt": "TensorRT backend",
    "pynvml": "GPU monitoring",
    "rouge_score": "ROUGE metrics",
    "sentence_transformers": "Semantic similarity",
}

for pkg, desc in optional_packages.items():
    try:
        __import__(pkg)
        print(f"  ✓ {pkg} - {desc}")
    except ImportError:
        warnings.append(f"Optional: {pkg} ({desc})")
        print(f"  ⚠ {pkg} - {desc} (will use fallback)")

# Check 3: Models
print("\n3. Checking models...")
hf_model = Path("models/tiny-gpt2")
if hf_model.exists():
    print(f"  ✓ {hf_model} exists")
else:
    errors.append(f"HuggingFace model missing: {hf_model}")
    print(f"  ✗ {hf_model} - MISSING")

# Check Ollama
try:
    import subprocess

    result = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, timeout=5
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")[1:]  # Skip header
        models = [line.split()[0] for line in lines if line.strip()]

        required_ollama = [
            "gemma3:270m",
            "gemma3:1b-it-qat",
            "gemma3:latest",
            "qwen2.5:7b",
            "llama3.1:8b-instruct-q4_0",
        ]

        for model in required_ollama:
            if model in models:
                print(f"  ✓ {model}")
            else:
                warnings.append(f"Ollama model not found: {model}")
                print(f"  ⚠ {model} - NOT DOWNLOADED")

        print(f"  Total Ollama models available: {len(models)}")
    else:
        errors.append("Ollama not responding")
        print("  ✗ Ollama not responding")
except Exception as e:
    errors.append(f"Ollama check failed: {e}")
    print(f"  ✗ Ollama check failed: {e}")

# Check 4: Configuration file
print("\n4. Checking configuration...")
config_file = Path("scripts/tr117/configs/matrix_tier3_full.yaml")
if config_file.exists():
    print(f"  ✓ {config_file} exists")

    try:
        import yaml

        with open(config_file) as f:
            config = yaml.safe_load(f)

        print(f"  ✓ Repetitions: {config['repetitions']}")
        print(f"  ✓ Scenarios: {len(config['scenarios'])}")
        print(f"  ✓ Models: {len(config['models'])}")
        print(f"  ✓ Backends: {len(config['backends'])}")

        # Calculate expected runs
        total_runs = (
            len(config["scenarios"])
            * len(config["models"])
            * len(config["backends"])
            * config["repetitions"]
            * 2  # prompts per scenario
        )
        print(f"  ✓ Expected total runs: ~{total_runs}")
        print(
            f"  ✓ Estimated time: {total_runs * 2 / 60:.0f}-{total_runs * 10 / 60:.0f} minutes"
        )

    except Exception as e:
        errors.append(f"Config parse error: {e}")
        print(f"  ✗ Config parse failed: {e}")
else:
    errors.append(f"Config file missing: {config_file}")
    print(f"  ✗ {config_file} - MISSING")

# Check 5: Output directory
print("\n5. Checking output directory...")
output_dir = Path("results/tr117_tier3")
output_dir.mkdir(parents=True, exist_ok=True)
if output_dir.exists():
    print(f"  ✓ Output directory ready: {output_dir}")
else:
    errors.append("Cannot create output directory")
    print(f"  ✗ Cannot create {output_dir}")

# Check 6: Harness scripts
print("\n6. Checking harness scripts...")
scripts = [
    "scripts/tr117/run_matrix.py",
    "scripts/tr117/analyze_tr117.py",
    "scripts/tr117/statistical_analysis.py",
    "scripts/tr117/cost_analysis.py",
]

for script in scripts:
    if Path(script).exists():
        print(f"  ✓ {script}")
    else:
        errors.append(f"Script missing: {script}")
        print(f"  ✗ {script} - MISSING")

# Check 7: GPU availability
print("\n7. Checking GPU...")
try:
    import torch

    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print("  ✓ CUDA available")
        print(f"  ✓ Device: {device_name}")
        print(f"  ✓ Memory: {memory_gb:.1f} GB")
    else:
        warnings.append("CUDA not available (CPU-only mode)")
        print("  ⚠ CUDA not available - will run CPU-only")
except Exception as e:
    warnings.append(f"GPU check failed: {e}")
    print(f"  ⚠ GPU check failed: {e}")

# Check 8: Disk space
print("\n8. Checking disk space...")
try:
    import shutil

    stat = shutil.disk_usage(".")
    free_gb = stat.free / (1024**3)
    if free_gb > 10:
        print(f"  ✓ Free disk space: {free_gb:.1f} GB")
    else:
        warnings.append(f"Low disk space: {free_gb:.1f} GB")
        print(f"  ⚠ Low disk space: {free_gb:.1f} GB (recommend >10GB)")
except Exception as e:
    warnings.append(f"Disk check failed: {e}")
    print(f"  ⚠ Disk check failed: {e}")

# Check 9: Environment variables
print("\n9. Checking environment...")
import os

env_vars = {
    "PYTHONPATH": os.getenv("PYTHONPATH"),
    "BANTER_TRANSFORMER_MODEL": os.getenv(
        "BANTER_TRANSFORMER_MODEL", "models/tiny-gpt2"
    ),
    "HF_HUB_OFFLINE": os.getenv("HF_HUB_OFFLINE", "1"),
}

for var, value in env_vars.items():
    if value:
        print(f"  ✓ {var}={value}")
    else:
        print(f"  ℹ {var} not set (will use defaults)")

# Final summary
print("\n" + "=" * 70)
if errors:
    print("❌ PRE-FLIGHT FAILED")
    print("=" * 70)
    print("\nCritical errors:")
    for error in errors:
        print(f"  ✗ {error}")
    print("\nFix these errors before running benchmark.")
    sys.exit(1)
else:
    print("✅ PRE-FLIGHT PASSED")
    print("=" * 70)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print("\nThese won't block the run but may limit functionality.")

    print("\n🚀 READY TO LAUNCH TIER 3 BENCHMARK")
    print("\nRun command:")
    print("  python scripts/tr117/run_matrix.py \\")
    print("    --config scripts/tr117/configs/matrix_tier3_full.yaml \\")
    print("    --output-root results/tr117_tier3/runs")
    print()
