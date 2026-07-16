# Pre-LLM implementation status

This is the handoff checkpoint immediately before model integration.

## Complete

### Data layer

- Normalized CSV and JSON ingestion.
- Direct mapping of the 811-row Kansas Food Source research export.
- Stable-ID validation and preservation of raw hours/eligibility evidence.
- Fictional sample fixtures that can be safely committed and tested.

### Knowledge graphs

- Typed `Pantry`, `City`, `County`, `ZipCode`, `Hours`, and `Day` nodes.
- Typed location and schedule edges, including interval properties.
- Separate KG-1, KG-2, and KG-3 materializations.
- Indexed graph traversal and strict intersection of multiple constraints.
- JSON graph summaries and full graph export from the CLI.

### Retrieval and safety

- Deterministic constraint extraction for the supported query grammar.
- Directory-bounded candidate ranking with stable tie-breaking.
- Conservative time matching and evidence-backed ID eligibility checks.
- Batched filtering, structured recommendations, and source evidence.
- Clarification when location/name/day context is absent.
- Zero out-of-directory provider IDs by construction.

### Evaluation

- Conversion of 1,000 workbook queries to stable-ID JSONL.
- Duplicate-name disambiguation and validation of 2,451 populated gold slots.
- Repairs for 20 recall cases and clarification treatment for the single
  context-free near-me case.
- Precision, recall, F1, constraint-satisfaction, hallucination, and
  clarification metrics.
- Unit and integration coverage for ingestion, parsing, hours, graph traversal,
  engine behavior, and evaluation.

## Current limitations

- The parser supports a defined grammar; it is not a general natural-language
  understanding system.
- Semantic eligibility checking currently recognizes ID-related constraints
  and exact token subsets only.
- Ranking is lexical token overlap, not dense retrieval or reranking.
- `near me` has no geocoder, user location, or distance calculation.
- Ordinal schedules such as `4th Saturday` are represented as Saturday
  availability because queries do not yet carry a calendar date. Date-aware
  recurrence is a future requirement.
- Day-only schedules can support a day query but not an exact-time query.
- The directory lacks consistent `last_verified_at` values, so freshness cannot
  yet be ranked or guaranteed.
- The benchmark's top answers primarily describe directory candidates. Some
  hours/combined gold entries do not independently prove the requested hours,
  so the current baseline must not be presented as the paper's final result.
- The CLI emits JSON; there is no conversational presentation layer.

## LLM integration contract

The first model-backed version should add capabilities around the deterministic
core, not bypass it:

1. Produce a schema-validated `QueryConstraints` object. Reject or clarify
   ambiguous fields rather than inventing values.
2. Use the existing KG traversal for hard name/location/hours constraints.
3. Optionally use embeddings or a model reranker only within the allowed
   candidate set.
4. Pass only accepted `Recommendation` records and their evidence to response
   generation.
5. Require provider claims in generated prose to map back to an included record
   and source field.
6. Preserve a non-LLM execution mode for reproducibility and ablations.
7. Evaluate parser accuracy, grounding, latency, and cost separately from
   retrieval metrics.

## Recommended next sequence

1. Define JSON schemas for model-produced constraints and grounded responses.
2. Add a provider-neutral LLM adapter behind an optional dependency boundary.
3. Build an offline parser evaluation set, including ambiguity and refusal
   cases.
4. Add date-aware hours recurrence and geospatial constraints.
5. Separate benchmark labels for structural relevance, hours satisfaction,
   eligibility evidence, and response grounding.
6. Add an HTTP API and minimal chat UI only after the grounding checks are
   enforced at the response boundary.
