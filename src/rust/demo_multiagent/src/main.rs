use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    fmt::Display,
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime},
};

use anyhow::{Context, Result};
use bytes::Bytes;
use chrono::{DateTime, TimeZone, Utc};
use clap::{Parser, ValueEnum};
use csv::ReaderBuilder;
use futures_util::StreamExt;
use hostname::get as get_hostname;
use rustc_version_runtime::version;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tracing::{info, warn, Level};
use tracing_subscriber::EnvFilter;
use walkdir::WalkDir;

#[cfg(any(
    feature = "runtime-async-std",
    feature = "runtime-smol",
    feature = "runtime-smol-1kb"
))]
mod http_runtime {
    use once_cell::sync::Lazy;
    use tokio::runtime::Runtime;

    static TOKIO_HTTP_RUNTIME: Lazy<Runtime> = Lazy::new(|| {
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .build()
            .expect("Tokio runtime for HTTP client")
    });

    pub async fn run<F, T>(future: F) -> T
    where
        F: std::future::Future<Output = T> + Send + 'static,
        T: Send + 'static,
    {
        TOKIO_HTTP_RUNTIME
            .spawn(future)
            .await
            .expect("HTTP task panicked")
    }
}

#[cfg(not(any(
    feature = "runtime-async-std",
    feature = "runtime-smol",
    feature = "runtime-smol-1kb"
)))]
mod http_runtime {
    pub async fn run<F, T>(future: F) -> T
    where
        F: std::future::Future<Output = T>,
    {
        future.await
    }
}

// Runtime-specific imports
#[cfg(any(feature = "runtime-tokio-default", feature = "runtime-tokio-localset"))]
use tokio::{fs, sync::Semaphore};

#[cfg(feature = "runtime-async-std")]
use async_std::{fs, task};

#[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
use smol::{fs, lock::Semaphore};

// HTTP client imports
#[cfg(not(feature = "runtime-smol-1kb"))]
use reqwest::Client as ReqwestClient;

#[cfg(feature = "runtime-smol-1kb")]
mod http_client_1kb;
#[cfg(feature = "runtime-smol-1kb")]
use http_client_1kb::Http1KBClient;

const DATA_COLLECTOR_PROMPT: &str = r#"You are DataCollector-9000, a systems analyst tasked with scanning benchmark artifacts.
Produce a concise data inventory with bullet points that highlight:
1. Directory coverage (reports/, csv_data/, artifacts/).
2. File counts per type (md, csv, json) and the latest modified timestamp you observe.
3. Any gaps or missing telemetry that could impact model evaluation.
Keep the response under 250 words but include concrete metrics so a second agent can reason over them."#;

const INSIGHT_AGENT_PROMPT: &str = r#"You are InsightAgent, a Chimera-optimised LLM operations specialist.
Given the repository context described previously, produce:
1. Executive summary of model performance.
2. Three optimisation recommendations that balance throughput, TTFT, and quality.
3. A risk/mitigation table with at least two rows.
Aim for 300-400 words, with numbered sections and bolded metric callouts."#;

#[derive(Parser, Debug)]
#[command(
    name = "demo_rust_multiagent",
    about = "Rust concurrent multi-agent benchmark"
)]
struct Args {
    #[arg(long, default_value = "gemma3:latest")]
    model: String,

    #[arg(long, default_value_t = 1)]
    runs: u32,

    #[arg(long, default_value = "Demo_rust_multiagent_results")]
    output_dir: String,

    #[arg(long, value_enum, default_value_t = Scenario::BaselineVsChimera)]
    scenario: Scenario,

    #[arg(long)]
    chimera_num_gpu: Option<u32>,
    #[arg(long)]
    chimera_num_ctx: Option<u32>,
    #[arg(long)]
    chimera_temperature: Option<f32>,
    #[arg(long)]
    chimera_top_p: Option<f32>,
    #[arg(long)]
    chimera_top_k: Option<u32>,
    #[arg(long)]
    chimera_repeat_penalty: Option<f32>,

    #[arg(long)]
    chimera2_num_gpu: Option<u32>,
    #[arg(long)]
    chimera2_num_ctx: Option<u32>,
    #[arg(long)]
    chimera2_temperature: Option<f32>,
    #[arg(long)]
    chimera2_top_p: Option<f32>,
    #[arg(long)]
    chimera2_top_k: Option<u32>,
    #[arg(long)]
    chimera2_repeat_penalty: Option<f32>,

    #[arg(long, default_value = "http://localhost:11434")]
    collector_ollama_url: String,
    #[arg(long, default_value = "http://localhost:11434")]
    insight_ollama_url: String,
}

#[derive(ValueEnum, Clone, Debug, Copy)]
enum Scenario {
    BaselineVsChimera,
    ChimeraHetero,
    ChimeraHomo,
}

impl Display for Scenario {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Scenario::BaselineVsChimera => write!(f, "baseline_vs_chimera"),
            Scenario::ChimeraHetero => write!(f, "chimera_hetero"),
            Scenario::ChimeraHomo => write!(f, "chimera_homo"),
        }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct OllamaOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    num_gpu: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    num_ctx: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_k: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    repeat_penalty: Option<f32>,
}

impl OllamaOptions {
    fn is_empty(&self) -> bool {
        self.num_gpu.is_none()
            && self.num_ctx.is_none()
            && self.temperature.is_none()
            && self.top_p.is_none()
            && self.top_k.is_none()
            && self.repeat_penalty.is_none()
    }

    fn description(&self) -> String {
        if self.is_empty() {
            "Ollama defaults".to_string()
        } else {
            format!(
                "num_gpu={}, num_ctx={}, temp={}, top_p={}, top_k={}, repeat_penalty={}",
                display_opt(self.num_gpu),
                display_opt(self.num_ctx),
                display_opt(self.temperature),
                display_opt(self.top_p),
                display_opt(self.top_k),
                display_opt(self.repeat_penalty)
            )
        }
    }
}

fn display_opt<T: ToString>(value: Option<T>) -> String {
    value
        .map(|v| v.to_string())
        .unwrap_or_else(|| "default".into())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AgentConfig {
    id: String,
    label: String,
    prompt: String,
    model: String,
    base_url: String,
    options: OllamaOptions,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct SingleRunMetrics {
    ttft_ms: f64,
    throughput_tokens_per_sec: f64,
    total_duration_ms: f64,
    tokens_generated: u64,
    prompt_eval_duration_ms: f64,
    eval_duration_ms: f64,
    load_duration_ms: f64,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct AggregateMetrics {
    average_tokens_per_second: f64,
    average_ttft_ms: f64,
    total_duration_ms: f64,
    total_tokens_generated: u64,
    prompt_eval_duration_ms: f64,
    eval_duration_ms: f64,
    load_duration_ms: f64,
    stddev_throughput: f64,
    stddev_ttft: f64,
}

#[derive(Debug, Clone)]
enum BenchmarkDataType {
    Csv,
    Json,
    Markdown,
}

impl BenchmarkDataType {
    fn from_extension(ext: &str) -> Option<Self> {
        match ext {
            "csv" => Some(Self::Csv),
            "json" => Some(Self::Json),
            "md" | "markdown" => Some(Self::Markdown),
            _ => None,
        }
    }

    fn label(&self) -> &'static str {
        match self {
            Self::Csv => "csv",
            Self::Json => "json",
            Self::Markdown => "markdown",
        }
    }
}

#[derive(Debug, Clone)]
struct BenchmarkMetadata {
    file_size: u64,
    modified_unix: Option<i64>,
}

#[derive(Debug, Clone)]
enum BenchmarkContent {
    Csv(Vec<HashMap<String, String>>),
    Json(Value),
    Markdown(String),
}

#[derive(Debug, Clone)]
struct BenchmarkData {
    source_file: String,
    data_type: BenchmarkDataType,
    metadata: BenchmarkMetadata,
    content: BenchmarkContent,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct AnalysisPayload {
    summary: String,
    key_findings: Vec<String>,
    performance_metrics: HashMap<String, Value>,
    recommendations: Vec<String>,
    raw_response: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct WorkflowBreakdown {
    ingest_seconds: f64,
    analysis_seconds: f64,
    report_seconds: f64,
    total_seconds: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct LlmCallRecord {
    stage: String,
    prompt: String,
    response: String,
    metrics: SingleRunMetrics,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct SystemInfo {
    os: String,
    arch: String,
    hostname: String,
    rust_version: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct RunResult {
    agent_type: String,
    model: String,
    runs: u32,
    configuration: OllamaOptions,
    individual_runs: Vec<SingleRunMetrics>,
    aggregate_metrics: AggregateMetrics,
    timestamp: DateTime<Utc>,
    system_info: SystemInfo,
    prompt: String,
    analysis: AnalysisPayload,
    report_markdown: String,
    data_summary: String,
    benchmark_data_count: usize,
    workflow: WorkflowBreakdown,
    llm_calls: Vec<LlmCallRecord>,
}

struct LlmCallOutcome {
    text: String,
    metrics: SingleRunMetrics,
}

#[derive(Debug, Serialize, Deserialize)]
struct AgentExecution {
    config: AgentConfig,
    result: RunResult,
    execution_time_s: f64,
}

#[derive(Debug, Serialize, Deserialize)]
struct RunSummary {
    run_number: u32,
    scenario: String,
    throughput_delta: f64,
    ttft_delta_ms: f64,
    concurrency_speedup: f64,
    efficiency_percent: f64,
    sequential_estimated_s: f64,
    concurrent_wall_time_s: f64,
    resource_contention_detected: bool,
    collector_throughput: f64,
    insight_throughput: f64,
    collector_ttft_ms: f64,
    insight_ttft_ms: f64,
}

fn stddev(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let variance =
        values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (values.len() - 1) as f64;
    variance.sqrt()
}

fn repository_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")))
}

fn ingest_benchmarks_sync(repo_root: PathBuf) -> Result<Vec<BenchmarkData>> {
    let mut benchmark_data = Vec::new();
    let targets = [
        ("reports", vec!["csv", "json", "md"]),
        ("csv_data", vec!["csv", "json"]),
    ];

    for (dir, extensions) in targets {
        let dir_path = repo_root.join(dir);
        if !dir_path.exists() {
            continue;
        }
        match load_benchmark_dir(&dir_path, &repo_root, &extensions) {
            Ok(mut data) => benchmark_data.append(&mut data),
            Err(err) => warn!("Failed to scan {}: {}", dir_path.display(), err),
        }
    }

    Ok(benchmark_data)
}

fn load_benchmark_dir(
    dir: &Path,
    repo_root: &Path,
    allowed_exts: &[&str],
) -> Result<Vec<BenchmarkData>> {
    let mut data = Vec::new();
    for entry in WalkDir::new(dir).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let ext = match path
            .extension()
            .and_then(|s| s.to_str())
            .map(|s| s.to_lowercase())
        {
            Some(ext) if allowed_exts.iter().any(|allowed| allowed == &ext.as_str()) => ext,
            _ => continue,
        };

        let Some(kind) = BenchmarkDataType::from_extension(&ext) else {
            continue;
        };

        match load_benchmark_file(path, kind, repo_root) {
            Ok(Some(b)) => data.push(b),
            Ok(None) => continue,
            Err(err) => warn!("Warning: Could not load {}: {}", path.display(), err),
        }
    }
    Ok(data)
}

fn load_benchmark_file(
    path: &Path,
    kind: BenchmarkDataType,
    repo_root: &Path,
) -> Result<Option<BenchmarkData>> {
    let metadata = std::fs::metadata(path)?;
    let modified_unix = metadata
        .modified()
        .ok()
        .and_then(|time| time.duration_since(SystemTime::UNIX_EPOCH).ok())
        .map(|dur| dur.as_secs() as i64);
    let rel_path = path
        .strip_prefix(repo_root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/");
    let meta = BenchmarkMetadata {
        file_size: metadata.len(),
        modified_unix,
    };

    let content = match kind {
        BenchmarkDataType::Csv => BenchmarkContent::Csv(read_csv_rows(path)?),
        BenchmarkDataType::Json => {
            let text = std::fs::read_to_string(path)?;
            let value: Value = serde_json::from_str(&text)?;
            BenchmarkContent::Json(value)
        }
        BenchmarkDataType::Markdown => {
            let text = std::fs::read_to_string(path)?;
            BenchmarkContent::Markdown(text)
        }
    };

    Ok(Some(BenchmarkData {
        source_file: rel_path,
        data_type: kind,
        metadata: meta,
        content,
    }))
}

fn read_csv_rows(path: &Path) -> Result<Vec<HashMap<String, String>>> {
    let mut reader = ReaderBuilder::new().from_path(path)?;
    let headers = reader.headers()?.clone();
    let mut rows = Vec::new();
    for result in reader.records() {
        let record = result?;
        let mut row = HashMap::new();
        for (idx, header) in headers.iter().enumerate() {
            let value = record.get(idx).unwrap_or("").trim().to_string();
            row.insert(header.to_string(), value);
        }
        rows.push(row);
    }
    Ok(rows)
}

fn create_data_summary(benchmark_data: &[BenchmarkData]) -> String {
    let mut summary = format!("Total files analyzed: {}\n\n", benchmark_data.len());
    let mut grouped: BTreeMap<&str, Vec<&BenchmarkData>> = BTreeMap::new();
    for data in benchmark_data {
        grouped
            .entry(data.data_type.label())
            .or_default()
            .push(data);
    }
    for (data_type, files) in grouped {
        summary.push_str(&format!(
            "{} Files ({})\n",
            data_type.to_uppercase(),
            files.len()
        ));
        for file in files.iter().take(5) {
            summary.push_str(&format!("  - {}\n", file.source_file));
        }
        if files.len() > 5 {
            summary.push_str(&format!("  ... and {} more\n", files.len() - 5));
        }
        if let Some(latest) = files
            .iter()
            .filter_map(|file| file.metadata.modified_unix)
            .max()
            .and_then(|ts| Utc.timestamp_opt(ts, 0).single())
        {
            summary.push_str(&format!(
                "  Latest modified: {}\n",
                latest.format("%Y-%m-%d %H:%M:%S UTC")
            ));
        }
        summary.push('\n');
    }
    summary
}

fn extract_summary_section(response: &str) -> String {
    let mut summary_lines = Vec::new();
    let mut in_summary = false;
    for line in response.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() && in_summary {
            summary_lines.push(String::new());
            continue;
        }
        let lower = trimmed.to_lowercase();
        if lower.contains("executive summary") || lower == "summary" {
            in_summary = true;
            continue;
        }
        if in_summary && trimmed.starts_with('#') {
            break;
        }
        if in_summary {
            summary_lines.push(trimmed.to_string());
        }
    }
    if summary_lines.is_empty() {
        response
            .lines()
            .take(5)
            .map(|l| l.trim().to_string())
            .collect::<Vec<_>>()
            .join("\n")
    } else {
        summary_lines
            .into_iter()
            .filter(|line| !line.is_empty())
            .collect::<Vec<_>>()
            .join("\n")
    }
}

fn clean_bullet(line: &str) -> String {
    let trimmed = line.trim_start_matches(|c: char| c == '-' || c == '*' || c == '•');
    trimmed
        .trim_start_matches(|c: char| c.is_ascii_digit() || c == '.' || c == ')')
        .trim()
        .to_string()
}

fn should_capture_metric(label: &str) -> bool {
    let lower = label.to_lowercase();
    ["tok", "throughput", "latency", "ttft", "speed"]
        .iter()
        .any(|needle| lower.contains(needle))
}

fn parse_numeric_str(value: &str) -> Option<f64> {
    value
        .trim()
        .trim_end_matches(|c: char| c == '%' || c == 's')
        .replace(',', "")
        .parse::<f64>()
        .ok()
}

fn harvest_json_metrics(value: &Value, path: &str, metrics: &mut HashMap<String, Value>) {
    match value {
        Value::Object(map) => {
            for (key, val) in map {
                let new_path = if path.is_empty() {
                    key.clone()
                } else {
                    format!("{path}.{key}")
                };
                harvest_json_metrics(val, &new_path, metrics);
            }
        }
        Value::Array(items) => {
            for (idx, item) in items.iter().enumerate() {
                let new_path = if path.is_empty() {
                    format!("[{idx}]")
                } else {
                    format!("{path}[{idx}]")
                };
                harvest_json_metrics(item, &new_path, metrics);
            }
        }
        Value::Number(num) => {
            if !path.is_empty() && should_capture_metric(path) {
                if let Some(parsed) = num.as_f64() {
                    metrics
                        .entry(format!("json_{path}"))
                        .or_insert_with(|| Value::from(parsed));
                }
            }
        }
        Value::String(text) => {
            if !path.is_empty() && should_capture_metric(path) {
                if let Some(parsed) = parse_numeric_str(text) {
                    metrics
                        .entry(format!("json_{path}"))
                        .or_insert_with(|| Value::from(parsed));
                }
            }
        }
        _ => {}
    }
}

fn extract_lines_with_keywords(response: &str, keywords: &[&str], limit: usize) -> Vec<String> {
    let mut matches = Vec::new();
    for line in response.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let lower = trimmed.to_lowercase();
        if keywords.iter().any(|kw| lower.contains(kw)) {
            matches.push(clean_bullet(trimmed));
            if matches.len() >= limit {
                break;
            }
        }
    }
    matches
}

fn extract_performance_metrics_from_data(
    benchmark_data: &[BenchmarkData],
) -> HashMap<String, Value> {
    let mut metrics = HashMap::new();
    metrics.insert(
        "total_files_analyzed".into(),
        Value::from(benchmark_data.len() as u64),
    );
    let mut data_types = BTreeSet::new();
    let mut total_size = 0_u64;
    for data in benchmark_data {
        data_types.insert(data.data_type.label().to_string());
        total_size += data.metadata.file_size;
    }
    metrics.insert(
        "data_types".into(),
        Value::from(
            data_types
                .into_iter()
                .map(Value::String)
                .collect::<Vec<_>>(),
        ),
    );
    metrics.insert("total_file_size_bytes".into(), Value::from(total_size));

    let mut markdown_headings = 0_u64;
    let mut json_documents = 0_u64;
    for data in benchmark_data {
        match &data.content {
            BenchmarkContent::Csv(rows) => {
                for row in rows.iter().take(10) {
                    for (key, value) in row {
                        if !should_capture_metric(key) {
                            continue;
                        }
                        let metric_key = format!("csv_{key}");
                        if metrics.contains_key(&metric_key) {
                            continue;
                        }
                        if let Some(parsed) = parse_numeric_str(value) {
                            metrics
                                .entry(metric_key)
                                .or_insert_with(|| Value::from(parsed));
                        } else {
                            metrics
                                .entry(metric_key)
                                .or_insert_with(|| Value::from(value.clone()));
                        }
                    }
                }
            }
            BenchmarkContent::Json(value) => {
                json_documents += 1;
                harvest_json_metrics(value, "", &mut metrics);
            }
            BenchmarkContent::Markdown(text) => {
                markdown_headings += text
                    .lines()
                    .filter(|line| line.trim_start().starts_with('#'))
                    .count() as u64;
            }
        }
    }
    if json_documents > 0 {
        metrics
            .entry("json_documents".into())
            .or_insert_with(|| Value::from(json_documents));
    }
    if markdown_headings > 0 {
        metrics
            .entry("markdown_heading_count".into())
            .or_insert_with(|| Value::from(markdown_headings));
    }

    metrics
}

fn parse_analysis_response(response: &str, benchmark_data: &[BenchmarkData]) -> AnalysisPayload {
    AnalysisPayload {
        summary: extract_summary_section(response),
        key_findings: extract_lines_with_keywords(
            response,
            &["finding", "insight", "discovery", "key"],
            10,
        ),
        performance_metrics: extract_performance_metrics_from_data(benchmark_data),
        recommendations: extract_lines_with_keywords(
            response,
            &["recommend", "suggest", "should", "consider"],
            10,
        ),
        raw_response: response.to_string(),
    }
}

#[cfg(any(feature = "runtime-tokio-default", feature = "runtime-tokio-localset"))]
async fn ingest_benchmarks(repo_root: &Path) -> Result<Vec<BenchmarkData>> {
    let root = repo_root.to_path_buf();
    let handle = tokio::task::spawn_blocking(move || ingest_benchmarks_sync(root));
    let result = handle.await??;
    Ok(result)
}

#[cfg(feature = "runtime-async-std")]
async fn ingest_benchmarks(repo_root: &Path) -> Result<Vec<BenchmarkData>> {
    let root = repo_root.to_path_buf();
    let result = task::spawn_blocking(move || ingest_benchmarks_sync(root)).await;
    Ok(result?)
}

#[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
async fn ingest_benchmarks(repo_root: &Path) -> Result<Vec<BenchmarkData>> {
    let root = repo_root.to_path_buf();
    let result = smol::unblock(move || ingest_benchmarks_sync(root)).await;
    Ok(result?)
}

fn build_analysis_prompt(data_summary: &str) -> String {
    format!(
        "You are a performance analysis expert. Analyze the following benchmark data and provide insights.\n\n\
Benchmark Data Summary:\n{data_summary}\n\n\
Please provide:\n\
1. Executive summary of the data\n\
2. Key performance findings\n\
3. Performance metrics analysis\n\
4. Recommendations for optimization\n\n\
Format your response as structured analysis with clear sections."
    )
}

fn build_report_prompt(analysis: &AnalysisPayload) -> Result<String> {
    let findings = if analysis.key_findings.is_empty() {
        "None provided".to_string()
    } else {
        analysis
            .key_findings
            .iter()
            .enumerate()
            .map(|(idx, finding)| format!("{}. {}", idx + 1, finding))
            .collect::<Vec<_>>()
            .join("\n")
    };
    let recommendations = if analysis.recommendations.is_empty() {
        "None provided".to_string()
    } else {
        analysis
            .recommendations
            .iter()
            .enumerate()
            .map(|(idx, rec)| format!("{}. {}", idx + 1, rec))
            .collect::<Vec<_>>()
            .join("\n")
    };
    let metrics_json = serde_json::to_string_pretty(&analysis.performance_metrics)?;
    Ok(format!(
        "Generate a comprehensive technical report in the style of Technical Report 108.\n\n\
Analysis Results:\n\
- Summary: {summary}\n\
- Key Findings:\n{findings}\n\
- Performance Metrics: {metrics}\n\
- Recommendations:\n{recs}\n\n\
Create a professional technical report with the following structure:\n\
1. Executive Summary\n\
2. Data Ingestion Summary\n\
3. Performance Analysis\n\
4. Key Findings\n\
5. Recommendations\n\
6. Appendix\n\n\
Use markdown formatting and include specific metrics and data points.",
        summary = analysis.summary,
        findings = findings,
        metrics = metrics_json,
        recs = recommendations
    ))
}

fn aggregate_llm_metrics(metrics: &[SingleRunMetrics]) -> AggregateMetrics {
    if metrics.is_empty() {
        return AggregateMetrics::default();
    }
    let throughput_values: Vec<f64> = metrics
        .iter()
        .map(|m| m.throughput_tokens_per_sec)
        .collect();
    let ttft_values: Vec<f64> = metrics.iter().map(|m| m.ttft_ms).collect();
    AggregateMetrics {
        average_tokens_per_second: throughput_values.iter().sum::<f64>() / metrics.len() as f64,
        average_ttft_ms: ttft_values.iter().sum::<f64>() / metrics.len() as f64,
        total_duration_ms: metrics.iter().map(|m| m.total_duration_ms).sum(),
        total_tokens_generated: metrics.iter().map(|m| m.tokens_generated).sum(),
        prompt_eval_duration_ms: metrics.iter().map(|m| m.prompt_eval_duration_ms).sum(),
        eval_duration_ms: metrics.iter().map(|m| m.eval_duration_ms).sum(),
        load_duration_ms: metrics.iter().map(|m| m.load_duration_ms).sum(),
        stddev_throughput: stddev(&throughput_values),
        stddev_ttft: stddev(&ttft_values),
    }
}

#[cfg(any(feature = "runtime-tokio-default", feature = "runtime-tokio-localset"))]
struct ResourceCoordinator {
    semaphore: std::sync::Arc<tokio::sync::Semaphore>,
}

#[cfg(feature = "runtime-async-std")]
struct ResourceCoordinator {
    semaphore: std::sync::Arc<async_std::sync::Mutex<usize>>,
    max_permits: usize,
}

#[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
struct ResourceCoordinator {
    semaphore: std::sync::Arc<smol::lock::Semaphore>,
}

#[cfg(any(feature = "runtime-tokio-default", feature = "runtime-tokio-localset"))]
impl ResourceCoordinator {
    fn new(size: usize) -> Self {
        Self {
            semaphore: std::sync::Arc::new(Semaphore::new(size)),
        }
    }

    async fn with_permit<F, Fut, T>(&self, fut: F) -> Result<T>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<T>>,
    {
        let permit = self.semaphore.acquire().await?;
        let result = fut().await;
        drop(permit);
        result
    }
}

#[cfg(feature = "runtime-async-std")]
impl ResourceCoordinator {
    fn new(size: usize) -> Self {
        Self {
            semaphore: std::sync::Arc::new(async_std::sync::Mutex::new(0)),
            max_permits: size,
        }
    }

    async fn with_permit<F, Fut, T>(&self, fut: F) -> Result<T>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<T>>,
    {
        // Simple lock-based coordination for async-std
        let _guard = self.semaphore.lock().await;
        fut().await
    }
}

#[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
impl ResourceCoordinator {
    fn new(size: usize) -> Self {
        Self {
            semaphore: std::sync::Arc::new(Semaphore::new(size)),
        }
    }

    async fn with_permit<F, Fut, T>(&self, fut: F) -> Result<T>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<T>>,
    {
        let permit = self.semaphore.acquire().await;
        let result = fut().await;
        drop(permit);
        result
    }
}

fn collect_overrides(
    num_gpu: Option<u32>,
    num_ctx: Option<u32>,
    temperature: Option<f32>,
    top_p: Option<f32>,
    top_k: Option<u32>,
    repeat_penalty: Option<f32>,
) -> OllamaOptions {
    OllamaOptions {
        num_gpu,
        num_ctx,
        temperature,
        top_p,
        top_k,
        repeat_penalty,
    }
}

fn system_info() -> SystemInfo {
    SystemInfo {
        os: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        hostname: get_hostname()
            .ok()
            .and_then(|h| h.into_string().ok())
            .unwrap_or_else(|| "unknown-host".into()),
        rust_version: version().to_string(),
    }
}

// Reqwest-based streaming (all runtimes except smol-1kb) with Tokio bridge for non-Tokio runtimes
#[cfg(not(feature = "runtime-smol-1kb"))]
async fn call_ollama_streaming(
    client: &ReqwestClient,
    base_url: &str,
    model: &str,
    prompt: &str,
    options: &OllamaOptions,
) -> Result<LlmCallOutcome> {
    #[derive(Serialize)]
    struct GenerateRequest {
        model: String,
        prompt: String,
        stream: bool,
        #[serde(skip_serializing_if = "OllamaOptions::is_empty")]
        options: OllamaOptions,
    }

    let client = client.clone();
    let base_url = base_url.trim_end_matches('/').to_owned();
    let model = model.to_owned();
    let prompt = prompt.to_owned();
    let options = options.clone();

    http_runtime::run(async move {
        let req = GenerateRequest {
            model,
            prompt,
            stream: true,
            options,
        };
        let url = format!("{}/api/generate", base_url);

        let request_start = Instant::now();
        let resp = client
            .post(&url)
            .json(&req)
            .send()
            .await
            .with_context(|| format!("Failed to reach Ollama at {}", url))?;
        if !resp.status().is_success() {
            anyhow::bail!("Ollama error: {}", resp.status());
        }

        let mut stream = resp.bytes_stream();
        let mut first_chunk_time: Option<Instant> = None;
        let mut total_tokens: u64 = 0;
        let mut prompt_eval_duration_ns: u64 = 0;
        let mut eval_duration_ns: u64 = 0;
        let mut load_duration_ns: u64 = 0;
        let mut buffer = String::new();

        let mut response_text = String::new();

        let mut process_line = |line: &str| {
            if line.trim().is_empty() {
                return;
            }
            if let Ok(value) = serde_json::from_str::<serde_json::Value>(line) {
                if let Some(response) = value.get("response").and_then(|r| r.as_str()) {
                    if !response.is_empty() {
                        response_text.push_str(response);
                    }
                    if !response.is_empty() && first_chunk_time.is_none() {
                        first_chunk_time = Some(Instant::now());
                    }
                }
                if let Some(true) = value.get("done").and_then(|d| d.as_bool()) {
                    total_tokens = value
                        .get("eval_count")
                        .and_then(|e| e.as_u64())
                        .unwrap_or(0);
                    prompt_eval_duration_ns = value
                        .get("prompt_eval_duration")
                        .and_then(|d| d.as_u64())
                        .unwrap_or(0);
                    eval_duration_ns = value
                        .get("eval_duration")
                        .and_then(|d| d.as_u64())
                        .unwrap_or(0);
                    load_duration_ns = value
                        .get("load_duration")
                        .and_then(|d| d.as_u64())
                        .unwrap_or(0);
                }
            }
        };

        while let Some(chunk_result) = stream.next().await {
            let chunk: Bytes = chunk_result?;
            let chunk_str = String::from_utf8_lossy(&chunk);
            buffer.push_str(&chunk_str);
            while let Some(idx) = buffer.find('\n') {
                let line = buffer[..idx].to_string();
                buffer.drain(..=idx);
                process_line(&line);
            }
        }
        if !buffer.trim().is_empty() {
            process_line(&buffer);
        }

        let total_elapsed = request_start.elapsed();
        let ttft = first_chunk_time
            .map(|t| t.duration_since(request_start))
            .unwrap_or(total_elapsed);

        let ttft_ms = ttft.as_secs_f64() * 1000.0;
        let prompt_eval_ms = prompt_eval_duration_ns as f64 / 1_000_000.0;
        let eval_ms = eval_duration_ns as f64 / 1_000_000.0;
        let load_ms = load_duration_ns as f64 / 1_000_000.0;
        let total_duration_ms = total_elapsed.as_secs_f64() * 1000.0;
        let generation_time_s = (eval_ms / 1000.0).max(1e-6);
        let throughput = total_tokens as f64 / generation_time_s;

        Ok(LlmCallOutcome {
            text: response_text.trim().to_string(),
            metrics: SingleRunMetrics {
                ttft_ms,
                throughput_tokens_per_sec: throughput,
                total_duration_ms,
                tokens_generated: total_tokens,
                prompt_eval_duration_ms: prompt_eval_ms,
                eval_duration_ms: eval_ms,
                load_duration_ms: load_ms,
            },
        })
    })
    .await
}

// 1KB-buffered streaming (smol-1kb runtime) with Tokio bridge
#[cfg(feature = "runtime-smol-1kb")]
async fn call_ollama_streaming(
    client: &Http1KBClient,
    base_url: &str,
    model: &str,
    prompt: &str,
    options: &OllamaOptions,
) -> Result<LlmCallOutcome> {
    #[derive(Serialize)]
    struct GenerateRequest {
        model: String,
        prompt: String,
        stream: bool,
        #[serde(skip_serializing_if = "OllamaOptions::is_empty")]
        options: OllamaOptions,
    }

    let client = client.clone();
    let base_url = base_url.trim_end_matches('/').to_owned();
    let model = model.to_owned();
    let prompt = prompt.to_owned();
    let options = options.clone();

    http_runtime::run(async move {
        let req = GenerateRequest {
            model,
            prompt,
            stream: true,
            options,
        };
        let url = format!("{}/api/generate", base_url);

        let request_start = Instant::now();
        let mut stream = client.post_streaming(&url, &req).await?;

        let mut first_chunk_time: Option<Instant> = None;
        let mut total_tokens: u64 = 0;
        let mut prompt_eval_duration_ns: u64 = 0;
        let mut eval_duration_ns: u64 = 0;
        let mut load_duration_ns: u64 = 0;
        let mut buffer = String::new();

        let mut response_text = String::new();

        let mut process_line = |line: &str| {
            if line.trim().is_empty() {
                return;
            }
            if let Ok(value) = serde_json::from_str::<serde_json::Value>(line) {
                if let Some(response) = value.get("response").and_then(|r| r.as_str()) {
                    if !response.is_empty() {
                        response_text.push_str(response);
                    }
                    if !response.is_empty() && first_chunk_time.is_none() {
                        first_chunk_time = Some(Instant::now());
                    }
                }
                if let Some(true) = value.get("done").and_then(|d| d.as_bool()) {
                    total_tokens = value
                        .get("eval_count")
                        .and_then(|e| e.as_u64())
                        .unwrap_or(0);
                    prompt_eval_duration_ns = value
                        .get("prompt_eval_duration")
                        .and_then(|d| d.as_u64())
                        .unwrap_or(0);
                    eval_duration_ns = value
                        .get("eval_duration")
                        .and_then(|d| d.as_u64())
                        .unwrap_or(0);
                    load_duration_ns = value
                        .get("load_duration")
                        .and_then(|d| d.as_u64())
                        .unwrap_or(0);
                }
            }
        };

        while let Some(chunk_result) = stream.next_chunk().await {
            let chunk = chunk_result?;
            let chunk_str = String::from_utf8_lossy(&chunk);
            buffer.push_str(&chunk_str);
            while let Some(idx) = buffer.find('\n') {
                let line = buffer[..idx].to_string();
                buffer.drain(..=idx);
                process_line(&line);
            }
        }
        if !buffer.trim().is_empty() {
            process_line(&buffer);
        }

        let total_elapsed = request_start.elapsed();
        let ttft = first_chunk_time
            .map(|t| t.duration_since(request_start))
            .unwrap_or(total_elapsed);

        let ttft_ms = ttft.as_secs_f64() * 1000.0;
        let prompt_eval_ms = prompt_eval_duration_ns as f64 / 1_000_000.0;
        let eval_ms = eval_duration_ns as f64 / 1_000_000.0;
        let load_ms = load_duration_ns as f64 / 1_000_000.0;
        let total_duration_ms = total_elapsed.as_secs_f64() * 1000.0;
        let generation_time_s = (eval_ms / 1000.0).max(1e-6);
        let throughput = total_tokens as f64 / generation_time_s;

        Ok(LlmCallOutcome {
            text: response_text.trim().to_string(),
            metrics: SingleRunMetrics {
                ttft_ms,
                throughput_tokens_per_sec: throughput,
                total_duration_ms,
                tokens_generated: total_tokens,
                prompt_eval_duration_ms: prompt_eval_ms,
                eval_duration_ms: eval_ms,
                load_duration_ms: load_ms,
            },
        })
    })
    .await
}

// Client type alias for each runtime
#[cfg(not(feature = "runtime-smol-1kb"))]
type ClientType = ReqwestClient;
#[cfg(feature = "runtime-smol-1kb")]
type ClientType = Http1KBClient;

async fn run_agent_once(client: &ClientType, config: &AgentConfig) -> Result<AgentExecution> {
    let repo_root = repository_root();
    let overall_start = Instant::now();

    let ingest_start = Instant::now();
    let benchmark_data = ingest_benchmarks(&repo_root).await?;
    let ingest_duration = ingest_start.elapsed().as_secs_f64();

    let data_summary = create_data_summary(&benchmark_data);
    let analysis_prompt = build_analysis_prompt(&data_summary);
    let analysis_start = Instant::now();
    let analysis_call = call_ollama_streaming(
        client,
        &config.base_url,
        &config.model,
        analysis_prompt.as_str(),
        &config.options,
    )
    .await?;
    let analysis_duration = analysis_start.elapsed().as_secs_f64();
    let analysis = parse_analysis_response(&analysis_call.text, &benchmark_data);

    let report_prompt = build_report_prompt(&analysis)?;
    let report_start = Instant::now();
    let report_call = call_ollama_streaming(
        client,
        &config.base_url,
        &config.model,
        report_prompt.as_str(),
        &config.options,
    )
    .await?;
    let report_duration = report_start.elapsed().as_secs_f64();

    let total_execution_s = overall_start.elapsed().as_secs_f64();
    let workflow = WorkflowBreakdown {
        ingest_seconds: ingest_duration,
        analysis_seconds: analysis_duration,
        report_seconds: report_duration,
        total_seconds: total_execution_s,
    };

    let llm_calls = vec![
        LlmCallRecord {
            stage: "analysis".into(),
            prompt: analysis_prompt,
            response: analysis_call.text.clone(),
            metrics: analysis_call.metrics.clone(),
        },
        LlmCallRecord {
            stage: "report".into(),
            prompt: report_prompt,
            response: report_call.text.clone(),
            metrics: report_call.metrics.clone(),
        },
    ];
    let individual_runs: Vec<SingleRunMetrics> =
        llm_calls.iter().map(|call| call.metrics.clone()).collect();
    let aggregate = aggregate_llm_metrics(&individual_runs);

    let header = format!(
        "# Technical Report: {label} Analysis\n\n**Date:** {date}\n**Agent Type:** {label}\n**Model:** {model}\n**Configuration:** {config_desc}\n\n---\n\n",
        label = config.label,
        date = Utc::now().format("%Y-%m-%d"),
        model = config.model,
        config_desc = config.options.description(),
    );
    let report_markdown = format!("{header}{}", report_call.text.trim());

    let run_result = RunResult {
        agent_type: config.label.clone(),
        model: config.model.clone(),
        runs: llm_calls.len() as u32,
        configuration: config.options.clone(),
        individual_runs,
        aggregate_metrics: aggregate,
        timestamp: Utc::now(),
        system_info: system_info(),
        prompt: config.prompt.clone(),
        analysis,
        report_markdown,
        data_summary,
        benchmark_data_count: benchmark_data.len(),
        workflow,
        llm_calls,
    };

    Ok(AgentExecution {
        config: config.clone(),
        result: run_result,
        execution_time_s: total_execution_s,
    })
}

fn build_agent_configs(args: &Args) -> (AgentConfig, AgentConfig) {
    let chimera_overrides = collect_overrides(
        args.chimera_num_gpu,
        args.chimera_num_ctx,
        args.chimera_temperature,
        args.chimera_top_p,
        args.chimera_top_k,
        args.chimera_repeat_penalty,
    );
    let chimera2_overrides = collect_overrides(
        args.chimera2_num_gpu,
        args.chimera2_num_ctx,
        args.chimera2_temperature,
        args.chimera2_top_p,
        args.chimera2_top_k,
        args.chimera2_repeat_penalty,
    );

    match args.scenario {
        Scenario::BaselineVsChimera => (
            AgentConfig {
                id: "collector".into(),
                label: "Baseline Collector".into(),
                prompt: DATA_COLLECTOR_PROMPT.to_string(),
                model: args.model.clone(),
                base_url: args.collector_ollama_url.clone(),
                options: OllamaOptions::default(),
            },
            AgentConfig {
                id: "insight".into(),
                label: "Chimera Insight".into(),
                prompt: INSIGHT_AGENT_PROMPT.to_string(),
                model: args.model.clone(),
                base_url: args.insight_ollama_url.clone(),
                options: chimera_overrides,
            },
        ),
        Scenario::ChimeraHetero => (
            AgentConfig {
                id: "chimera_a".into(),
                label: "Chimera Agent A".into(),
                prompt: DATA_COLLECTOR_PROMPT.to_string(),
                model: args.model.clone(),
                base_url: args.collector_ollama_url.clone(),
                options: chimera_overrides.clone(),
            },
            AgentConfig {
                id: "chimera_b".into(),
                label: "Chimera Agent B".into(),
                prompt: INSIGHT_AGENT_PROMPT.to_string(),
                model: args.model.clone(),
                base_url: args.insight_ollama_url.clone(),
                options: if chimera2_overrides.is_empty() {
                    chimera_overrides
                } else {
                    chimera2_overrides
                },
            },
        ),
        Scenario::ChimeraHomo => (
            AgentConfig {
                id: "chimera_a".into(),
                label: "Chimera Agent A".into(),
                prompt: DATA_COLLECTOR_PROMPT.to_string(),
                model: args.model.clone(),
                base_url: args.collector_ollama_url.clone(),
                options: chimera_overrides.clone(),
            },
            AgentConfig {
                id: "chimera_b".into(),
                label: "Chimera Agent B".into(),
                prompt: INSIGHT_AGENT_PROMPT.to_string(),
                model: args.model.clone(),
                base_url: args.insight_ollama_url.clone(),
                options: chimera_overrides,
            },
        ),
    }
}

fn summarize_run(
    run_number: u32,
    scenario: Scenario,
    collector: &AgentExecution,
    insight: &AgentExecution,
    concurrent_wall_time: f64,
) -> RunSummary {
    let collector_throughput = collector.result.aggregate_metrics.average_tokens_per_second;
    let insight_throughput = insight.result.aggregate_metrics.average_tokens_per_second;
    let collector_ttft = collector.result.aggregate_metrics.average_ttft_ms;
    let insight_ttft = insight.result.aggregate_metrics.average_ttft_ms;

    let sequential_time = collector.execution_time_s + insight.execution_time_s;
    let speedup = if concurrent_wall_time > 0.0 {
        sequential_time / concurrent_wall_time
    } else {
        1.0
    };
    let efficiency = (speedup / 2.0) * 100.0;
    RunSummary {
        run_number,
        scenario: scenario.to_string(),
        throughput_delta: insight_throughput - collector_throughput,
        ttft_delta_ms: collector_ttft - insight_ttft,
        concurrency_speedup: speedup,
        efficiency_percent: efficiency,
        sequential_estimated_s: sequential_time,
        concurrent_wall_time_s: concurrent_wall_time,
        resource_contention_detected: speedup < 1.5,
        collector_throughput,
        insight_throughput,
        collector_ttft_ms: collector_ttft,
        insight_ttft_ms: insight_ttft,
    }
}

fn build_combined_report(
    summary: &RunSummary,
    collector: &AgentExecution,
    insight: &AgentExecution,
) -> String {
    format!(
        r#"# Rust Multi-Agent Report – Run {run}

## Scenario
- Type: {scenario}
- Concurrent Wall Time: {wall:.2}s
- Sequential Estimate: {seq:.2}s
- Speedup: {speed:.2}x
- Efficiency: {eff:.1}% (ideal = 2x speedup)
- Contention Detected: {cont}

## Agent A ({agent_a})
- Base URL: {url_a}
- Config: {config_a}
- Throughput: {tp_a:.2} tok/s
- TTFT: {ttft_a:.2} ms
- Total Duration: {dur_a:.2} ms

## Agent B ({agent_b})
- Base URL: {url_b}
- Config: {config_b}
- Throughput: {tp_b:.2} tok/s
- TTFT: {ttft_b:.2} ms
- Total Duration: {dur_b:.2} ms

## Delta (B - A)
- Throughput Δ: {delta_tp:+.2} tok/s
- TTFT Δ: {delta_ttft:+.2} ms (positive = Agent B faster TTFT)
"#,
        run = summary.run_number,
        scenario = summary.scenario,
        wall = summary.concurrent_wall_time_s,
        seq = summary.sequential_estimated_s,
        speed = summary.concurrency_speedup,
        eff = summary.efficiency_percent,
        cont = if summary.resource_contention_detected {
            "Yes"
        } else {
            "No"
        },
        agent_a = collector.config.label,
        url_a = collector.config.base_url,
        config_a = collector.config.options.description(),
        tp_a = summary.collector_throughput,
        ttft_a = summary.collector_ttft_ms,
        dur_a = collector.result.aggregate_metrics.total_duration_ms,
        agent_b = insight.config.label,
        url_b = insight.config.base_url,
        config_b = insight.config.options.description(),
        tp_b = summary.insight_throughput,
        ttft_b = summary.insight_ttft_ms,
        dur_b = insight.result.aggregate_metrics.total_duration_ms,
        delta_tp = summary.throughput_delta,
        delta_ttft = summary.ttft_delta_ms,
    )
}

fn bullet_block(items: &[String]) -> String {
    if items.is_empty() {
        "- None".to_string()
    } else {
        items
            .iter()
            .map(|item| format!("- {}", item))
            .collect::<Vec<_>>()
            .join("\n")
    }
}

fn generate_agent_report(execution: &AgentExecution) -> String {
    let agg = &execution.result.aggregate_metrics;
    let workflow = &execution.result.workflow;
    let analysis = &execution.result.analysis;
    format!(
        r#"# {label}

{report}

---

## Workflow Summary
- Files analyzed: {count}
- Execution time: {total:.2}s (ingest {ing:.2}s | analysis {analysis_s:.2}s | report {report_s:.2}s)
- Data summary:
```
{data_summary}
```

## Metrics
- Throughput: {tp:.2} tok/s
- TTFT: {ttft:.2} ms
- Total Duration: {dur:.2} ms
- Tokens Generated: {tokens}
- Prompt Eval: {prompt_eval:.2} ms
- Eval Duration: {eval:.2} ms
- Load Duration: {load:.2} ms

## Key Findings
{findings}

## Recommendations
{recs}

## Persona Prompt
```
{prompt}
```
"#,
        label = execution.config.label,
        report = execution.result.report_markdown,
        count = execution.result.benchmark_data_count,
        total = workflow.total_seconds,
        ing = workflow.ingest_seconds,
        analysis_s = workflow.analysis_seconds,
        report_s = workflow.report_seconds,
        data_summary = execution.result.data_summary.trim(),
        tp = agg.average_tokens_per_second,
        ttft = agg.average_ttft_ms,
        dur = agg.total_duration_ms,
        tokens = agg.total_tokens_generated,
        prompt_eval = agg.prompt_eval_duration_ms,
        eval = agg.eval_duration_ms,
        load = agg.load_duration_ms,
        findings = bullet_block(&analysis.key_findings),
        recs = bullet_block(&analysis.recommendations),
        prompt = execution.config.prompt,
    )
}

async fn save_run_artifacts(
    run_dir: &Path,
    collector: &AgentExecution,
    insight: &AgentExecution,
    summary: &RunSummary,
) -> Result<()> {
    fs::write(
        run_dir.join("collector_report.md"),
        generate_agent_report(collector),
    )
    .await?;
    fs::write(
        run_dir.join("insight_report.md"),
        generate_agent_report(insight),
    )
    .await?;
    fs::write(
        run_dir.join("combined_report.md"),
        build_combined_report(summary, collector, insight),
    )
    .await?;

    let metrics_json = serde_json::json!({
        "run_number": summary.run_number,
        "scenario": summary.scenario,
        "collector": collector,
        "insight": insight,
        "summary": summary,
    });
    fs::write(
        run_dir.join("metrics.json"),
        serde_json::to_string_pretty(&metrics_json)?,
    )
    .await?;
    Ok(())
}

async fn save_aggregate_summary(
    output_dir: &Path,
    scenario: Scenario,
    summaries: &[RunSummary],
    configs: &(AgentConfig, AgentConfig),
) -> Result<()> {
    let mut aggregate = HashMap::new();
    if summaries.is_empty() {
        aggregate.insert("average_throughput_delta", 0.0);
        aggregate.insert("average_ttft_delta_ms", 0.0);
        aggregate.insert("average_concurrency_speedup", 1.0);
        aggregate.insert("average_efficiency", 50.0);
    } else {
        aggregate.insert(
            "average_throughput_delta",
            summaries.iter().map(|s| s.throughput_delta).sum::<f64>() / summaries.len() as f64,
        );
        aggregate.insert(
            "average_ttft_delta_ms",
            summaries.iter().map(|s| s.ttft_delta_ms).sum::<f64>() / summaries.len() as f64,
        );
        aggregate.insert(
            "average_concurrency_speedup",
            summaries.iter().map(|s| s.concurrency_speedup).sum::<f64>() / summaries.len() as f64,
        );
        aggregate.insert(
            "average_efficiency",
            summaries.iter().map(|s| s.efficiency_percent).sum::<f64>() / summaries.len() as f64,
        );
    }

    let summary_json = serde_json::json!({
        "scenario": scenario.to_string(),
        "runs": summaries,
        "aggregate": aggregate,
        "agent_a": configs.0,
        "agent_b": configs.1,
        "generated_at": Utc::now(),
    });
    fs::write(
        output_dir.join("summary.json"),
        serde_json::to_string_pretty(&summary_json)?,
    )
    .await?;

    let summary_md = format!(
        r#"# Multi-Agent Summary ({scenario})

Runs: {count}
Average Throughput Δ: {tp:+.2} tok/s
Average TTFT Δ: {tt:+.2} ms
Average Speedup: {speed:.2}x
Average Efficiency: {eff:.1}%

## Agent Configurations
- Agent A: {config_a}
- Agent B: {config_b}
"#,
        scenario = scenario,
        count = summaries.len(),
        tp = *aggregate.get("average_throughput_delta").unwrap_or(&0.0),
        tt = *aggregate.get("average_ttft_delta_ms").unwrap_or(&0.0),
        speed = *aggregate.get("average_concurrency_speedup").unwrap_or(&1.0),
        eff = *aggregate.get("average_efficiency").unwrap_or(&50.0),
        config_a = configs.0.options.description(),
        config_b = configs.1.options.description(),
    );
    fs::write(output_dir.join("summary.md"), summary_md).await?;
    Ok(())
}

async fn async_main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .with_env_filter(EnvFilter::from_default_env())
        .with_target(false)
        .init();

    let args = Args::parse();
    let output_dir = Path::new(&args.output_dir);
    fs::create_dir_all(output_dir).await?;

    // Initialize HTTP client
    #[cfg(not(feature = "runtime-smol-1kb"))]
    let client = ReqwestClient::builder()
        .timeout(Duration::from_secs(300))
        .build()?;

    #[cfg(feature = "runtime-smol-1kb")]
    let client = Http1KBClient::new()?;

    let coordinator = ResourceCoordinator::new(2);
    let configs = build_agent_configs(&args);

    let mut summaries = Vec::new();
    for run in 1..=args.runs {
        info!(
            "Starting run {}/{} for scenario {}",
            run, args.runs, args.scenario
        );
        let run_dir = output_dir.join(format!("run_{run}"));
        fs::create_dir_all(&run_dir).await?;

        let start = Instant::now();

        #[cfg(any(feature = "runtime-tokio-default", feature = "runtime-async-std"))]
        let (collector, insight) = futures_util::try_join!(
            coordinator.with_permit(|| run_agent_once(&client, &configs.0)),
            coordinator.with_permit(|| run_agent_once(&client, &configs.1)),
        )?;

        #[cfg(feature = "runtime-tokio-localset")]
        let (collector, insight) = {
            let local = tokio::task::LocalSet::new();
            local
                .run_until(async {
                    tokio::try_join!(
                        coordinator.with_permit(|| run_agent_once(&client, &configs.0)),
                        coordinator.with_permit(|| run_agent_once(&client, &configs.1)),
                    )
                })
                .await?
        };

        #[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
        let (collector, insight) = futures_util::try_join!(
            coordinator.with_permit(|| run_agent_once(&client, &configs.0)),
            coordinator.with_permit(|| run_agent_once(&client, &configs.1)),
        )?;

        let wall = start.elapsed().as_secs_f64();
        let summary = summarize_run(run, args.scenario, &collector, &insight, wall);
        save_run_artifacts(&run_dir, &collector, &insight, &summary).await?;
        summaries.push(summary);
    }

    save_aggregate_summary(output_dir, args.scenario, &summaries, &configs).await?;

    println!(
        "Multi-agent benchmark complete. Results saved to {}",
        output_dir.display()
    );
    Ok(())
}

// Runtime-specific entry points
#[cfg(feature = "runtime-tokio-default")]
#[tokio::main]
async fn main() -> Result<()> {
    async_main().await
}

#[cfg(feature = "runtime-tokio-localset")]
#[tokio::main]
async fn main() -> Result<()> {
    async_main().await
}

#[cfg(feature = "runtime-async-std")]
#[async_std::main]
async fn main() -> Result<()> {
    async_main().await
}

#[cfg(any(feature = "runtime-smol", feature = "runtime-smol-1kb"))]
fn main() -> Result<()> {
    smol::block_on(async_main())
}
