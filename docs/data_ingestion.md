# Data ingestion and normalization

TRACE accepts CSV, JSON, and XLSX directories. XLSX ingestion reads the first
worksheet and expects a header row followed by service records.

## Canonical model

Every source is converted to a `ServiceProvider` record. The canonical fields
include:

- identity: `provider_id`, `name`, and `organization`;
- service information: `description`, `category`, `application_process`,
  `required_documents`, `fees`, and `eligibility`;
- contact information: `phone`, `email`, and `source_url`;
- location: raw `address`, derived or supplied `city`, `state`, `county`, and
  `zipcode`;
- availability and provenance: `hours`, `last_verified_at`, and
  `location_source`.

Only `provider_id` and `name` are universally required after source adaptation.
Missing geographic fields remain empty.

## 211 workbook adapter

The adapter recognizes a workbook containing `Name`, `Organization`, and
`Category (Auto)`. It maps the remaining 211 headers as follows:

| Workbook column | Canonical field |
| --- | --- |
| `Name` | `name` |
| `Organization` | `organization` |
| `Description` | `description` |
| `Application Process` | `application_process` |
| `Required Documents` | `required_documents` |
| `Fees` | `fees` |
| `Email` | `email` |
| `Phones` | `phone` |
| `Mailing Address` | `address` |
| `County` | `county` |
| `Service Page URL` | `source_url` and, when possible, `provider_id` |
| `Hours` | `hours` |
| `Category (Auto)` | `category` |

The numeric 211 item ID embedded in `Service Page URL` becomes an ID such as
`211-1753`. If no source ID is available, TRACE creates a deterministic hash
from the service name, organization, and source URL.

## Location precedence

TRACE preserves the raw mailing address and applies these rules:

1. Use explicit city, state, and ZIP fields when present.
2. Fill missing components from a terminal `City, ST ZIP` address pattern.
3. Normalize ZIP+4 values to the five-digit retrieval ZIP.
4. Use the explicit county field and normalize a trailing `County`.
5. Do not infer a missing county from a city or ZIP.
6. Do not invent location values when an address is absent or unparseable.

`location_source` records whether the normalized location was `provided`,
`parsed`, `provided+parsed`, or `missing`.

The mailing address may not be the physical service-delivery location. A future
service-area adapter should model delivery areas separately instead of treating
the mailing address as authoritative coverage.

## Category behavior

When a category column is available, categories become structural KG
constraints. The deterministic parser maps common user language such as
`shelter`, `groceries`, `dental`, and `transportation` to the canonical
categories present in the loaded directory.

Legacy pantry schemas without a category are assigned `Food`, preserving the
published pantry retrieval behavior.
