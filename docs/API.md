# API Documentation

## Overview

This document provides API documentation for the Chimeraforge benchmarking framework.

## Python API

### Agent Base Classes

#### `BaseAgent`

Base class for all agents.

```python
from banterhearts.demo_agent.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    async def generate(self, prompt: str) -> str:
        """Generate response from prompt."""
        ...
```

**Methods**:
- `async generate(prompt: str) -> str`: Generate response
- `async ingest_benchmarks() -> List[BenchmarkData]`: Load benchmark data

#### `ChimeraAgent`

Optimized agent using Chimera configuration.

```python
from banterhearts.demo_agent.agents.chimera_agent import ChimeraAgent

agent = ChimeraAgent(
    model="gemma3:latest",
    overrides={"num_gpu": 80, "num_ctx": 512}
)
```

**Parameters**:
- `model: str`: Model name
- `overrides: Dict[str, Any]`: Configuration overrides
- `base_url: str`: Ollama base URL

#### `BaselineAgent`

Baseline agent without optimization.

```python
from banterhearts.demo_agent.agents.baseline_agent import BaselineAgent

agent = BaselineAgent(model="gemma3:latest")
```

### Benchmarking

#### `BenchmarkManager`

Manages benchmark execution and data collection.

```python
from banterhearts.benchmarking.benchmark_manager import BenchmarkManager

manager = BenchmarkManager(repo_root=Path("."))
metrics = manager.get_recent_metrics(hours=1)
```

**Methods**:
- `get_recent_metrics(hours: int) -> List[Dict]`: Get recent metrics
- `get_historical_metrics(days: int) -> List[Dict]`: Get historical metrics

### Metrics Collection

#### `MetricsCollector`

Collects performance metrics during execution.

```python
from banterhearts.demo_agent.metrics.collector import MetricsCollector

collector = MetricsCollector(model="gemma3:latest")
# Metrics collected automatically during agent execution
```

### Configuration

#### `ChimeraConfig`

Chimera optimization configuration.

```python
from banterhearts.demo_agent.config.chimera_config import ChimeraConfig

config = ChimeraConfig(
    num_gpu=80,
    num_ctx=512,
    temperature=0.8
)
```

**Parameters**:
- `num_gpu: int`: GPU layers to offload
- `num_ctx: int`: Context window size
- `temperature: float`: Sampling temperature
- `top_p: float`: Top-p sampling
- `top_k: int`: Top-k sampling
- `repeat_penalty: float`: Repeat penalty

## Rust API

### Agent Traits

#### `Agent`

Trait for agent implementations.

```rust
use demo_rust_agent::Agent;

struct MyAgent;

impl Agent for MyAgent {
    async fn generate(&self, prompt: &str) -> Result<String> {
        // Implementation
    }
}
```

### Benchmarking

#### `BenchmarkRunner`

Runs benchmarks and collects metrics.

```rust
use demo_rust_agent::BenchmarkRunner;

let runner = BenchmarkRunner::new();
let results = runner.run_benchmark(agent, runs).await?;
```

### Metrics

#### `Metrics`

Performance metrics structure.

```rust
use demo_rust_agent::Metrics;

let metrics = Metrics {
    throughput: 100.0,
    ttft: 450.0,
    latency: 500.0,
    // ...
};
```

## Command Line Interface

### Python Agents

#### Single-Agent

```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

#### Multi-Agent

```bash
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048
```

### Rust Agents

#### Single-Agent

```bash
cd src/rust/demo_agent
cargo run --release -- \
  --model gemma3:latest \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

#### Multi-Agent

```bash
cd src/rust/demo_multiagent
cargo run --release -- \
  --scenario chimera_homo \
  --runs 5 \
  --collector-ollama-url http://localhost:11434 \
  --insight-ollama-url http://localhost:11435
```

## Data Structures

### BenchmarkData

```python
@dataclass
class BenchmarkData:
    source_file: str
    data_type: str
    content: str
    metadata: Dict[str, Any]
```

### Metrics

```python
@dataclass
class Metrics:
    throughput: float  # tokens/second
    ttft: float        # milliseconds
    latency: float     # milliseconds
    memory_usage: float
    cpu_usage: float
```

### BenchmarkResults

```python
@dataclass
class BenchmarkResults:
    runs: List[Metrics]
    mean: Metrics
    stddev: Metrics
    cv: Metrics  # Coefficient of variation
```

## Error Handling

### Python

```python
try:
    result = await agent.generate(prompt)
except AgentError as e:
    # Handle agent-specific errors
except OllamaError as e:
    # Handle Ollama connection errors
```

### Rust

```rust
match agent.generate(prompt).await {
    Ok(result) => println!("{}", result),
    Err(AgentError::OllamaError(e)) => eprintln!("Ollama error: {}", e),
    Err(e) => eprintln!("Error: {}", e),
}
```

## Examples

### Custom Agent

```python
from banterhearts.demo_agent.agents.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self, model: str):
        super().__init__(model, {}, "http://localhost:11434")
    
    async def generate(self, prompt: str) -> str:
        # Custom implementation
        response = await self._call_ollama(prompt)
        return response
```

### Custom Metrics

```python
from banterhearts.demo_agent.metrics.collector import MetricsCollector

class CustomMetricsCollector(MetricsCollector):
    def collect_custom_metric(self, value: float):
        self.metrics["custom_metric"] = value
```

---

**Last Updated**: January 2025

