# Reproducibility

This procedure verifies the committed implementation without an API key or
network service.

## Environment

- Python 3.11 or newer.
- Windows PowerShell examples are shown; the commands are otherwise portable.
- No runtime third-party packages.
- The real-data benchmark additionally requires an authorized local copy of
  `KS Pantries.csv`.

## Clean verification

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m compileall -q src tests scripts
python -m unittest discover -s tests -v
python -c "from trace_engine.evaluation import load_benchmark; assert len(load_benchmark('benchmarks/synthetic_1000.jsonl')) == 1000"
```

## Sample smoke tests

```powershell
python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  ask "Find a pantry in Sedgwick County open Monday at 10am without ID" `
  --variant kg3

python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  graph --variant kg3

python -m trace_engine.cli `
  --data data/sample/pantries.csv `
  evaluate --benchmark benchmarks/sample.jsonl --variant kg3 --k 3
```

## Real-data checks

Set a local path without copying the source into this repository:

```powershell
$data = "C:\path\to\KS Pantries.csv"
python -m trace_engine.cli --data $data graph --variant kg3
python -m trace_engine.cli `
  --data $data `
  ask "Which pantries in Sedgwick County are open Saturday at 10am?" `
  --variant kg3 --limit 3
```

Regenerate the validated benchmark with that authorized source and confirm it
is byte-for-byte identical to the committed derivative:

```powershell
python scripts/validate_benchmark.py `
  --data $data `
  --source benchmarks/synthetic_1000_source.jsonl `
  --output work/synthetic_1000.validated.jsonl

$a = (Get-FileHash benchmarks/synthetic_1000.jsonl -Algorithm SHA256).Hash
$b = (Get-FileHash work/synthetic_1000.validated.jsonl -Algorithm SHA256).Hash
$a -eq $b
```

The final command should print `True` for the inspected source snapshot.

For the inspected 811-row export, KG-3 should report 2,446 nodes and 4,374
edges, including 1,130 `OPEN_ON` edges. A different source snapshot may produce
different counts and should be versioned separately.

Run each ablation:

```powershell
foreach ($variant in "kg0", "kg1", "kg2", "kg3") {
  python -m trace_engine.cli `
    --data $data evaluate `
    --benchmark benchmarks/synthetic_1000.jsonl `
    --variant $variant --k 3
}
```

Record the source file hash, Python version, repository commit, command, and
output when reporting results. Do not compare the numbers to a paper table
without also documenting benchmark-label policy and source snapshot.

## Continuous integration

The GitHub Actions workflow runs compilation, unit/integration tests, validates
that all 1,000 committed benchmark rows load, and executes sample CLI smoke
tests on Python 3.11 and 3.12. It does not use or upload the non-redistributed
Kansas directory. Full benchmark regeneration remains an explicit real-data
check.
