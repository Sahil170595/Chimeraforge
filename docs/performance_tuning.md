# Performance Tuning Guide

Advanced optimization techniques for maximizing LLM performance.

## Overview

This guide covers advanced performance tuning techniques beyond basic Chimera optimization, including system-level optimizations, hardware tuning, and production deployment strategies.

## System-Level Optimizations

### GPU Optimization

#### CUDA Memory Management

```python
# Set memory allocation strategy
import os
os.environ["TORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

# Pre-allocate memory
import torch
torch.cuda.empty_cache()
torch.cuda.set_per_process_memory_fraction(0.9)
```

#### GPU Power Limits

```bash
# Set persistent power limit (Linux)
sudo nvidia-smi -pl 175  # Watts

# Check current limit
nvidia-smi -q -d POWER
```

#### GPU Clock Speeds

```bash
# Set performance mode (Linux)
sudo nvidia-smi -pm 1  # Enable persistence mode
sudo nvidia-smi -ac <memory_clock>,<graphics_clock>
```

### CPU Optimization

#### CPU Affinity

```python
import os
# Pin to specific CPU cores
os.sched_setaffinity(0, {0, 1, 2, 3})  # Use cores 0-3
```

#### CPU Governor

```bash
# Set performance governor (Linux)
sudo cpupower frequency-set -g performance

# Check current governor
cpupower frequency-info
```

### Memory Optimization

#### Huge Pages

```bash
# Enable huge pages (Linux)
echo 1024 | sudo tee /proc/sys/vm/nr_hugepages

# Verify
cat /proc/meminfo | grep Huge
```

#### Memory Preallocation

```python
# Pre-allocate memory
import torch
torch.cuda.empty_cache()
torch.cuda.set_per_process_memory_fraction(0.9)
```

## Application-Level Optimizations

### Batch Processing

```python
# Process multiple prompts in batch
async def batch_process(prompts: List[str], batch_size: int = 4):
    for i in range(0, len(prompts), batch_size):
        batch = prompts[i:i+batch_size]
        results = await asyncio.gather(*[agent.run(p) for p in batch])
        yield results
```

### Connection Pooling

```python
# Reuse HTTP connections
import httpx

async with httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=10)
) as client:
    # Reuse client for multiple requests
    pass
```

### Streaming Optimization

```python
# Stream responses for better latency
async def stream_response(prompt: str):
    async with client.stream("POST", url, json=data) as response:
        async for chunk in response.aiter_text():
            yield chunk
```

## Configuration Tuning

### Adaptive Configuration

```python
# Adjust configuration based on workload
def get_optimal_config(prompt_length: int, vram_available: int):
    if prompt_length < 100:
        return {"num_ctx": 512, "num_gpu": 80}
    elif prompt_length < 500:
        return {"num_ctx": 1024, "num_gpu": 80}
    else:
        return {"num_ctx": 2048, "num_gpu": 60}
```

### Dynamic GPU Allocation

```python
# Allocate GPU layers based on available VRAM
def calculate_gpu_layers(vram_available: int, model_size: int):
    max_layers = (vram_available * 1024) // (model_size * 4)
    return min(max_layers, 120)  # Cap at 120
```

## Production Optimizations

### Load Balancing

```python
# Distribute load across multiple Ollama instances
class LoadBalancer:
    def __init__(self, instances: List[str]):
        self.instances = instances
        self.current = 0
    
    def get_instance(self) -> str:
        instance = self.instances[self.current]
        self.current = (self.current + 1) % len(self.instances)
        return instance
```

### Caching

```python
# Cache frequent requests
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_generate(prompt: str, config_hash: str) -> str:
    return agent.run(prompt)
```

### Request Queuing

```python
# Queue requests for better throughput
import asyncio
from collections import deque

class RequestQueue:
    def __init__(self, max_concurrent: int = 4):
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process(self, prompt: str):
        async with self.semaphore:
            return await agent.run(prompt)
```

## Profiling

### Python Profiling

```python
# Profile code execution
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# Your code here
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

### GPU Profiling

```bash
# Profile GPU usage
nsys profile --trace=cuda,nvtx python script.py

# Analyze profile
nsys-ui profile.qdrep
```

### Memory Profiling

```python
# Profile memory usage
from memory_profiler import profile

@profile
def my_function():
    # Your code here
    pass
```

## Monitoring

### Real-Time Metrics

```python
# Monitor performance in real-time
import time
from collections import deque

class PerformanceMonitor:
    def __init__(self, window_size: int = 100):
        self.throughput_history = deque(maxlen=window_size)
        self.ttft_history = deque(maxlen=window_size)
    
    def record(self, throughput: float, ttft: float):
        self.throughput_history.append(throughput)
        self.ttft_history.append(ttft)
    
    def get_stats(self):
        return {
            "mean_throughput": sum(self.throughput_history) / len(self.throughput_history),
            "mean_ttft": sum(self.ttft_history) / len(self.ttft_history),
        }
```

### Alerting

```python
# Alert on performance degradation
class PerformanceAlert:
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.baseline = None
    
    def check(self, current: float):
        if self.baseline is None:
            self.baseline = current
            return
        
        if current < self.baseline * self.threshold:
            print(f"ALERT: Performance degraded by {(1 - current/self.baseline)*100:.1f}%")
```

## Advanced Techniques

### Model Quantization

```python
# Use quantized models for better performance
# Pull quantized model
# ollama pull gemma3:latest-q4_0

# Use in configuration
model = "gemma3:latest-q4_0"
```

### KV Cache Optimization

```python
# Optimize KV cache size
# Smaller context = smaller KV cache = faster inference
num_ctx = 512  # Optimal for most use cases
```

### Token Batching

```python
# Batch token generation
async def batch_generate(prompts: List[str]):
    # Process multiple prompts concurrently
    results = await asyncio.gather(*[agent.run(p) for p in prompts])
    return results
```

## References

- [Chimera Optimization Guide](chimera_optimization.md)
- [Benchmarking Guide](benchmarking.md)
- [Configuration Reference](configuration.md)
- [TR108: Single-Inference Optimization](../outputs/publish_ready/reports/Technical_Report_108.md)

---

**Last Updated**: November 2025

