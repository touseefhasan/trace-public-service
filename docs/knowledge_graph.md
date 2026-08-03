# Knowledge-graph implementation

TRACE currently uses a deterministic in-memory property graph implemented in
Python. It does **not** use Neo4j, Cypher, RDF, a graph server, or a persistent
graph database. The graph is materialized from normalized provider records each
time a `TraceEngine` starts.

## Node types

| Node kind | Key properties | Purpose |
|---|---|---|
| `ServiceProvider` | `provider_id`, `name`, `normalized_name` | One node per directory record |
| `ServiceCategory` | `name`, `normalized_name` | Shared canonical service category |
| `City` | `name`, `normalized_name` | Shared city constraint |
| `County` | `name`, `normalized_name` | Shared county constraint |
| `ZipCode` | `value` | Shared ZIP-code constraint |
| `Hours` | `raw_text` | One operating-hours node per provider |
| `Day` | `name` | Shared normalized weekday |

## Edge types

```text
(ServiceProvider)-[:IN_CATEGORY]->(ServiceCategory)
(ServiceProvider)-[:LOCATED_IN_CITY]->(City)
(ServiceProvider)-[:LOCATED_IN_COUNTY]->(County)
(ServiceProvider)-[:LOCATED_IN_ZIPCODE]->(ZipCode)
(ServiceProvider)-[:HAS_HOURS]->(Hours)
(Hours)-[:OPEN_ON {start_minute, end_minute}]->(Day)
```

`OPEN_ON` carries normalized interval properties so a question such as “open
Saturday at 10am” can be checked as a graph constraint rather than a raw-text
match.

## How it participates in retrieval

The query parser first creates structured constraints. Graph traversal obtains
a provider-ID set for each applicable constraint. Multiple requested categories
are unioned with one another, while different dimensions are intersected:

```text
(Housing & Shelter OR Legal) AND city=Wichita AND open=Monday@10:00
```

Only providers surviving that graph operation enter lexical ranking and the
subsequent semantic checks. The optional LLM classifies categories before this
step and phrases the final answer after it; it does not alter graph edges or add
providers.

## Ablation variants

| Variant | Materialized constraints |
|---|---|
| `kg0` | No graph; lexical baseline |
| `kg1` | Provider name, category, city, county, and ZIP code |
| `kg2` | Provider name and operating hours |
| `kg3` | All KG-1 and KG-2 constraints |

The custom graph keeps experiments dependency-free and makes the ablations easy
to reproduce. Neo4j could later replace the storage/traversal layer for a much
larger or continuously updated directory, but it is not required for the current
dataset size.
