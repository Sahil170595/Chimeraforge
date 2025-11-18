# Runtime Variants Implementation Details

## Overview

TR115 tests 5 Rust async runtime configurations to identify the optimal balance between performance and concurrency efficiency for multi-agent LLM workloads.

## Runtime Variants

### 1. tokio-default (Baseline)

**Feature flag**: `runtime-tokio-default`

**Implementation**:
```rust
#[tokio::main]
async fn main() -> Result<()> {
    async_main().await
}
```

**Characteristics**:
- Work-stealing scheduler (multi-threaded)
- Aggressive task distribution
- Reqwest HTTP client (8KB buffering)

**Expected Performance**:
- Peak efficiency: 95.7% (TR114 baseline)
- Strengths: Mature, well-tested
- Weaknesses: Work-stealing overhead causes cache thrashing

---

### 2. tokio-localset (Single-Threaded Tokio)

**Feature flag**: `runtime-tokio-localset`

**Implementation**:
```rust
#[tokio::main]
async fn main() -> Result<()> {
    async_main().await  // Uses LocalSet internally
}

// Inside async_main():
let local = tokio::task::LocalSet::new();
local.run_until(async {
    tokio::try_join!(agent1, agent2)
}).await
```

**Characteristics**:
- Single-threaded execution via LocalSet
- No work-stealing between agents
- Reqwest HTTP client (8KB buffering)

**Expected Performance**:
- Peak efficiency: 97-98% (+2-3pp vs baseline)
- Strengths: Eliminates work-stealing overhead, preserves cache locality
- Weaknesses: Still uses 8KB buffering

**Hypothesis**: Pinning both agents to single thread prevents cache thrashing observed in TR114.

---

### 3. async-std (Simpler Runtime)

**Feature flag**: `runtime-async-std`

**Implementation**:
```rust
#[async_std::main]
async fn main() -> Result<()> {
    async_main().await
}
```

**Characteristics**:
- Simpler scheduler than tokio
- Less aggressive work-stealing
- Reqwest HTTP client (8KB buffering)

**Expected Performance**:
- Peak efficiency: 96-97% (+1-2pp vs baseline)
- Strengths: Lighter runtime overhead
- Weaknesses: Less mature than tokio for high-performance use cases

---

### 4. smol (Lightweight Runtime)

**Feature flag**: `runtime-smol`

**Implementation**:
```rust
fn main() -> Result<()> {
    smol::block_on(async_main())
}
```

**Characteristics**:
- Minimal runtime overhead
- Single-threaded by default
- Reqwest HTTP client (8KB buffering)

**Expected Performance**:
- Peak efficiency: 97-98% (+2-3pp vs baseline)
- Strengths: Lightest runtime, minimal scheduling overhead
- Weaknesses: Still uses 8KB buffering

**Hypothesis**: Smol's minimal overhead eliminates work-stealing and reduces context switch costs.

---

### 5. smol-1kb (Custom HTTP Client)

**Feature flag**: `runtime-smol-1kb`

**Implementation**:
```rust
fn main() -> Result<()> {
    smol::block_on(async_main())
}

// Custom HTTP client
use http_client_1kb::Http1KBClient;
let client = Http1KBClient::new()?;
```

**Characteristics**:
- smol runtime (minimal overhead)
- Custom hyper-based HTTP client
- **1KB chunk buffering** (vs reqwest's 8KB)

**Expected Performance**:
- Peak efficiency: 98-99% (+3-4pp vs baseline)
- Strengths: Matches Python httpx's 1KB buffering, minimal runtime overhead
- Weaknesses: Custom client requires maintenance

**Hypothesis**: Combination of lightweight runtime + 1KB chunking closes the gap to Python's 99.25%.

---

## Custom 1KB HTTP Client

### Implementation

**File**: `src/http_client_1kb.rs`

**Key Features**:
- Hyper-based streaming HTTP client
- Enforces 1KB maximum chunk size
- Matches Python httpx behavior

**Code Overview**:
```rust
pub struct Http1KBClient {
    client: LegacyClient<HttpConnector, Body>,
}

impl Http1KBClient {
    pub async fn post_streaming<T: Serialize>(
        &self,
        url: &str,
        body: &T,
    ) -> Result<impl Stream<Item = Result<Vec<u8>>>> {
        // Build request
        // Send with hyper
        // Return stream with 1KB chunks
    }
}
```

**Rationale**: Python's httpx uses 1KB buffer size for smoother I/O interleaving between concurrent agents. Reqwest's 8KB default creates longer blocking periods.

---

## Conditional Compilation

### ResourceCoordinator

The `ResourceCoordinator` struct uses different semaphore types per runtime:

```rust
#[cfg(any(feature = "runtime-tokio-default", feature = "runtime-tokio-localset"))]
struct ResourceCoordinator {
    semaphore: Arc<tokio::sync::Semaphore>,
}

#[cfg(feature = "runtime-async-std")]
struct ResourceCoordinator {
    semaphore: Arc<async_std::sync::Semaphore>,
}

#[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
struct ResourceCoordinator {
    semaphore: Arc<smol::lock::Semaphore>,
}
```

### Client Type

```rust
#[cfg(not(feature = "runtime-smol-1kb"))]
let client = reqwest::Client::builder()
    .timeout(Duration::from_secs(300))
    .build()?;

#[cfg(feature = "runtime-smol-1kb")]
let client = Http1KBClient::new()?;
```

---

## Building Runtime Variants

### Build Commands

```bash
# tokio-default
cargo build --release --no-default-features --features=runtime-tokio-default

# tokio-localset
cargo build --release --no-default-features --features=runtime-tokio-localset

# async-std
cargo build --release --no-default-features --features=runtime-async-std

# smol
cargo build --release --no-default-features --features=runtime-smol

# smol-1kb
cargo build --release --no-default-features --features=runtime-smol-1kb
```

### Automated Build

The `run_tr115_sweep.py` script automatically builds each variant:

```python
cmd = [
    "cargo", "build", "--release",
    "--no-default-features",
    f"--features={runtime}",
]
subprocess.run(cmd, cwd=RUST_PROJECT)
```

---

## Expected Results Summary

| Runtime | Expected Peak | Expected Gain | Key Optimization |
|---------|---------------|---------------|------------------|
| tokio-default | 95.7% | (baseline) | - |
| tokio-localset | 97-98% | +2-3pp | No work-stealing |
| async-std | 96-97% | +1-2pp | Simpler scheduler |
| smol | 97-98% | +2-3pp | Minimal overhead |
| smol-1kb | 98-99% | +3-4pp | 1KB chunks + light runtime |

**Target**: ≥98% efficiency (within 1.25pp of Python's 99.25%)

---

## References

- [TR114: Rust Multi-Agent (Dual Ollama)](../../PublishReady/reports/Technical_Report_114.md)
- [TR110: Python Multi-Agent](../../PublishReady/reports/Technical_Report_110.md)
- [Tokio Documentation](https://tokio.rs/)
- [async-std Documentation](https://async.rs/)
- [smol Documentation](https://docs.rs/smol/)

---

**Last Updated**: November 13, 2025

