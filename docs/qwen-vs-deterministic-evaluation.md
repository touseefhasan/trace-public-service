# Deterministic vs. Qwen 3.5 4B Evaluation

## Protocol

- Benchmark: 83 CARE/211 queries.
- Taxonomy: 12 provider categories from the 211 dataset.
- Retrieval: KG-3, top 3 providers.
- Qwen: `qwen3.5:4b`, local Ollama, temperature 0, structured output.
- Provider evaluation: constraint satisfaction; provider IDs were not compared with the arbitrary gold top 3.
- Category labels remain provisional (`Needs Review`), so results are diagnostic rather than final publication claims.

## Category extraction

| Metric | Deterministic | Qwen | Qwen delta |
|---|---:|---:|---:|
| Exact match | 43.37% | 45.78% | +2.41 pp |
| Micro precision | 66.67% | 68.07% | +1.40 pp |
| Micro recall | 66.02% | 78.64% | +12.62 pp |
| Micro F1 | 66.34% | 72.97% | +6.63 pp |
| Macro F1 | 68.55% | 74.02% | +5.47 pp |
| Mean Jaccard | 56.12% | 63.76% | +7.63 pp |
| Multi-label exact match | 26.67% | 26.67% | 0.00 pp |

Paired exact-match outcomes: Qwen alone was correct on 9 queries, the deterministic
classifier alone was correct on 7, both were correct on 29, and neither was exact on 38.
Qwen therefore improves overall label coverage and recall, but does not improve the
strict multi-label exact-match result in this provisional benchmark.

## Downstream KG-3 retrieval

| Metric | Deterministic | Qwen | Qwen delta |
|---|---:|---:|---:|
| Recommendations | 177 | 178 | +1 |
| Provider category satisfaction | 57.06% | 61.80% | +4.74 pp |
| Provider strict hard satisfaction | 50.85% | 58.99% | +8.14 pp |
| Mean Need Coverage@3 | 52.21% | 57.43% | +5.22 pp |
| Full Need Coverage@3 | 46.99% | 51.81% | +4.82 pp |
| Strict Query Success@3 | 51.81% | 59.04% | +7.23 pp |
| No-result rate | 21.69% | 20.48% | -1.20 pp |
| Exact listed-location confirmation | 100.00% | 100.00% | 0.00 pp |

Need coverage improved on 12 queries, regressed on 6, and was unchanged on 65.
Category predictions changed on 44 queries, while provider counts changed on 11.

## Interpretation

Qwen improves recall, F1, Jaccard overlap, and most downstream constraint metrics.
The clearest gains occur on indirect or multi-concept needs, such as hearing aids for
seniors, expungement for employment, first-time homebuyer assistance, and combined
housing/financial/food needs.

The gain is not uniform. Qwen missed or replaced correct categories for some utility
assistance, supported living, senior activities, household goods, and domestic-violence
shelter queries. Empty category predictions can also cause broad location-only retrieval;
this may accidentally return a provider in the requested category and inflate downstream
coverage. Category extraction and retrieval metrics must therefore be reported together.

The strongest defensible conclusion is that Qwen is a better high-recall classifier than
the deterministic baseline, but it should be used in a hybrid design with deterministic
fallback/union logic and confidence or empty-output safeguards. Human review of the
provisional category annotations and provider semantic relevance remains necessary.

## Runtime caveat

Ollama reported no GPU offload (`size_vram: 0`). A representative sequential query took
62.5 seconds. The complete run used checkpointed concurrent CPU inference; cached scoring
latencies are not model latencies and must not be reported as such.
