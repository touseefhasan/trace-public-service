# Real-data retrieval baseline

This baseline was run on 2026-07-16 with Python 3.12.13. It uses the supplied
811-row `KS Pantries.csv`, the validated 1,000-query benchmark, and `k=3`. One
near-me query has no location context and is evaluated as a clarification case,
leaving 999 retrieval queries.

| Variant | P@3 | R@3 | F1@3 | Constraint satisfaction | Hallucination | Clarification accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| KG-0 | 0.171839 | 0.233901 | 0.189156 | 0.021021 | 0.000000 | 1.000000 |
| KG-1 | 0.577244 | 0.758926 | 0.630697 | 0.616617 | 0.000000 | 1.000000 |
| KG-2 | 0.170838 | 0.232399 | 0.187955 | 0.042042 | 0.000000 | 1.000000 |
| KG-3 | 0.484818 | 0.638805 | 0.529897 | 0.544545 | 0.000000 | 1.000000 |

Reproduction identifiers:

| Artifact | SHA-256 |
| --- | --- |
| Local `KS Pantries.csv` | `6FA502894AEEEEC77F4A94E621CB268FC10711437A48EAA0CEC381613887904E` |
| `synthetic_1000_source.jsonl` | `8EA80D72472315E05506E6616F6CCFAC95709F4A819FF26A92CF84104CEB0BA3` |
| `synthetic_1000.jsonl` | `5E256755AD0623D4F9D18F588A6EB4A276DC6996B47D4A2A710716383F3AAC3B` |

The exact command shape is:

```powershell
$env:PYTHONPATH = "src"
python -m trace_engine.cli `
  --data "C:\path\to\KS Pantries.csv" `
  evaluate --benchmark benchmarks/synthetic_1000.jsonl `
  --variant kg3 --k 3
```

These are implementation baselines, not a reproduction of the paper's reported
table. KG-1 currently scores highest because the workbook's top-answer lists are
primarily directory candidates selected by location. Some hours and combined
queries include gold providers whose hours are unavailable or inconsistent with
the requested day and time. KG-3 enforces the current conservative hours parser,
so those rows reduce its retrieval overlap.

The zero hallucination rate follows from structured output: every recommendation
contains a stable provider record loaded from the directory. It does not measure
free-form LLM generation yet.

## Required next experiment

Create separate labels for:

1. structural candidate relevance;
2. hours-constraint satisfaction;
3. eligibility evidence availability; and
4. response-generation grounding.

This will let the KG ablation and semantic filtering stages be evaluated against
the constraint they actually enforce instead of one shared candidate list.
