# Installation Guide

Complete installation instructions for Chimeraforge, the benchmarking-only
breakout from Banterhearts.

## Prerequisites

### Required Software

- **Python 3.11+** (for Python agents)
- **Rust 1.70+** (for Rust agents, optional)
- **Ollama** (model serving)
- **NVIDIA GPU** (12GB+ VRAM recommended)
- **CUDA 11.8+** (for GPU acceleration)
- **Git** (for cloning repository)

### System Requirements

- **OS**: Windows 10+, Linux, macOS
- **RAM**: 16GB+ recommended
- **VRAM**: 12GB+ (RTX 4080 or better)
- **Storage**: 10GB+ free space

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/your-org/Chimeraforge.git
cd Chimeraforge
```

### 2. Python Setup

#### Create Virtual Environment

**Windows**:
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS**:
```bash
python -m venv venv
source venv/bin/activate
```

#### Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Rust Setup (Optional)

#### Install Rust

```bash
# Install Rust via rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Or download from https://rustup.rs/
```

#### Build Rust Agents

```bash
# Single-agent
cd src/rust/demo_agent
cargo build --release

# Multi-agent
cd ../Demo_rust_multiagent
cargo build --release
```

### 4. Ollama Setup

#### Install Ollama

**Windows**:
- Download from https://ollama.ai/download
- Run installer

**Linux**:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**macOS**:
```bash
brew install ollama
```

#### Start Ollama

```bash
ollama serve
```

#### Pull Model

```bash
ollama pull gemma3:latest
```

### 5. Verify Installation

```bash
# Check Python
python --version  # Should be 3.11+

# Check Rust (if installed)
rustc --version  # Should be 1.70+

# Check Ollama
ollama list  # Should show gemma3:latest

# Test Python agent
python src/python/banterhearts/demo_agent/run_demo.py --runs 1

# Test Rust agent (if installed)
cd src/rust/demo_agent
cargo run --release -- --runs 1
```

## Configuration

### Environment Variables

Create `.env` file (optional):

```bash
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODELS=~/.ollama/models

# GPU
CUDA_VISIBLE_DEVICES=0
TORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

# Logging
LOG_LEVEL=INFO
RUST_LOG=info
```

### Dual Ollama Setup (Multi-Agent)

For multi-agent benchmarks, you need two Ollama instances:

**Windows**:
```powershell
.\scripts\windows\ollama\setup_dual_ollama.ps1
```

**Manual Setup**:
```bash
# Terminal 1
OLLAMA_HOST=127.0.0.1:11434 ollama serve

# Terminal 2
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

## Troubleshooting

### Python Issues

**Import Errors**:
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Virtual Environment Not Activating**:
```bash
# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### Rust Issues

**Build Errors**:
```bash
# Update Rust
rustup update

# Clean and rebuild
cargo clean
cargo build --release
```

**Missing Dependencies**:
```bash
# Install system dependencies (Linux)
sudo apt-get install build-essential pkg-config libssl-dev
```

### Ollama Issues

**Ollama Not Starting**:
```bash
# Check if port is in use
netstat -an | grep 11434

# Kill existing process
pkill ollama  # Linux/macOS
taskkill /F /IM ollama.exe  # Windows
```

**Model Not Found**:
```bash
# List available models
ollama list

# Pull model
ollama pull gemma3:latest
```

**GPU Not Detected**:
```bash
# Check CUDA
nvidia-smi

# Verify Ollama GPU support
ollama run gemma3:latest "test"  # Should use GPU
```

## Next Steps

- [Quick Start Guide](quick_start.md)
- [Benchmarking Guide](benchmarking.md)
- [Configuration Reference](configuration.md)

---

**Installation complete?** Proceed to [Quick Start Guide](quick_start.md).

