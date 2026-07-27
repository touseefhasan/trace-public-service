param(
    [string]$DataPath,
    [string]$PythonPath,
    [string]$Query
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $DataPath) {
    $DataPath = Join-Path $repoRoot "data/sample/pantries.csv"
}

if (-not $PythonPath) {
    $bundledPython = Join-Path $env:USERPROFILE ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    $PythonPath = if (Test-Path $bundledPython) { $bundledPython } else { "python" }
}

$env:PYTHONPATH = Join-Path $repoRoot "src"

# Pass -Query for one manual question. Without it, these examples are used.
$queries = if ($Query) {
    @($Query)
}
else {
    @(
        "Which pantries in Sedgwick County are open Saturday at 10am?",
        "Which pantries are in ZIP code 67114?",
        "I need food assistance"
    )
}

foreach ($query in $queries) {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "QUERY: $query" -ForegroundColor Cyan

    $json = & $PythonPath -m trace_engine.cli `
        --data $DataPath `
        ask $query `
        --variant kg3 `
        --limit 3

    if ($LASTEXITCODE -ne 0) {
        throw "Retrieval command failed for query: $query"
    }

    $result = ($json -join [Environment]::NewLine) | ConvertFrom-Json

    Write-Host "`nPARSED CONSTRAINTS"
    $result.constraints | Format-List

    if ($result.clarification) {
        Write-Host "CLARIFICATION: $($result.clarification)" -ForegroundColor Yellow
        continue
    }

    Write-Host "RECOMMENDATIONS"
    @($result.recommendations) |
        Select-Object `
            @{Name = "ProviderId"; Expression = { $_.provider.provider_id }},
            @{Name = "Name"; Expression = { $_.provider.name }},
            @{Name = "Category"; Expression = { $_.provider.category }},
            @{Name = "City"; Expression = { $_.provider.city }},
            @{Name = "County"; Expression = { $_.provider.county }},
            @{Name = "Hours"; Expression = { $_.provider.hours }},
            score |
        Format-Table -Wrap -AutoSize

    Write-Host "Candidates examined: $($result.candidates_examined)"
}
