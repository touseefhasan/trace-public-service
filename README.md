# TRACE Public-Service Retrieval Engine

TRACE is a deterministic, constraint-aware retrieval engine for food-pantry
directories. This repository contains the implementation before LLM integration, i.e., only the 'retrieval' part:

- A deterministic parser for pantry name, city, county, ZIP code, weekday,
  opening time, and ID-related eligibility constraints.
- Explicit knowledge graphs (KGs) with typed nodes, edges, properties, indexes, and
  graph traversal for the KG-1, KG-2, and KG-3 ablations.
- Normalization of free-form hours into day/time intervals.
- Batched candidate retrieval followed by semantic filtering.
- Clarification for queries that lack a usable structural constraint.
- A validated 1,000-query benchmark.

## What is not implemented yet

This milestone is not yet a natural-language chatbot. It has no LLM provider,
prompting layer, embeddings, vector index, generated prose, conversation
memory, HTTP API, or web UI. Its token-overlap score is a deterministic ranking
signal, not an embedding similarity or confidence probability. See
[`docs/pre-llm-status.md`](docs/pre-llm-status.md) for the exact integration
boundary and next work.

## Architecture at a glance

```mermaid
flowchart LR
    S["CSV or JSON directory"] --> I["Schema adapter and normalization"]
    I --> P["Typed Pantry records"]
    P --> G["KG-1 / KG-2 / KG-3 property graph"]
    Q["User query"] --> C["Deterministic constraint parser"]
    C --> X{"Structural constraint?"}
    X -- No --> CL["Clarification"]
    X -- Yes --> T["Typed graph traversal"]
    G --> T
    T --> R["Text-ranked candidates"]
    R --> E["Eligibility evidence check"]
    E --> O["Grounded structured result"]
```

The graph is not a label for field filtering. Query execution resolves graph
nodes, traverses typed incoming edges, intersects provider-ID sets using strict
AND semantics, and ranks only the resulting candidates. Full design details
are in [`docs/architecture.md`](docs/architecture.md) and
[`docs/knowledge_graph.md`](docs/knowledge_graph.md).

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

If Windows opens the Microsoft Store or reports that `python` was not found,
use the Python launcher (`py -3.11`) in place of `python`. In a Codex desktop
workspace, the bundled Python executable reported by the workspace runtime can
also be used directly.

Run all tests:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Inspect the sample graph:

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  graph --variant kg3
```

Use the original Kansas export without modifying or copying it:

```powershell
python -m trace_engine.cli `
  --data "C:\path\to\KS Pantries.csv" `
  ask "Which pantries in Sedgwick County are open Saturday at 10am?" `
  --variant kg3 --limit 3
```

See [`docs/cli.md`](docs/cli.md) for every command and an explanation of the
JSON response.

## Retrieval variants

| Variant | Graph-backed exact constraints | Candidate ranking |
| --- | --- | --- |
| `kg0` | None | Text overlap across the full directory |
| `kg1` | Pantry name and location | Text overlap within graph-selected location matches |
| `kg2` | Pantry name and operating hours | Text overlap within graph-selected schedule matches |
| `kg3` | Pantry name, location, and operating hours | Text overlap within the intersection of all graph constraints |

## Reproducing the benchmark

The repository contains an evaluation-ready 1,000-query JSONL derivative. The
full 811-row source directory is deliberately not redistributed; point the CLI
at your authorized local copy:

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

## Documentation map

- [`docs/architecture.md`](docs/architecture.md): components and end-to-end data flow.
- [`docs/knowledge_graph.md`](docs/knowledge_graph.md): graph schema, traversal, and hours coverage.
- [`docs/pre-llm-status.md`](docs/pre-llm-status.md): completed work, limitations, and LLM handoff.
- [`docs/cli.md`](docs/cli.md): commands, output fields, and troubleshooting.
- [`docs/reproducibility.md`](docs/reproducibility.md): clean-room verification procedure.
- [`data/README.md`](data/README.md): accepted schemas and source-data policy.
- [`benchmarks/README.md`](benchmarks/README.md): benchmark derivation and validation.
- [`reports/baseline.md`](reports/baseline.md): current real-data results.
