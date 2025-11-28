$ModelDir = "data/models"
$ModelFilename = "gpt-oss-20b-derestricted-q4_k_m.gguf"
$HfRepo = "gghfez/gpt-oss-20b-Derestricted-Q4_K_M-GGUF"
$ModelfilePath = "Modelfile_gpt_oss"
$ModelName = "gpt-oss-20b"
$ModelPath = Join-Path $ModelDir $ModelFilename

# Ensure data/models directory exists
if (-not (Test-Path -Path $ModelDir)) {
    New-Item -ItemType Directory -Path $ModelDir | Out-Null
}

# Download model if not exists (or resume)
Write-Host "Checking/Downloading model..."
huggingface-cli download $HfRepo $ModelFilename --local-dir $ModelDir --local-dir-use-symlinks False

# Write Modelfile content (Harmony format for gpt-oss-20b)
$ModelfileContent = @"
FROM $ModelPath

# Harmony chat template for gpt-oss-20b (derestricted) on Ollama.
# Renders messages using the Harmony format the model was trained on.
TEMPLATE """<|start|>system<|message|>You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2024-06
Current date: 2025-06-28

Reasoning: high

# Valid channels: analysis, commentary, final. Channel must be included for every message.
Calls to these tools must go to the commentary channel: 'functions'.<|end|>
{{- if .System }}

<|start|>developer<|message|># Instructions

{{ .System }}<|end|>
{{- end }}
{{- if not .Messages }}
<|start|>user<|message|>{{ .Prompt }}<|end|>
{{- end }}
{{- range .Messages }}
{{- if eq .Role "system" }}

<|start|>system<|message|>{{ .Content }}<|end|>
{{- else if eq .Role "developer" }}

<|start|>developer<|message|>{{ .Content }}<|end|>
{{- else if eq .Role "user" }}

<|start|>user<|message|>{{ .Content }}<|end|>
{{- else if eq .Role "assistant" }}

<|start|>assistant<|channel|>final<|message|>{{ .Content }}<|end|>
{{- end }}
{{- end }}

<|start|>assistant"""

PARAMETER num_ctx 8192
PARAMETER temperature 1
PARAMETER top_p 1
PARAMETER stop "<|return|>"
PARAMETER stop "<|call|>"
"@

Set-Content -Path $ModelfilePath -Value $ModelfileContent

# Create Ollama model
Write-Host "Creating Ollama model '$ModelName'..."
ollama create $ModelName -f $ModelfilePath

Write-Host "Done. Run the model with: ollama run $ModelName"
