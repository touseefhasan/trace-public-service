# Data

The engine accepts either its normalized provider schema or the original Kansas
Food Source research-export schema.

## Kansas source schema

The supplied `KS Pantries.csv` contains 811 provider rows with these columns:

`pid`, `pantry_name`, `address_cleaned`, `zipcode`, `city`, `county`, `phone`,
`hours`, and `other_info`.

At load time the adapter:

- preserves `pid` as the stable provider ID;
- removes the `County, Kansas` suffix from county names;
- retains the scraped hours and eligibility text verbatim;
- extracts the first absolute or Kansas Food Source-relative URL as provenance;
- preserves ZIP codes as five-character identifiers; and
- does not modify the original CSV.

The inspected source has no missing IDs, names, addresses, ZIP codes, cities, or
counties and no duplicate IDs. It has four missing phone values, one missing
hours value, 154 blank `other_info` values, and 26 duplicated normalized pantry
names. Stable IDs must therefore be used for evaluation.

The full source CSV is not copied into this repository until its redistribution
terms and the repository data license are explicitly documented. The fictional
files under `data/sample/` are safe test fixtures.

The snapshot used for the baseline report has SHA-256
`6FA502894AEEEEC77F4A94E621CB268FC10711437A48EAA0CEC381613887904E`.
Use the hash to distinguish source revisions without publishing the file.
