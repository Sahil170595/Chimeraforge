# Python Agent Development Guide

Complete guide to developing and deploying Python LLM agents using the
Chimeraforge framework (the Banterhearts benchmarking breakout).

## Overview

The Python agent framework provides a production-ready foundation for building LLM-powered agents with comprehensive benchmarking, metrics collection, and optimization capabilities.

## Architecture

### Core Components

```
src/python/banterhearts/demo_agent/
 agents/
    base_agent.py      # Base agent class
    baseline_agent.py  # Baseline (Ollama defaults)
    chimera_agent.py   # Chimera-optimized agent
 config/
    baseline_config.py # Baseline configuration
    chimera_config.py  # Chimera configuration
 metrics/
    collector.py       # Metrics collection
 run_demo.py            # Main orchestrator
```

### Agent Base Class

```python
from banterhearts.demo_agent.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    """Custom agent implementation."""
    
    async def run(self, prompt: str) -> str:
        """Execute agent task."""
        # Your implementation
        response = await self._call_ollama(prompt)
        return response
```

## Quick Start

### Basic Agent

```python
from banterhearts.demo_agent.agents.baseline_agent import BaselineAgent

async def main():
    agent = BaselineAgent(model="gemma3:latest")
    result = await agent.run("Generate a technical report")
    print(result)

asyncio.run(main())
```

### Chimera-Optimized Agent

```python
from banterhearts.demo_agent.agents.chimera_agent import ChimeraAgent

async def main():
    agent = ChimeraAgent(
        model="gemma3:latest",
        num_gpu=80,
        num_ctx=512,
        temperature=0.8
    )
    result = await agent.run("Generate a technical report")
    print(result)

asyncio.run(main())
```

## Running Benchmarks

### Single Run

```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 1 \
  --output-dir my_results
```

### Multiple Runs (Statistical Significance)

```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 5 \
  --output-dir my_results \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

### Parameter Sweep

```python
# run_sweep.py
import asyncio
from banterhearts.demo_agent.run_demo import ChimeraDemoOrchestrator

async def sweep():
    configs = [
        {"num_gpu": 60, "num_ctx": 512, "temperature": 0.8},
        {"num_gpu": 80, "num_ctx": 512, "temperature": 0.8},
        {"num_gpu": 100, "num_ctx": 512, "temperature": 0.8},
    ]
    
    for config in configs:
        orchestrator = ChimeraDemoOrchestrator(
            model="gemma3:latest",
            output_dir=f"results/gpu{config['num_gpu']}",
            runs=5,
            chimera_overrides=config
        )
        await orchestrator.run()

asyncio.run(sweep())
```

## Configuration

### Baseline Configuration

```python
from banterhearts.demo_agent.config.baseline_config import BaselineConfig

config = BaselineConfig(
    model="gemma3:latest",
    timeout=30.0,
    max_tokens=1000
)
```

### Chimera Configuration

```python
from banterhearts.demo_agent.config.chimera_config import ChimeraConfig

config = ChimeraConfig(
    model="gemma3:latest",
    num_gpu=80,
    num_ctx=512,
    temperature=0.8,
    top_p=0.9,
    top_k=40,
    repeat_penalty=1.1
)
```

## Metrics Collection

### Automatic Collection

The framework automatically collects:
- Throughput (tokens/second)
- Time to First Token (TTFT)
- Prompt evaluation duration
- Generation evaluation duration
- Model load duration
- Memory usage
- CPU usage

### Custom Metrics

```python
from banterhearts.demo_agent.metrics.collector import MetricsCollector

collector = MetricsCollector()

async def my_agent():
    start = time.time()
    result = await agent.run(prompt)
    duration = time.time() - start
    
    collector.record_metric("custom_duration", duration)
    collector.save_metrics("metrics.json")
```

## Best Practices

### 1. Use Async/Await

```python
# Good
async def run_agent():
    result = await agent.run(prompt)
    return result

# Bad
def run_agent():
    result = asyncio.run(agent.run(prompt))
    return result
```

### 2. Handle Errors Gracefully

```python
try:
    result = await agent.run(prompt)
except OllamaError as e:
    logger.error(f"Ollama error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### 3. Use Configuration Objects

```python
# Good
config = ChimeraConfig(num_gpu=80, num_ctx=512)
agent = ChimeraAgent(config=config)

# Bad
agent = ChimeraAgent(num_gpu=80, num_ctx=512, ...)
```

### 4. Collect Metrics

```python
# Good
collector = MetricsCollector()
await collector.collect_metrics(agent, prompt)

# Bad
result = await agent.run(prompt)  # No metrics
```

### 5. Use Type Hints

```python
# Good
async def run_agent(prompt: str) -> str:
    return await agent.run(prompt)

# Bad
async def run_agent(prompt):
    return await agent.run(prompt)
```

## Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### Check Ollama Connection

```python
import httpx

async def check_ollama():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:11434/api/tags")
        print(response.json())
```

### Monitor GPU Usage

```bash
watch -n 1 nvidia-smi
```

## Examples

### Example 1: Simple Agent

```python
import asyncio
from banterhearts.demo_agent.agents.baseline_agent import BaselineAgent

async def main():
    agent = BaselineAgent(model="gemma3:latest")
    result = await agent.run("Hello, world!")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Optimized Agent

```python
import asyncio
from banterhearts.demo_agent.agents.chimera_agent import ChimeraAgent

async def main():
    agent = ChimeraAgent(
        model="gemma3:latest",
        num_gpu=80,
        num_ctx=512,
        temperature=0.8
    )
    result = await agent.run("Generate a technical report")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 3: Custom Agent

```python
import asyncio
from banterhearts.demo_agent.agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    async def run(self, prompt: str) -> str:
        # Custom preprocessing
        processed_prompt = self.preprocess(prompt)
        
        # Call Ollama
        response = await self._call_ollama(processed_prompt)
        
        # Custom postprocessing
        result = self.postprocess(response)
        
        return result
    
    def preprocess(self, prompt: str) -> str:
        return f"System: You are a helpful assistant.\nUser: {prompt}"
    
    def postprocess(self, response: str) -> str:
        return response.strip()

async def main():
    agent = MyCustomAgent(model="gemma3:latest")
    result = await agent.run("Hello!")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Production Deployment

### Environment Variables

```bash
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODELS=~/.ollama/models
export LOG_LEVEL=INFO
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY banterhearts/ ./banterhearts/
COPY scripts/ ./scripts/

CMD ["python", "-m", "banterhearts.demo_agent.run_demo"]
```

### Systemd Service

```ini
[Unit]
Description=Chimeraforge Python Agent
After=network.target

[Service]
Type=simple
User=banterhearts
WorkingDirectory=/opt/banterhearts
ExecStart=/usr/bin/python3 -m banterhearts.demo_agent.run_demo
Restart=always

[Install]
WantedBy=multi-user.target
```

## References

- [Chimera Optimization Guide](chimera_optimization.md)
- [Benchmarking Guide](benchmarking.md)
- [TR109: Python Agent Workflows](../outputs/publish_ready/reports/Technical_Report_109.md)
- [TR110: Python Multi-Agent](../outputs/publish_ready/reports/Technical_Report_110.md)

---

**Last Updated**: November 2025

