# Dual Ollama Setup Guide

Complete guide to setting up dual Ollama instances for concurrent multi-agent execution.

## Overview

Dual Ollama instances enable true concurrent execution of multiple LLM agents by eliminating server-level resource contention. This setup is **mandatory** for production multi-agent deployments.

## Why Dual Ollama?

### Single Instance Problems

- **Sequential Model Loading**: Models load one at a time
- **Resource Contention**: 74% contention rate (Rust)
- **Reduced Efficiency**: 72-82% vs 95-99% with dual
- **Bottleneck**: Server becomes serialization point

### Dual Instance Benefits

- **True Concurrency**: Models load in parallel
- **No Contention**: <6% contention rate
- **High Efficiency**: 95-99% parallel efficiency
- **Production Ready**: Scalable architecture

## Quick Setup

### Windows (Automated)

```powershell
.\scripts\windows\ollama\setup_dual_ollama.ps1
```

This script:
1. Stops existing Ollama instances
2. Starts Ollama on port 11434
3. Starts Ollama on port 11435 (separate window)
4. Verifies both instances are running

### Manual Setup

#### Windows

**Terminal 1**:
```cmd
set OLLAMA_HOST=127.0.0.1:11434
ollama serve
```

**Terminal 2** (New PowerShell window):
```powershell
$env:OLLAMA_HOST="127.0.0.1:11435"
ollama serve
```

#### Linux/macOS

**Terminal 1**:
```bash
OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

**Terminal 2**:
```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

## Configuration Details

### Port Configuration

**Instance 1**:
- Port: 11434 (default)
- Host: 127.0.0.1
- Environment: `OLLAMA_HOST=127.0.0.1:11434`

**Instance 2**:
- Port: 11435 (custom)
- Host: 127.0.0.1
- Environment: `OLLAMA_HOST=127.0.0.1:11435`

### Model Directories (Optional)

By default, both instances share the same model directory (`~/.ollama/models`). For complete isolation:

**Instance 1**:
```bash
OLLAMA_MODELS=/path/to/models1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

**Instance 2**:
```bash
OLLAMA_MODELS=/path/to/models2 OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

**Note**: Separate directories require pulling models twice (one per instance).

## Verification

### Check Both Instances

```bash
# Instance 1
curl http://localhost:11434/api/tags

# Instance 2
curl http://localhost:11435/api/tags
```

### Pull Model on Both Instances

```bash
# Instance 1
OLLAMA_HOST=127.0.0.1:11434 ollama pull gemma3:latest

# Instance 2
OLLAMA_HOST=127.0.0.1:11435 ollama pull gemma3:latest
```

### Test Concurrent Access

```python
import asyncio
import httpx

async def test_concurrent():
    async with httpx.AsyncClient() as client:
        # Concurrent requests to both instances
        results = await asyncio.gather(
            client.get("http://localhost:11434/api/tags"),
            client.get("http://localhost:11435/api/tags")
        )
        print("Both instances responding:", all(r.status_code == 200 for r in results))

asyncio.run(test_concurrent())
```

## Troubleshooting

### Port Already in Use

**Error**: `bind: address already in use`

**Solution**:
```bash
# Find process using port
netstat -ano | findstr :11434  # Windows
lsof -i :11434                  # Linux/macOS

# Kill process
taskkill /PID <pid> /F          # Windows
kill <pid>                      # Linux/macOS
```

### Instance Not Responding

**Check**:
1. Is Ollama running? `ollama list` (default instance)
2. Is port accessible? `curl http://localhost:11434/api/tags`
3. Check firewall settings
4. Verify environment variable is set

**Solution**:
```bash
# Restart instance
# Terminal 1
OLLAMA_HOST=127.0.0.1:11434 ollama serve

# Terminal 2
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

### Model Not Found on Instance 2

**Error**: `model not found` when accessing instance 2

**Solution**:
```bash
# Pull model on instance 2
OLLAMA_HOST=127.0.0.1:11435 ollama pull gemma3:latest
```

### High Memory Usage

**Issue**: Both instances loading models = 2x VRAM usage

**Solution**:
- Use smaller models
- Reduce `num_gpu` layers
- Ensure sufficient VRAM (12GB+ recommended)

## Performance Validation

### Run Multi-Agent Benchmark

**Python**:
```bash
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 3 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0
```

**Rust**:
```bash
cd src/rust/demo_multiagent
cargo run --release -- \
  --scenario chimera_homo \
  --runs 3 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 1.0 \
  --collector-ollama-url http://localhost:11434 \
  --insight-ollama-url http://localhost:11435
```

### Expected Results

**With Dual Ollama**:
- Efficiency: 95-99%
- Speedup: 1.9-2.0x
- Contention: <6%

**Without Dual Ollama** (single instance):
- Efficiency: 72-82%
- Speedup: 1.4-1.6x
- Contention: 74%

## Production Deployment

### Systemd Service (Linux)

**Instance 1** (`/etc/systemd/system/ollama1.service`):
```ini
[Unit]
Description=Ollama Instance 1
After=network.target

[Service]
Type=simple
User=ollama
Environment="OLLAMA_HOST=127.0.0.1:11434"
ExecStart=/usr/local/bin/ollama serve
Restart=always

[Install]
WantedBy=multi-user.target
```

**Instance 2** (`/etc/systemd/system/ollama2.service`):
```ini
[Unit]
Description=Ollama Instance 2
After=network.target

[Service]
Type=simple
User=ollama
Environment="OLLAMA_HOST=127.0.0.1:11435"
ExecStart=/usr/local/bin/ollama serve
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable Services**:
```bash
sudo systemctl enable ollama1 ollama2
sudo systemctl start ollama1 ollama2
```

### Docker Compose

```yaml
version: '3.8'

services:
  ollama1:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
    volumes:
      - ollama1_data:/root/.ollama
    restart: unless-stopped

  ollama2:
    image: ollama/ollama:latest
    ports:
      - "11435:11435"
    environment:
      - OLLAMA_HOST=0.0.0.0:11435
    volumes:
      - ollama2_data:/root/.ollama
    restart: unless-stopped

volumes:
  ollama1_data:
  ollama2_data:
```

**Run**:
```bash
docker-compose up -d
```

## References

- [Multi-Agent Architecture](multi_agent.md)
- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)
- [TR114: Rust Multi-Agent](../outputs/publish_ready/reports/Technical_Report_114.md)
- [Ollama Documentation](https://ollama.ai/docs)

---

**Last Updated**: November 2025

