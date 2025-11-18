# Rust Agent Development Guide

Complete guide to developing and deploying Rust LLM agents using the
Chimeraforge framework (the Banterhearts benchmarking breakout).

## Overview

The Rust agent framework provides a production-ready, memory-safe foundation for building high-performance LLM agents with comprehensive benchmarking and optimization capabilities.

## Architecture

### Core Components

```
Demo_rust_agent/
 src/
    main.rs          # Main agent implementation
 Cargo.toml           # Dependencies
 README.md            # Project documentation
```

### Key Dependencies

```toml
[dependencies]
tokio = { version = "1.0", features = ["full"] }
reqwest = { version = "0.11", features = ["json", "stream"] }
serde = { version = "1.0", features = ["derive"] }
clap = { version = "4.0", features = ["derive"] }
anyhow = "1.0"
tracing = "0.1"
```

## Quick Start

### Basic Agent

```rust
use anyhow::Result;

#[tokio::main]
async fn main() -> Result<()> {
    let agent = Agent::new("gemma3:latest", "http://localhost:11434").await?;
    let result = agent.run("Generate a technical report").await?;
    println!("{}", result);
    Ok(())
}
```

### Chimera-Optimized Agent

```rust
use anyhow::Result;

#[tokio::main]
async fn main() -> Result<()> {
    let options = OllamaOptions {
        num_gpu: Some(80),
        num_ctx: Some(512),
        temperature: Some(0.8),
        ..Default::default()
    };
    
    let agent = Agent::with_options(
        "gemma3:latest",
        "http://localhost:11434",
        options
    ).await?;
    
    let result = agent.run("Generate a technical report").await?;
    println!("{}", result);
    Ok(())
}
```

## Running Benchmarks

### Single Run

```bash
cd src/rust/demo_agent
cargo run --release -- \
  --model gemma3:latest \
  --runs 1 \
  --output-dir my_results
```

### Multiple Runs (Statistical Significance)

```bash
cargo run --release -- \
  --model gemma3:latest \
  --runs 5 \
  --output-dir my_results \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

### Parameter Sweep

```bash
# Use Python orchestration script
python run_rust_benchmark_sweep.py
```

## Configuration

### Command-Line Arguments

```rust
#[derive(Parser, Debug)]
struct Args {
    #[arg(long, default_value = "gemma3:latest")]
    model: String,
    
    #[arg(long, default_value = "http://localhost:11434")]
    base_url: String,
    
    #[arg(long, default_value_t = 3)]
    runs: u32,
    
    #[arg(long)]
    chimera_num_gpu: Option<u32>,
    #[arg(long)]
    chimera_num_ctx: Option<u32>,
    #[arg(long)]
    chimera_temperature: Option<f32>,
}
```

### Ollama Options

```rust
#[derive(Debug, Serialize, Deserialize, Default)]
struct OllamaOptions {
    num_gpu: Option<u32>,
    num_ctx: Option<u32>,
    temperature: Option<f32>,
    top_p: Option<f32>,
    top_k: Option<u32>,
    repeat_penalty: Option<f32>,
}
```

## Metrics Collection

### Automatic Collection

The framework automatically collects:
- Throughput (tokens/second)
- Time to First Token (TTFT)
- Prompt evaluation duration
- Generation evaluation duration
- Model load duration
- System information

### Metrics Structure

```rust
#[derive(Debug, Serialize, Deserialize)]
struct Metrics {
    throughput_tok_s: f64,
    ttft_ms: f64,
    prompt_eval_duration_ms: f64,
    eval_duration_ms: f64,
    load_duration_ms: f64,
    tokens_generated: u32,
}
```

### Saving Metrics

```rust
let metrics = Metrics { /* ... */ };
let json = serde_json::to_string_pretty(&metrics)?;
fs::write("metrics.json", json).await?;
```

## Best Practices

### 1. Use Async/Await

```rust
//  Good
async fn run_agent() -> Result<String> {
    let result = agent.run(prompt).await?;
    Ok(result)
}

//  Bad
fn run_agent() -> Result<String> {
    let rt = Runtime::new()?;
    rt.block_on(agent.run(prompt))
}
```

### 2. Handle Errors Properly

```rust
//  Good
match agent.run(prompt).await {
    Ok(result) => println!("{}", result),
    Err(e) => eprintln!("Error: {}", e),
}

//  Bad
let result = agent.run(prompt).await.unwrap();
```

### 3. Use Result Types

```rust
//  Good
async fn run_agent() -> Result<String> {
    // ...
}

//  Bad
async fn run_agent() -> String {
    // ...
}
```

### 4. Use Streaming for Large Responses

```rust
//  Good
let mut stream = client
    .post(&generate_url)
    .json(&request)
    .send()
    .await?
    .bytes_stream();

while let Some(chunk) = stream.next().await {
    // Process chunk
}

//  Bad
let response = client.post(&generate_url).send().await?;
let full_text = response.text().await?;  // Loads everything into memory
```

### 5. Use Type Safety

```rust
//  Good
struct Agent {
    model: String,
    base_url: String,
    client: Client,
}

//  Bad
struct Agent {
    model: String,
    base_url: String,
    client: Box<dyn Any>,
}
```

## Debugging

### Enable Tracing

```rust
use tracing::{info, Level};

tracing_subscriber::fmt()
    .with_max_level(Level::DEBUG)
    .init();

info!("Starting agent");
```

### Check Ollama Connection

```rust
async fn check_ollama(base_url: &str) -> Result<()> {
    let client = Client::new();
    let response = client
        .get(&format!("{}/api/tags", base_url))
        .send()
        .await?;
    
    println!("Status: {}", response.status());
    Ok(())
}
```

### Monitor GPU Usage

```bash
watch -n 1 nvidia-smi
```

## Examples

### Example 1: Simple Agent

```rust
use anyhow::Result;
use reqwest::Client;

#[tokio::main]
async fn main() -> Result<()> {
    let client = Client::new();
    let response = client
        .post("http://localhost:11434/api/generate")
        .json(&serde_json::json!({
            "model": "gemma3:latest",
            "prompt": "Hello, world!",
            "stream": false
        }))
        .send()
        .await?;
    
    let result: serde_json::Value = response.json().await?;
    println!("{}", result["response"]);
    Ok(())
}
```

### Example 2: Streaming Agent

```rust
use futures_util::StreamExt;
use reqwest::Client;

async fn stream_agent(prompt: &str) -> Result<()> {
    let client = Client::new();
    let mut stream = client
        .post("http://localhost:11434/api/generate")
        .json(&serde_json::json!({
            "model": "gemma3:latest",
            "prompt": prompt,
            "stream": true
        }))
        .send()
        .await?
        .bytes_stream();
    
    while let Some(chunk) = stream.next().await {
        let chunk = chunk?;
        let text = String::from_utf8_lossy(&chunk);
        print!("{}", text);
    }
    
    Ok(())
}
```

### Example 3: Custom Agent

```rust
use anyhow::Result;

struct MyAgent {
    model: String,
    client: Client,
}

impl MyAgent {
    fn new(model: String) -> Self {
        Self {
            model,
            client: Client::new(),
        }
    }
    
    async fn run(&self, prompt: &str) -> Result<String> {
        // Preprocess
        let processed = self.preprocess(prompt);
        
        // Call Ollama
        let response = self.call_ollama(&processed).await?;
        
        // Postprocess
        let result = self.postprocess(response);
        
        Ok(result)
    }
    
    fn preprocess(&self, prompt: &str) -> String {
        format!("System: You are a helpful assistant.\nUser: {}", prompt)
    }
    
    fn postprocess(&self, response: String) -> String {
        response.trim().to_string()
    }
    
    async fn call_ollama(&self, prompt: &str) -> Result<String> {
        // Implementation
        Ok(String::new())
    }
}
```

## Production Deployment

### Build Release Binary

```bash
cargo build --release
```

### Environment Variables

```bash
export OLLAMA_HOST=http://localhost:11434
export RUST_LOG=info
```

### Docker Deployment

```dockerfile
FROM rust:1.70 as builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/demo_rust_agent /usr/local/bin/
CMD ["demo_rust_agent"]
```

### Systemd Service

```ini
[Unit]
Description=Chimeraforge Rust Agent
After=network.target

[Service]
Type=simple
User=banterhearts
WorkingDirectory=/opt/banterhearts
ExecStart=/usr/local/bin/demo_rust_agent
Restart=always
Environment="RUST_LOG=info"

[Install]
WantedBy=multi-user.target
```

## Multi-Agent Setup

See [Multi-Agent Architecture](multi_agent.md) for concurrent execution patterns.

```rust
use tokio::try_join;

async fn run_multiagent() -> Result<()> {
    let (result1, result2) = try_join!(
        agent1.run(prompt1),
        agent2.run(prompt2)
    )?;
    
    Ok(())
}
```

## References

- [Chimera Optimization Guide](chimera_optimization.md)
- [Benchmarking Guide](benchmarking.md)
- [TR111: Rust Single-Agent](../outputs/publish_ready/reports/Technical_Report_111.md)
- [TR114: Rust Multi-Agent](../outputs/publish_ready/reports/Technical_Report_114.md)

---

**Last Updated**: November 2025

