# TRACE Public-Service Retrieval Engine

TRACE is a constraint-aware retrieval engine for food-pantry (ideally, any public-service)
directories. This repository contains the implementation before LLM integration, i.e., only the 'retrieval' part:

- A deterministic parser for pantry name, city, county, ZIP code, weekday,
  opening time, and ID-related eligibility constraints.
- Explicit knowledge graphs (KGs) with typed nodes, edges, properties, indexes, and
  graph traversal for the KG-1, KG-2, and KG-3 ablations.
- Normalization of free-form hours into day/time intervals.
- Batched candidate retrieval followed by semantic filtering.
- Location clarification when a query lacks a city, county, ZIP code, or named
  provider, plus weekday clarification when a time is supplied without a day.
- A validated 1,000-query benchmark.

Why hasn't LLM been integrated yet? Well...the key aspect of the TRACE framework is the retrieval process. Retrieval is the cornerstone! LLMs (and a full-fledged chatbot!) coming soon...

## Architecture at a glance

```mermaid
flowchart LR
    S["CSV or JSON directory"] --> I["Schema normalization"]
    I --> P["Pantry records"]
    P --> G["KG-1 / KG-2 / KG-3 property graph"]
    Q["User query"] --> C["Deterministic constraint parser"]
    C --> X{"City, county, ZIP, or pantry name?"}
    X -- No --> CL["Ask for location"]
    X -- Yes --> D{"Time has a weekday?"}
    D -- No --> CD["Ask for weekday"]
    D -- Yes --> T["KG traversal"]
    G --> T
    T --> R["Text-ranked candidates"]
    R --> E["Eligibility check"]
    E --> O["Structured result"]
```

## Quick start

Requirements: Python 3.11 or newer. The project has no runtime dependencies.

```powershell
cd trace-public-service
$env:PYTHONPATH = "src"
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  ask "Find a pantry in Sedgwick County open Monday at 10am without ID" `
  --variant kg3
```

If `python` is not found,
use the Python launcher (`py -3.11`) in place of `python`.

Run all tests:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Run a few basic retrieval queries from PowerShell (no LLM or API key):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_retrieval.ps1
```

Use an authorized local Kansas directory instead of the sample data:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_retrieval.ps1 `
  -DataPath "C:\path\to\KS Pantries.csv"
```

Edit the `$queries` array in the script to try other questions. The script
automatically locates Python in a Codex workspace; elsewhere, pass
`-PythonPath`. `-ExecutionPolicy Bypass` applies only to that new PowerShell
process and does not change the machine's saved policy.

Run one manual query:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_retrieval.ps1 `
  -DataPath "C:\path\to\KS Pantries.csv" `
  -Query "Which pantries in Sedgwick County are open Saturday at 10am?"
```

Inspect the sample graph:

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  graph --variant kg3
```

Use the original KansasFoodSource dataset without modifying or copying it:

```powershell
python -m trace_engine.cli `
  --data "C:\path\to\KS Pantries.csv" `
  ask "Which pantries in Sedgwick County are open Saturday at 10am?" `
  --variant kg3 --limit 3
```

## Retrieval (KG) variants

| Variant | Graph constraints |
| --- | --- |
| `kg0` | None |
| `kg1` | Pantry name and location |
| `kg2` | Pantry name and operating hours |
| `kg3` | Pantry name, location, and operating hours |

## Reproducing the benchmark

The repository contains a 1,000-query JSONL derivative for reproducing the benchmark.

```powershell
$env:PYTHONPATH = "src"
python scripts/validate_benchmark.py `
  --data "C:\path\to\KS Pantries.csv" `
  --source benchmarks/synthetic_1000_source.jsonl `
  --output work/synthetic_1000.validated.jsonl

python -m trace_engine.cli `
  --data "C:\path\to\KS Pantries.csv" `
  evaluate --benchmark benchmarks/synthetic_1000.jsonl --variant kg3 --k 3
```
