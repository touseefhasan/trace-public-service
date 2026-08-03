param(
    [string]$DataPath,
    [string]$PythonPath,
    [switch]$Public,
    [switch]$OpenBrowser,
    [string]$Username,
    [string]$Password,
    [string]$OllamaModel = "qwen3.5:4b",
    [int]$Port = 7860
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $DataPath) {
    $DataPath = Join-Path $repoRoot "211_Sample_Dataset.xlsx"
}
if (-not (Test-Path -LiteralPath $DataPath)) {
    throw "Dataset not found: $DataPath"
}

if (-not $PythonPath) {
    $bundledPython = Join-Path $env:USERPROFILE ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    $PythonPath = if (Test-Path -LiteralPath $bundledPython) {
        $bundledPython
    }
    else {
        "python"
    }
}

& $PythonPath -c "import gradio" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Gradio is not installed. Run: & `"$PythonPath`" -m pip install gradio"
}

if ([bool]$Username -ne [bool]$Password) {
    throw "Provide both -Username and -Password, or neither."
}

$env:PYTHONPATH = Join-Path $repoRoot "src"
$appArguments = @(
    "-m", "trace_engine.gradio_app",
    "--data", $DataPath,
    "--variant", "kg3",
    "--intent-classifier", "ollama",
    "--response-generator", "ollama",
    "--ollama-model", $OllamaModel,
    "--port", $Port
)
if ($Public) {
    $appArguments += "--share"
}
if ($OpenBrowser) {
    $appArguments += "--inbrowser"
}
if ($Username) {
    $appArguments += @("--username", $Username, "--password", $Password)
}

Write-Host "Starting TRACE. Keep this window and Ollama running." -ForegroundColor Cyan
if ($Public) {
    Write-Host "Gradio will print a temporary public URL below." -ForegroundColor Green
}
& $PythonPath @appArguments
