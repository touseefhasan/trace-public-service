# Local LLM intent classification

TRACE can use a local Ollama model to classify a query into one or more service
categories. The LLM improves intent understanding only; it does not select or
invent providers. KG traversal remains the source of grounded recommendations.

## Two-stage LLM pipeline

The optional LLM calls have separate responsibilities:

1. **Intent classification:** Qwen receives the query and the category taxonomy,
   then returns canonical categories and short evidence phrases. It does not see
   or select provider records.
2. **Response generation:** after deterministic KG retrieval and ranking, Qwen
   receives only the final provider records and rewrites those facts as a
   conversational answer. It cannot add candidates to the result.

TRACE requires every non-empty provider value supplied to the second call to
appear unchanged in its answer. An omitted or altered value triggers a fully
deterministic chat response, recorded as `deterministic_fallback`.

## Retrieval semantics

Multiple categories are alternatives within the category dimension and are
combined with other dimensions using strict intersection:

```text
(Housing & Shelter OR Mental Health & Addiction) AND city=Wichita
```

When the requested result limit is at least the number of selected categories,
TRACE places the highest-ranked candidate from each category before filling
remaining slots. This prevents one category from crowding the others out of the
displayed recommendations.

The JSON response retains `category` as the first label for compatibility and
adds:

- `categories`: all selected canonical labels;
- `category_source`: `ollama:<model>`, `deterministic`, or
  `deterministic_fallback`;
- `category_evidence`: short query phrases supporting the classification.

## Install and prepare Ollama

Install Ollama for Windows from <https://ollama.com/download/windows>, then open
a new PowerShell window and download the default model:

```powershell
ollama pull qwen3.5:4b
ollama list
```

The default model is approximately 3.4 GB. Another local model can be selected
with `--ollama-model`, although its classifications should be evaluated before
being used for benchmark results.

## Run one query

```powershell
$env:PYTHONPATH = Join-Path $PWD "src"

python -m trace_engine.cli `
  --data "C:\path\to\211_Sample_Dataset.xlsx" `
  ask "I need transitional housing and addiction recovery help in Wichita" `
  --variant kg3 `
  --intent-classifier ollama `
  --ollama-model "qwen3.5:4b" `
  --limit 5
```

The PowerShell test wrapper accepts the same mode:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\test_retrieval.ps1" `
  -DataPath "C:\path\to\211_Sample_Dataset.xlsx" `
  -Query "I need a ride to chemotherapy in Wichita" `
  -IntentClassifier ollama
```

Add `-ResponseStyle chat` to also run grounded response generation. The default
is `list`, which preserves the retrieval inspection output used in evaluation.
The response call has a separate 240-second default timeout because it produces
substantially more text; change it with `-ResponseTimeout` when needed.

## Failure behavior

If Ollama is stopped, the model is missing, the request times out, or the model
returns invalid output, TRACE uses its deterministic multi-label classifier.
The result records `category_source` as `deterministic_fallback`, allowing
evaluation code to distinguish actual LLM classifications from fallback runs.

The LLM output is constrained by a JSON Schema whose category enum is built
from categories present in the loaded directory. TRACE validates the response
again and discards labels outside that taxonomy.

Environment variables can change the defaults:

```powershell
$env:TRACE_OLLAMA_MODEL = "qwen3.5:4b"
$env:TRACE_OLLAMA_URL = "http://127.0.0.1:11434"
$env:TRACE_OLLAMA_TIMEOUT = "120"
```

Keep deterministic mode for a no-model baseline:

```powershell
python -m trace_engine.cli `
  --data "C:\path\to\211_Sample_Dataset.xlsx" `
  ask "Where can I get prenatal care in Wichita?" `
  --variant kg3 `
  --intent-classifier deterministic
```
