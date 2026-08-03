param(
    [string]$DataPath,
    [string]$PythonPath,
    [string]$Query,
    [ValidateSet("deterministic", "ollama")]
    [string]$IntentClassifier = "deterministic",
    [string]$OllamaModel = "qwen3.5:4b",
    [double]$OllamaTimeout = 120,
    [double]$ResponseTimeout = 240,
    [ValidateSet("list", "chat")]
    [string]$ResponseStyle = "list"
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
$responseGenerator = if ($ResponseStyle -eq "chat") { "ollama" } else { "none" }

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
        --intent-classifier $IntentClassifier `
        --ollama-model $OllamaModel `
        --ollama-timeout $OllamaTimeout `
        --response-generator $responseGenerator `
        --response-timeout $ResponseTimeout `
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

    if ($ResponseStyle -eq "chat") {
        Write-Host "TRACE RESPONSE" -ForegroundColor Green
        Write-Host $result.answer
        Write-Host "`nResponse source: $($result.response_source)"
        if ($result.response_error) {
            Write-Host "Generation fallback reason: $($result.response_error)" -ForegroundColor Yellow
        }
        Write-Host "Candidates examined: $($result.candidates_examined)"
        continue
    }

    Write-Host "RECOMMENDATIONS"
    $recommendations = @($result.recommendations)
    if (-not $recommendations) {
        Write-Host "No matching providers found." -ForegroundColor Yellow
    }
    else {
        for ($index = 0; $index -lt $recommendations.Count; $index++) {
            $provider = $recommendations[$index].provider
            Write-Host ""
            Write-Host "$($index + 1). $($provider.name)" -ForegroundColor Green
            Write-Host "   Provider ID : $($provider.provider_id)"
            if ($provider.organization -and $provider.organization -ne $provider.name) {
                Write-Host "   Organization: $($provider.organization)"
            }
            if ($provider.category) {
                Write-Host "   Category    : $($provider.category)"
            }
            if ($provider.address) {
                Write-Host "   Address     : $($provider.address)"
            }
            $location = @($provider.city, $provider.county, $provider.zipcode) |
                Where-Object { $_ }
            if ($location) {
                Write-Host "   Location    : $($location -join ', ')"
            }
            if ($provider.phone) {
                Write-Host "   Phone       : $($provider.phone)"
            }
            if ($provider.hours) {
                Write-Host "   Hours       : $($provider.hours)"
            }
            if ($provider.source_url) {
                Write-Host "   Source      : $($provider.source_url)"
            }
        }
    }

    Write-Host "Candidates examined: $($result.candidates_examined)"
}
