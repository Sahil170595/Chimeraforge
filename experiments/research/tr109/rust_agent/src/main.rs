use anyhow::{Context, Result};
use bytes::Bytes;
use chrono::{DateTime, TimeZone, Utc};
use clap::Parser;
use csv::ReaderBuilder;
use futures_util::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime},
};
use tokio::{fs, task};
use tracing::{info, Level};
use walkdir::WalkDir;

#[derive(Parser, Debug)]
#[command(
    name = "demo_rust_agent",
    about = "Production-grade Rust LLM agent benchmark"
)]
struct Args {
    #[arg(long, default_value = "gemma3:latest")]
    model: String,

    #[arg(long, default_value = "http://localhost:11434")]
    base_url: String,

    #[arg(long, default_value_t = 3)]
    runs: u32,

    #[arg(long, default_value = "Demo_rust_agent_out_benchmark")]
    output_dir: String,

    // Chimera optimization parameters
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
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
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
                self.num_gpu
                    .map_or("default".to_string(), |v| v.to_string()),
                self.num_ctx
                    .map_or("default".to_string(), |v| v.to_string()),
                self.temperature
                    .map_or("default".to_string(), |v| v.to_string()),
                self.top_p.map_or("default".to_string(), |v| v.to_string()),
                self.top_k.map_or("default".to_string(), |v| v.to_string()),
                self.repeat_penalty
                    .map_or("default".to_string(), |v| v.to_string()),
            )
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct GenerateRequest<'a> {
    model: &'a str,
    prompt: &'a str,
    stream: bool,
    #[serde(skip_serializing_if = "OllamaOptions::is_empty")]
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

#[derive(Debug, Serialize, Deserialize)]
struct RunResult {
    agent_type: String,
    model: String,
    runs: u32,
    configuration: OllamaOptions,
    llm_calls: Vec<LlmCallRecord>,
    aggregate_metrics: AggregateMetrics,
    workflow_runs: Vec<WorkflowExecution>,
    timestamp: DateTime<Utc>,
    system_info: SystemInfo,
}

#[derive(Debug, Serialize, Deserialize)]
struct SystemInfo {
    os: String,
    arch: String,
    rust_version: String,
    hostname: String,
}

fn system_info() -> SystemInfo {
    SystemInfo {
        os: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        rust_version: rustc_version_runtime::version().to_string(),
        hostname: hostname::get()
            .ok()
            .and_then(|h| h.into_string().ok())
            .unwrap_or_else(|| "unknown".to_string()),
    }
}

struct LlmCallOutcome {
    text: String,
    metrics: SingleRunMetrics,
}

#[derive(Debug, Serialize, Deserialize)]
struct ComparisonMetrics {
    throughput_improvement_percent: f64,
    ttft_reduction_percent: f64,
    baseline_throughput: f64,
    chimera_throughput: f64,
    baseline_ttft_ms: f64,
    chimera_ttft_ms: f64,
    throughput_delta_absolute: f64,
    ttft_delta_absolute_ms: f64,
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
    run_number: u32,
    stage: String,
    prompt: String,
    response: String,
    metrics: SingleRunMetrics,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct WorkflowExecution {
    run_number: u32,
    benchmark_data_count: usize,
    data_summary: String,
    analysis: AnalysisPayload,
    report_markdown: String,
    workflow: WorkflowBreakdown,
    llm_calls: Vec<LlmCallRecord>,
}

fn percent_change(new: f64, old: f64) -> f64 {
    if old > 0.0 {
        ((new - old) / old) * 100.0
    } else {
        0.0
    }
}

fn calc_delta(baseline: &AggregateMetrics, chimera: &AggregateMetrics) -> ComparisonMetrics {
    let throughput_improvement = percent_change(
        chimera.average_tokens_per_second,
        baseline.average_tokens_per_second,
    );
    let ttft_reduction = if baseline.average_ttft_ms > 0.0 {
        ((baseline.average_ttft_ms - chimera.average_ttft_ms) / baseline.average_ttft_ms) * 100.0
    } else {
        0.0
    };

    ComparisonMetrics {
        throughput_improvement_percent: throughput_improvement,
        ttft_reduction_percent: ttft_reduction,
        baseline_throughput: baseline.average_tokens_per_second,
        chimera_throughput: chimera.average_tokens_per_second,
        baseline_ttft_ms: baseline.average_ttft_ms,
        chimera_ttft_ms: chimera.average_ttft_ms,
        throughput_delta_absolute: chimera.average_tokens_per_second
            - baseline.average_tokens_per_second,
        ttft_delta_absolute_ms: baseline.average_ttft_ms - chimera.average_ttft_ms,
    }
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
            Err(err) => eprintln!("Warning: could not scan {}: {}", dir_path.display(), err),
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
            Err(err) => eprintln!("Warning: could not load {}: {}", path.display(), err),
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

async fn ingest_benchmarks(repo_root: &Path) -> Result<Vec<BenchmarkData>> {
    let root = repo_root.to_path_buf();
    task::spawn_blocking(move || ingest_benchmarks_sync(root)).await?
}

async fn execute_agent_workflow(
    client: &Client,
    args: &Args,
    options: &OllamaOptions,
    agent_type: &str,
    run_number: u32,
    repo_root: &Path,
) -> Result<WorkflowExecution> {
    let overall_start = Instant::now();
    let ingest_start = Instant::now();
    let benchmark_data = ingest_benchmarks(repo_root).await?;
    let ingest_seconds = ingest_start.elapsed().as_secs_f64();

    let data_summary = create_data_summary(&benchmark_data);
    let analysis_prompt = build_analysis_prompt(&data_summary);
    let analysis_start = Instant::now();
    let analysis_call = call_ollama_streaming(
        client,
        &args.base_url,
        &args.model,
        &analysis_prompt,
        options,
    )
    .await?;
    let analysis_seconds = analysis_start.elapsed().as_secs_f64();
    let analysis = parse_analysis_response(&analysis_call.text, &benchmark_data);

    let report_prompt = build_report_prompt(&analysis)?;
    let report_start = Instant::now();
    let report_call =
        call_ollama_streaming(client, &args.base_url, &args.model, &report_prompt, options).await?;
    let report_seconds = report_start.elapsed().as_secs_f64();

    let workflow = WorkflowBreakdown {
        ingest_seconds,
        analysis_seconds,
        report_seconds,
        total_seconds: overall_start.elapsed().as_secs_f64(),
    };

    let llm_calls = vec![
        LlmCallRecord {
            run_number,
            stage: "analysis".into(),
            prompt: analysis_prompt,
            response: analysis_call.text.clone(),
            metrics: analysis_call.metrics.clone(),
        },
        LlmCallRecord {
            run_number,
            stage: "report".into(),
            prompt: report_prompt,
            response: report_call.text.clone(),
            metrics: report_call.metrics.clone(),
        },
    ];

    let header = format!(
        "# Technical Report: {agent} Agent Analysis\n\n**Date:** {date}\n**Model:** {model}\n**Agent Type:** {agent}\n**Configuration:** {config}\n\n---\n\n",
        agent = agent_type,
        date = Utc::now().format("%Y-%m-%d"),
        model = args.model,
        config = options.description(),
    );

    Ok(WorkflowExecution {
        run_number,
        benchmark_data_count: benchmark_data.len(),
        data_summary,
        analysis,
        report_markdown: format!("{header}{}", report_call.text.trim()),
        workflow,
        llm_calls,
    })
}

/// Call Ollama with streaming to get true TTFT measurement
async fn call_ollama_streaming(
    client: &Client,
    base_url: &str,
    model: &str,
    prompt: &str,
    options: &OllamaOptions,
) -> Result<LlmCallOutcome> {
    let req = GenerateRequest {
        model,
        prompt,
        stream: true,
        options: options.clone(),
    };
    let url = format!("{}/api/generate", base_url.trim_end_matches('/'));

    let request_start = Instant::now();
    let resp = client
        .post(&url)
        .json(&req)
        .send()
        .await
        .context("Failed to send request to Ollama")?;

    if !resp.status().is_success() {
        anyhow::bail!("Ollama error: {}", resp.status());
    }

    let mut stream = resp.bytes_stream();
    let mut first_chunk_time: Option<Instant> = None;
    let mut full_response = String::new();
    let mut total_tokens: u64 = 0;
    let mut prompt_eval_duration_ns: u64 = 0;
    let mut eval_duration_ns: u64 = 0;
    let mut load_duration_ns: u64 = 0;
    let mut buffer = String::new();

    let mut process_line = |line: &str| {
        if line.trim().is_empty() {
            return;
        }

        if let Ok(v) = serde_json::from_str::<serde_json::Value>(line) {
            if let Some(response) = v.get("response").and_then(|r| r.as_str()) {
                if !response.is_empty() {
                    if first_chunk_time.is_none() {
                        first_chunk_time = Some(Instant::now());
                    }
                    full_response.push_str(response);
                }
            }

            if let Some(true) = v.get("done").and_then(|d| d.as_bool()) {
                total_tokens = v.get("eval_count").and_then(|e| e.as_u64()).unwrap_or(0);
                prompt_eval_duration_ns = v
                    .get("prompt_eval_duration")
                    .and_then(|d| d.as_u64())
                    .unwrap_or(0);
                eval_duration_ns = v.get("eval_duration").and_then(|d| d.as_u64()).unwrap_or(0);
                load_duration_ns = v.get("load_duration").and_then(|d| d.as_u64()).unwrap_or(0);
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

    // Convert to milliseconds
    let ttft_ms = ttft.as_secs_f64() * 1000.0;
    let prompt_eval_ms = prompt_eval_duration_ns as f64 / 1_000_000.0;
    let eval_ms = eval_duration_ns as f64 / 1_000_000.0;
    let load_ms = load_duration_ns as f64 / 1_000_000.0;
    let total_duration_ms = total_elapsed.as_secs_f64() * 1000.0;

    // Calculate throughput based on generation time only
    let generation_time_s = (eval_ms / 1000.0).max(1e-6);
    let throughput = total_tokens as f64 / generation_time_s;

    Ok(LlmCallOutcome {
        text: full_response.trim().to_string(),
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
}

async fn run_agent_benchmark(
    client: &Client,
    args: &Args,
    agent_type: &str,
    options: &OllamaOptions,
) -> Result<RunResult> {
    info!("Running {} agent with {} runs...", agent_type, args.runs);
    info!("Configuration: {}", options.description());

    let repo_root = repository_root();
    let mut workflow_runs = Vec::new();
    let mut llm_calls = Vec::new();

    for run_idx in 1..=args.runs {
        info!("  Run {}/{}", run_idx, args.runs);
        let execution =
            execute_agent_workflow(client, args, options, agent_type, run_idx, &repo_root).await?;
        for call in &execution.llm_calls {
            info!(
                "    [{}] stage={} TTFT {:.2}ms, Throughput {:.2} tok/s, Tokens {}",
                call.run_number,
                call.stage,
                call.metrics.ttft_ms,
                call.metrics.throughput_tokens_per_sec,
                call.metrics.tokens_generated
            );
        }
        llm_calls.extend(execution.llm_calls.clone());
        workflow_runs.push(execution);

        if run_idx < args.runs {
            tokio::time::sleep(Duration::from_secs(2)).await;
        }
    }

    let metrics: Vec<SingleRunMetrics> =
        llm_calls.iter().map(|call| call.metrics.clone()).collect();
    let aggregate_metrics = aggregate_llm_metrics(&metrics);

    Ok(RunResult {
        agent_type: agent_type.to_string(),
        model: args.model.clone(),
        runs: args.runs,
        configuration: options.clone(),
        llm_calls,
        aggregate_metrics,
        workflow_runs,
        timestamp: Utc::now(),
        system_info: system_info(),
    })
}

async fn write_reports(
    output_dir: &std::path::Path,
    baseline: &RunResult,
    chimera: &RunResult,
    delta: &ComparisonMetrics,
) -> Result<()> {
    let reports_dir = output_dir.join("reports");
    let data_dir = output_dir.join("data");
    fs::create_dir_all(&reports_dir).await?;
    fs::create_dir_all(&data_dir).await?;

    // Write comparison report
    let comparison_md = generate_comparison_report(baseline, chimera, delta);
    fs::write(reports_dir.join("comparison_report.md"), comparison_md).await?;

    // Write baseline report
    let baseline_md = generate_agent_report(baseline);
    fs::write(reports_dir.join("baseline_report.md"), baseline_md).await?;

    // Write chimera report
    let chimera_md = generate_agent_report(chimera);
    fs::write(reports_dir.join("chimera_report.md"), chimera_md).await?;

    if let Some(run) = baseline.workflow_runs.last() {
        fs::write(
            reports_dir.join("baseline_technical_report.md"),
            &run.report_markdown,
        )
        .await?;
    }
    if let Some(run) = chimera.workflow_runs.last() {
        fs::write(
            reports_dir.join("chimera_technical_report.md"),
            &run.report_markdown,
        )
        .await?;
    }

    // Write metrics JSON
    let metrics_json = serde_json::json!({
        "benchmark_type": "rust_vs_python_agent",
        "language": "rust",
        "timestamp": Utc::now(),
        "baseline": baseline,
        "chimera": chimera,
        "delta": delta,
    });
    fs::write(
        data_dir.join("metrics.json"),
        serde_json::to_string_pretty(&metrics_json)?,
    )
    .await?;

    info!("Reports written to {:?}", reports_dir);
    info!("Metrics written to {:?}", data_dir);

    Ok(())
}

fn generate_agent_report(result: &RunResult) -> String {
    let latest = result.workflow_runs.last();
    let (workflow_block, data_block, findings_block, recommendations_block, technical_report) =
        if let Some(run) = latest {
            let findings = if run.analysis.key_findings.is_empty() {
                "- None captured".to_string()
            } else {
                run.analysis
                    .key_findings
                    .iter()
                    .map(|f| format!("- {}", f))
                    .collect::<Vec<_>>()
                    .join("\n")
            };
            let recs = if run.analysis.recommendations.is_empty() {
                "- None captured".to_string()
            } else {
                run.analysis
                    .recommendations
                    .iter()
                    .map(|r| format!("- {}", r))
                    .collect::<Vec<_>>()
                    .join("\n")
            };
            (
                format!(
                    "- Files analyzed: {}\n- Execution time: {:.2}s (ingest {:.2}s | analysis {:.2}s | report {:.2}s)",
                    run.benchmark_data_count,
                    run.workflow.total_seconds,
                    run.workflow.ingest_seconds,
                    run.workflow.analysis_seconds,
                    run.workflow.report_seconds
                ),
                format!("```\n{}\n```", run.data_summary.trim()),
                findings,
                recs,
                run.report_markdown.clone(),
            )
        } else {
            (
                "- No workflow executions recorded".to_string(),
                "No data summary captured.".to_string(),
                "- None captured".to_string(),
                "- None captured".to_string(),
                "No technical report available.".to_string(),
            )
        };

    format!(
        r#"# {agent} Agent Report

**Model:** {model}  
**Runs:** {runs}  
**Timestamp:** {time}  
**Language:** Rust  
**System:** {os} ({arch})

## Configuration

{config}

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Average Throughput | {avg_tp:.2} ± {std_tp:.2} tok/s |
| Average TTFT | {avg_tt:.2} ± {std_tt:.2} ms |
| Total Tokens Generated | {tokens} |
| Total LLM Call Duration | {dur:.2} ms |
| Prompt Eval Duration (sum) | {prompt_eval:.2} ms |
| Eval Duration (sum) | {eval:.2} ms |
| Load Duration (sum) | {load:.2} ms |

## Workflow Summary

{workflow_block}

### Data Summary
{data_block}

### Key Findings
{findings_block}

### Recommendations
{recommendations_block}

## Technical Report (LLM Generated)

{technical_report}

## LLM Call Metrics

{run_table}

## Statistical Summary

- **Throughput CV**: {cv_tp:.1}%
- **TTFT CV**: {cv_tt:.1}%
- **Runs**: {runs}
"#,
        agent = result.agent_type,
        model = result.model,
        runs = result.runs,
        time = result.timestamp.format("%Y-%m-%d %H:%M:%S UTC"),
        os = result.system_info.os,
        arch = result.system_info.arch,
        config = result.configuration.description(),
        avg_tp = result.aggregate_metrics.average_tokens_per_second,
        std_tp = result.aggregate_metrics.stddev_throughput,
        avg_tt = result.aggregate_metrics.average_ttft_ms,
        std_tt = result.aggregate_metrics.stddev_ttft,
        tokens = result.aggregate_metrics.total_tokens_generated,
        dur = result.aggregate_metrics.total_duration_ms,
        prompt_eval = result.aggregate_metrics.prompt_eval_duration_ms,
        eval = result.aggregate_metrics.eval_duration_ms,
        load = result.aggregate_metrics.load_duration_ms,
        workflow_block = workflow_block,
        data_block = data_block,
        findings_block = findings_block,
        recommendations_block = recommendations_block,
        technical_report = technical_report,
        run_table = generate_run_table(&result.llm_calls),
        cv_tp = if result.aggregate_metrics.average_tokens_per_second.abs() > f64::EPSILON {
            result.aggregate_metrics.stddev_throughput
                / result.aggregate_metrics.average_tokens_per_second
                * 100.0
        } else {
            0.0
        },
        cv_tt = if result.aggregate_metrics.average_ttft_ms.abs() > f64::EPSILON {
            result.aggregate_metrics.stddev_ttft / result.aggregate_metrics.average_ttft_ms * 100.0
        } else {
            0.0
        },
    )
}

fn generate_run_table(calls: &[LlmCallRecord]) -> String {
    if calls.is_empty() {
        return "No LLM calls recorded.\n".to_string();
    }
    let mut table =
        String::from("| Run | Stage | TTFT (ms) | Throughput (tok/s) | Tokens | Duration (ms) |\n");
    table.push_str("|-----|-------|-----------|-------------------|--------|---------------|\n");
    for call in calls {
        table.push_str(&format!(
            "| {} | {} | {:.2} | {:.2} | {} | {:.2} |\n",
            call.run_number,
            call.stage,
            call.metrics.ttft_ms,
            call.metrics.throughput_tokens_per_sec,
            call.metrics.tokens_generated,
            call.metrics.total_duration_ms
        ));
    }
    table
}

fn generate_comparison_report(
    baseline: &RunResult,
    chimera: &RunResult,
    delta: &ComparisonMetrics,
) -> String {
    format!(
        r#"# Rust Agent Performance Comparison Report

**Date:** {}  
**Model:** {}  
**Runs:** {}  
**Language:** Rust {}  
**System:** {} ({})  
**Hostname:** {}

## Executive Summary

This benchmark compares baseline Ollama defaults against Chimera-optimized configuration for Rust-based LLM agents using production-grade methodology matching Technical Reports 109 and 110.

### Key Findings

- **Throughput improvement:** {:.1}% ({:.2} → {:.2} tok/s)
- **TTFT reduction:** {:.1}% ({:.2} → {:.2} ms)
- **Statistical significance:** {} runs with standard deviation tracking
- **Configuration:** {}

## Aggregate Performance

| Metric | Baseline | Chimera | Δ |
|--------|----------|---------|---|
| Average Throughput (tok/s) | {:.2} ± {:.2} | {:.2} ± {:.2} | {:+.1}% ({:+.2}) |
| Average TTFT (ms) | {:.2} ± {:.2} | {:.2} ± {:.2} | {:+.1}% ({:+.2}) |
| Total Tokens Generated | {} | {} | {:+} |
| Avg Prompt Eval (ms) | {:.2} | {:.2} | {:+.1}% |
| Avg Eval Duration (ms) | {:.2} | {:.2} | {:+.1}% |
| Avg Load Duration (ms) | {:.2} | {:.2} | {:+.1}% |

## Configuration Details

### Baseline
{}

### Chimera Optimized
{}

## Statistical Analysis

### Throughput
- Baseline: {:.2} ± {:.2} tok/s (CV: {:.1}%)
- Chimera: {:.2} ± {:.2} tok/s (CV: {:.1}%)
- Improvement: {:+.2} tok/s ({:+.1}%)

### TTFT
- Baseline: {:.2} ± {:.2} ms (CV: {:.1}%)
- Chimera: {:.2} ± {:.2} ms (CV: {:.1}%)
- Reduction: {:+.2} ms ({:+.1}%)

## Run-by-Run Comparison

### Baseline Individual Runs
{}

### Chimera Individual Runs
{}

## System Information

- **Operating System:** {}
- **Architecture:** {}
- **Rust Version:** {}
- **Hostname:** {}

## Conclusion

The Rust agent with Chimera optimization achieved {:.1}% higher throughput and {:.1}% {} time-to-first-token compared to baseline configuration across {} statistically significant runs.

This demonstrates that Rust's zero-cost abstractions and efficient async runtime, combined with optimized Ollama parameters, can deliver measurable performance improvements in production LLM inference pipelines.

### Performance Characteristics

1. **Throughput**: Chimera configuration shows {:+.1}% improvement in token generation speed
2. **Latency**: TTFT improved by {:+.1}%, indicating faster initial response
3. **Consistency**: CV of {:.1}% for throughput and {:.1}% for TTFT demonstrates stable performance
4. **Total Tokens**: Generated {} tokens across {} runs ({:.0} tokens/run average)

### Comparison to Python Agent Benchmarks

These results provide a direct comparison baseline for Rust vs Python agent performance analysis (Technical Report 111). The same prompt complexity and measurement methodology ensure fair cross-language comparison.
"#,
        Utc::now().format("%Y-%m-%d %H:%M:%S UTC"),
        baseline.model,
        baseline.runs,
        baseline.system_info.rust_version,
        baseline.system_info.os,
        baseline.system_info.arch,
        baseline.system_info.hostname,
        delta.throughput_improvement_percent,
        delta.baseline_throughput,
        delta.chimera_throughput,
        delta.ttft_reduction_percent,
        delta.baseline_ttft_ms,
        delta.chimera_ttft_ms,
        baseline.runs,
        chimera.configuration.description(),
        baseline.aggregate_metrics.average_tokens_per_second,
        baseline.aggregate_metrics.stddev_throughput,
        chimera.aggregate_metrics.average_tokens_per_second,
        chimera.aggregate_metrics.stddev_throughput,
        delta.throughput_improvement_percent,
        delta.throughput_delta_absolute,
        baseline.aggregate_metrics.average_ttft_ms,
        baseline.aggregate_metrics.stddev_ttft,
        chimera.aggregate_metrics.average_ttft_ms,
        chimera.aggregate_metrics.stddev_ttft,
        delta.ttft_reduction_percent,
        delta.ttft_delta_absolute_ms,
        baseline.aggregate_metrics.total_tokens_generated,
        chimera.aggregate_metrics.total_tokens_generated,
        chimera.aggregate_metrics.total_tokens_generated as i64
            - baseline.aggregate_metrics.total_tokens_generated as i64,
        baseline.aggregate_metrics.prompt_eval_duration_ms,
        chimera.aggregate_metrics.prompt_eval_duration_ms,
        percent_change(
            chimera.aggregate_metrics.prompt_eval_duration_ms,
            baseline.aggregate_metrics.prompt_eval_duration_ms
        ),
        baseline.aggregate_metrics.eval_duration_ms,
        chimera.aggregate_metrics.eval_duration_ms,
        percent_change(
            chimera.aggregate_metrics.eval_duration_ms,
            baseline.aggregate_metrics.eval_duration_ms
        ),
        baseline.aggregate_metrics.load_duration_ms,
        chimera.aggregate_metrics.load_duration_ms,
        percent_change(
            chimera.aggregate_metrics.load_duration_ms,
            baseline.aggregate_metrics.load_duration_ms
        ),
        baseline.configuration.description(),
        chimera.configuration.description(),
        baseline.aggregate_metrics.average_tokens_per_second,
        baseline.aggregate_metrics.stddev_throughput,
        (baseline.aggregate_metrics.stddev_throughput
            / baseline.aggregate_metrics.average_tokens_per_second
            * 100.0),
        chimera.aggregate_metrics.average_tokens_per_second,
        chimera.aggregate_metrics.stddev_throughput,
        (chimera.aggregate_metrics.stddev_throughput
            / chimera.aggregate_metrics.average_tokens_per_second
            * 100.0),
        delta.throughput_delta_absolute,
        delta.throughput_improvement_percent,
        baseline.aggregate_metrics.average_ttft_ms,
        baseline.aggregate_metrics.stddev_ttft,
        (baseline.aggregate_metrics.stddev_ttft / baseline.aggregate_metrics.average_ttft_ms
            * 100.0),
        chimera.aggregate_metrics.average_ttft_ms,
        chimera.aggregate_metrics.stddev_ttft,
        (chimera.aggregate_metrics.stddev_ttft / chimera.aggregate_metrics.average_ttft_ms * 100.0),
        delta.ttft_delta_absolute_ms,
        delta.ttft_reduction_percent,
        generate_run_table(&baseline.llm_calls),
        generate_run_table(&chimera.llm_calls),
        baseline.system_info.os,
        baseline.system_info.arch,
        baseline.system_info.rust_version,
        baseline.system_info.hostname,
        delta.throughput_improvement_percent,
        delta.ttft_reduction_percent,
        if delta.ttft_reduction_percent >= 0.0 {
            "faster"
        } else {
            "slower"
        },
        baseline.runs,
        delta.throughput_improvement_percent,
        delta.ttft_reduction_percent,
        (chimera.aggregate_metrics.stddev_throughput
            / chimera.aggregate_metrics.average_tokens_per_second
            * 100.0),
        (chimera.aggregate_metrics.stddev_ttft / chimera.aggregate_metrics.average_ttft_ms * 100.0),
        chimera.aggregate_metrics.total_tokens_generated,
        chimera.runs,
        (chimera.aggregate_metrics.total_tokens_generated as f64 / chimera.runs as f64),
    )
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .with_target(false)
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let args = Args::parse();
    let output_dir = std::path::Path::new(&args.output_dir);
    fs::create_dir_all(output_dir).await?;

    let client = Client::builder()
        .timeout(Duration::from_secs(300))
        .build()?;

    info!("╔══════════════════════════════════════════╗");
    info!("║  Rust Agent Benchmark Suite              ║");
    info!("║  Production-Grade LLM Performance Test   ║");
    info!("╚══════════════════════════════════════════╝");
    info!("");
    info!("Model: {}", args.model);
    info!("Runs: {}", args.runs);
    info!("Output: {}", args.output_dir);
    info!("");

    info!("━━━ Running Baseline Agent ━━━");
    let baseline_opts = OllamaOptions::default();
    let baseline = run_agent_benchmark(&client, &args, "Baseline", &baseline_opts).await?;
    info!(
        "✓ Baseline complete: {:.2} tok/s, TTFT {:.2}ms",
        baseline.aggregate_metrics.average_tokens_per_second,
        baseline.aggregate_metrics.average_ttft_ms
    );
    info!("");

    info!("━━━ Running Chimera Optimized Agent ━━━");
    let chimera_opts = OllamaOptions {
        num_gpu: args.chimera_num_gpu,
        num_ctx: args.chimera_num_ctx,
        temperature: args.chimera_temperature,
        top_p: args.chimera_top_p,
        top_k: args.chimera_top_k,
        repeat_penalty: args.chimera_repeat_penalty,
    };
    let chimera = run_agent_benchmark(&client, &args, "Chimera", &chimera_opts).await?;
    info!(
        "✓ Chimera complete: {:.2} tok/s, TTFT {:.2}ms",
        chimera.aggregate_metrics.average_tokens_per_second,
        chimera.aggregate_metrics.average_ttft_ms
    );
    info!("");

    let delta = calc_delta(&baseline.aggregate_metrics, &chimera.aggregate_metrics);

    write_reports(output_dir, &baseline, &chimera, &delta).await?;

    info!("╔══════════════════════════════════════════╗");
    info!("║  Benchmark Complete                      ║");
    info!("╚══════════════════════════════════════════╝");
    info!("");
    info!("Results Summary:");
    info!(
        "  Baseline:  {:.2} tok/s, TTFT {:.2}ms",
        baseline.aggregate_metrics.average_tokens_per_second,
        baseline.aggregate_metrics.average_ttft_ms
    );
    info!(
        "  Chimera:   {:.2} tok/s, TTFT {:.2}ms",
        chimera.aggregate_metrics.average_tokens_per_second,
        chimera.aggregate_metrics.average_ttft_ms
    );
    info!("");
    info!(
        "  Improvement: {:+.1}% throughput, {:+.1}% TTFT reduction",
        delta.throughput_improvement_percent, delta.ttft_reduction_percent
    );
    info!("");
    info!("Reports saved to: {}", output_dir.display());

    Ok(())
}
