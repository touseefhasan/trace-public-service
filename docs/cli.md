# Command-line interface

Run from the repository root with `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
python -m trace_engine.cli --data <directory> <command> [options]
```

`--data` is required for every command and accepts a CSV or JSON directory.

## `ask`

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  ask "Which pantries in Sedgwick County are open Saturday at 10am?" `
  --variant kg3 --limit 3 --batch-size 3
```

- `--variant`: `kg0`, `kg1`, `kg2`, or `kg3`; default `kg3`.
- `--limit`: maximum accepted recommendations; default 3.
- `--batch-size`: candidates retrieved before each evidence-check pass; default 3.

The JSON response includes:

- `query` and `variant`: the executed request and ablation.
- `constraints`: parsed name, location, day/time, and semantic constraints.
- `clarification`: a targeted question when the request lacks a city, county,
  ZIP code, or pantry-name anchor, or when a clock time lacks a weekday;
  otherwise `null`.
- `candidates_examined`: directory records checked before completion.
- `recommendations`: grounded records, matched constraints, evidence, and score.

The score is lexical token overlap divided by the number of query tokens. It is
useful for deterministic ordering but should not be read as probability.

## `list`

```powershell
python -m trace_engine.cli --data data/sample/pantries.csv list
```

Prints the normalized provider model. This is useful for validating a new
source adapter before testing retrieval.

## `graph`

Print only counts:

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv graph --variant kg3
```

Export nodes and edges:

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  graph --variant kg3 --output work/kg3.json
```

The export contains graph metadata, node IDs/kinds/properties, and typed edges.
KG-0 cannot be exported because it deliberately materializes no graph.

## `evaluate`

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  evaluate --benchmark benchmarks/sample.jsonl --variant kg3 --k 3
```

The evaluator reports macro-averaged precision, recall, and F1 at `k`, plus
constraint satisfaction, out-of-directory hallucination, and clarification
accuracy. See `benchmarks/README.md` before interpreting the 1,000-query
research derivative.

## Windows troubleshooting

If the command fails with `Python was not found`, Windows is invoking its
Microsoft Store execution alias. Try:

```powershell
py -3.11 -m trace_engine.cli --data data/sample/pantries.csv list
```

If neither `python` nor `py` is available, install Python 3.11+ or use the
Python executable supplied by your development environment. Keep the
`$env:PYTHONPATH = "src"` assignment in the same PowerShell session.

PowerShell's backtick is a line-continuation character and must be the final
character on the line. A command can always be written on one line instead.
