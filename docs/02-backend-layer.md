# Backend Layer — Trade-offs & Design Decisions

## Framework: FastAPI

### Why FastAPI over alternatives

| Alternative | Trade-off |
|-------------|-----------|
| **Django** | Full-featured but heavyweight for an API-only service. Django's ORM, admin panel, and template engine are unnecessary here. FastAPI's async-first design is better suited for I/O-bound LLM calls. |
| **Flask** | Simpler but lacks built-in async support, automatic OpenAPI docs, and Pydantic validation. Would require more boilerplate for request validation and documentation. |
| **Express.js (Node)** | Would require a separate runtime from the Python ML/AI ecosystem. Python is the natural choice given OpenAI SDK and data processing needs (pandas). |

### What we gain
- **Auto-generated OpenAPI docs** at `/docs` — free interactive API explorer.
- **Pydantic models** for request/response validation — catches bugs at the boundary.
- **Async support** — non-blocking OpenAI API calls.
- **Lifespan events** — clean database initialization on startup.

### What we sacrifice
- Smaller community than Django for full-stack web apps (but larger for APIs).
- No built-in admin panel (not needed for this use case).

---

## Database: SQLite

### Why SQLite over alternatives

| Alternative | Trade-off |
|-------------|-----------|
| **PostgreSQL** | More powerful (JSON ops, full-text search, concurrent writes) but requires a separate server process, connection pooling, and infrastructure management. Overkill for demo datasets with <1000 rows. |
| **DuckDB** | Better for analytical queries (columnar storage, vectorized execution) but less widely understood, harder to deploy, and its Python API differs from standard DB-API. Would be a strong choice if datasets grew to millions of rows. |
| **In-memory only** | Fastest, but loses query history and settings on restart. We need persistence for user configuration (API keys, model preferences). |

### What we gain
- **Zero configuration** — no server process, no connection string, no Docker container.
- **File-based persistence** — survives restarts when deployed with a persistent volume.
- **Standard SQL** — the generated SQL is portable; users can learn SQL patterns they can apply elsewhere.
- **WAL mode** — enabled for better concurrent read performance.

### What we sacrifice
- No concurrent writes (SQLite uses file-level locking). Acceptable for single-user or low-concurrency scenarios.
- Limited to ~1TB database size. More than sufficient for our use case.
- No native JSON column type (though SQLite has JSON functions).

### Schema design decisions
- **Separate system tables** (`query_history`, `settings`) and **semantic layer tables** (`semantic_*`) from data tables. The `get_all_tables()` function explicitly excludes both system and semantic tables so the LLM only sees relevant data schemas.
- **TEXT dates** (ISO 8601 format) instead of SQLite's lack of a native DATE type. This simplifies date filtering in generated SQL (`WHERE order_date >= '2024-01-01'`).
- **No foreign keys between datasets** — each dataset is self-contained. This avoids JOIN complexity in the NL-to-SQL layer, which is the hardest part of text-to-SQL.
- **Semantic layer stored in SQLite** — 7 dedicated `semantic_*` tables store column descriptions, glossary terms, metrics, dimensions, filters, joins, and trusted queries. Co-locating this metadata with the data ensures consistency and simplifies deployment (single DB file). See [08-semantic-layer.md](./08-semantic-layer.md) for details.
- **Schema retrieval tables** — 3 additional tables support the 6-level hybrid schema retriever:
  - `semantic_value_dictionary` — auto-scanned categorical column values (e.g., "Electronics" in `product_category`) for Level 1 value matching.
  - `semantic_column_stats` — auto-profiled column statistics (distinct count, min/max, null rate, cardinality) for Level 2 column profiling.
  - `schema_usage_patterns` — records co-occurring table/column pairs from executed queries for Level 5 usage-based boosting.

---

## API Design

### Endpoint structure

| Endpoint | Method | Purpose | Design rationale |
|----------|--------|---------|------------------|
| `/api/ask` | POST | NL question → SQL → results | Core endpoint. Returns everything needed for the frontend in one call: SQL, data, chart config, explanation. Avoids multiple round-trips. |
| `/api/query` | POST | Execute raw SQL | Escape hatch for power users. Restricted to SELECT only for safety. |
| `/api/datasets` | GET | List all datasets + schemas | Enables the sidebar dataset explorer. Returns column types for schema display. |
| `/api/datasets/{name}` | GET | Dataset details + sample | Preview data before querying. |
| `/api/datasets/{name}/sample` | GET | Paginated sample data | Separate from details to allow different limits. |
| `/api/history` | GET | Query history | Enables "recent queries" sidebar. |
| `/api/settings` | GET/POST | Read/update settings | API key management. GET never returns the full key (security). |
| `/api/suggested-questions` | GET | Curated starter questions | Improves onboarding UX. Hardcoded for speed; could be dynamic in future. |
| `/api/schema` | GET | Full schema as text | Useful for debugging or advanced users who want to see what the LLM sees. |
| `/api/semantic` | GET | Full semantic layer summary | Returns all semantic metadata (columns, glossary, metrics, dimensions, filters, joins, trusted queries) in one call. Powers the frontend Semantic tab. |
| `/api/semantic/columns` | GET | Column descriptions | Filterable by `table_name`. Includes business names and data formats. |
| `/api/semantic/glossary` | GET/POST/DELETE | Business glossary CRUD | Maps business terms to table/column references with synonyms. |
| `/api/semantic/metrics` | GET/POST/DELETE | Metric definitions CRUD | Pre-defined SQL expressions (e.g., `SUM(total_amount)` for "Total Revenue"). |
| `/api/semantic/dimensions` | GET | Dimension columns | Common GROUP BY columns per table. |
| `/api/semantic/filters` | GET | Pre-defined filters | Ready-made WHERE clauses (e.g., "Active Employees", "Low Stock"). |
| `/api/semantic/joins` | GET | Join relationships | How tables relate to each other (e.g., sales_orders to product_inventory). |
| `/api/semantic/trusted-queries` | GET/POST/DELETE | Trusted SQL queries CRUD | Curated SQL for common questions — matched before calling the LLM. |
| `/api/semantic/value-dictionary` | GET | Value dictionary entries | Auto-scanned categorical column values with frequency counts. Supports `?table_name=` filter. |
| `/api/semantic/column-stats` | GET | Column statistics | Auto-profiled column stats (distinct count, min/max, null rate, cardinality). Supports `?table_name=` filter. |
| `/api/semantic/instructions` | GET/POST/DELETE | Per-space instructions CRUD | Text rules injected into SQL generator prompt (global or dataset-scoped). |
| `/api/feedback` | POST/GET | Feedback submission & listing | Thumbs up/down voting per response with optional comments. |
| `/api/feedback/stats` | GET | Feedback accuracy stats | Accuracy %, upvote/downvote counts, recent feedback items. |
| `/api/benchmark/cases` | GET/POST/DELETE | Benchmark case management | Define expected Q&A pairs for accuracy testing. |
| `/api/benchmark/run` | POST | Run benchmark suite | Executes all cases through compound AI pipeline, compares results. |
| `/api/benchmark/history` | GET | Benchmark run history | Past benchmark runs with accuracy trends. |
| `/api/benchmark/runs/{id}` | GET | Benchmark run detail | Detailed per-case results for a specific run. |

### Trade-offs in API design

1. **Monolithic `/api/ask` response vs. separate endpoints**: We return SQL, data, chart config, and explanation in a single response. This means one round-trip instead of three (generate SQL → execute → suggest chart). The trade-off is a larger response payload and tighter coupling, but for a chat-style UX, latency matters more than response size.

2. **Read-only query restriction**: The `execute_query()` function rejects non-SELECT queries. This is a deliberate security boundary — the NL-to-SQL engine could theoretically generate destructive SQL. We chose safety over flexibility. Users who need write operations should use a proper database client.

3. **Settings stored in DB vs. environment variables**: We support both. Environment variables are checked first (for deployment configuration), but the DB-backed settings allow runtime configuration through the UI without redeployment. The trade-off is that the API key is stored in plaintext in SQLite. For production, this should be encrypted or moved to a secrets manager.

4. **Semantic layer as a single GET (`/api/semantic`)**: The full semantic summary is returned in one call to populate the frontend Semantic tab. Individual sub-endpoints (columns, glossary, metrics, etc.) exist for filtering and CRUD operations. This mirrors the monolithic `/api/ask` philosophy — prefer one round-trip for read-heavy operations.

---

## Data Loading Strategy

### Why synthetic datasets over real public APIs

| Approach | Trade-off |
|----------|-----------|
| **Synthetic data (chosen)** | Fully self-contained, no external dependencies, instant startup, predictable schema. But less realistic and doesn't demonstrate real-world data messiness. |
| **CSV downloads (e.g., Kaggle)** | More realistic but requires downloading files, handling encoding issues, and managing external dependencies. Startup time increases. |
| **Live API ingestion** | Most realistic but introduces API rate limits, authentication, network failures, and schema changes. Inappropriate for a demo app. |

### Dataset selection rationale

We chose four datasets that represent common business analytics scenarios:

1. **World Countries** (50 rows) — Geographic/demographic data. Good for aggregation queries ("top countries by..."), filtering ("countries in Asia"), and geographic visualizations.

2. **Sales Orders** (500 rows) — Transactional data with dates, categories, regions. Supports time-series analysis, segmentation, and the most common business questions ("revenue by quarter", "top customers").

3. **Employees** (150 rows) — HR data with departments, salaries, performance. Supports organizational analytics ("average salary by department", "headcount by office").

4. **Product Inventory** (40 rows) — Supply chain data with stock levels, costs, suppliers. Supports operational queries ("low stock items", "profit margins by category").

### What we sacrifice
- No cross-dataset relationships (no JOINs between tables). This simplifies the NL-to-SQL problem but limits analytical depth.
- Fixed data — no real-time updates. In a production Genie-like system, data would come from live data warehouses.
- Small scale — real Databricks Genie handles billions of rows via Spark. Our SQLite approach works for thousands.
