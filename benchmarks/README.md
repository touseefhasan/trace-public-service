# Benchmarks

`synthetic_1000_source.jsonl` is derived from the supplied workbook **Synthetic
Queries and Ground Truth - 1000.xlsx**. Each row preserves the workbook's query ID,
family, query text, structural-match count, and top-three pantry names. Pantry
names are additionally resolved to stable IDs from the supplied `KS Pantries.csv`.

The conversion validated all 1,000 unique query IDs and all 2,451 populated
ground-truth slots. Twenty-six pantry names occur more than once in the source
directory; 244 ground-truth slots using those names were disambiguated using the
address, city, county, and ZIP evidence in the workbook's `TopAnswers` field.
No slot remained unresolved.

The query-sheet family distribution is:

| Family | Rows |
| --- | ---: |
| Location only (`location`) | 489 |
| Eligibility (`eligibility`) | 200 |
| Open hours (`hours`) | 200 |
| Combined (`combined`) | 90 |
| Recall (`recall`) | 20 |
| Near me (`near_me`) | 1 |

This differs from the workbook's Overview sheet, which reports 500 location,
five near-me, and five recall queries. The JSONL preserves the labels from the
1,000-row query sheet because those labels are attached to the observations.

The workbook's top answers are directory-grounded candidates, but they should
not automatically be interpreted as proof that every hours or eligibility
condition is satisfied. For example, some hours queries list providers whose
hours are `Not available`. Retrieval evaluation and semantic constraint
evaluation therefore need separate ground-truth policies.

## Validated benchmark

`synthetic_1000.jsonl` is the evaluation-ready derivative produced by
`scripts/validate_benchmark.py`. The source workbook assigns all 20 recall rows
and its one near-me row the same first three directory entries with a structural
match count of 811. The validator:

- repairs each recall row to the unique pantry explicitly named in its query;
- treats the near-me row as an expected clarification and excludes it from
  retrieval precision/recall; and
- retains the replaced source fields and a validation note on every changed row.

No other query family's ground truth is changed.
