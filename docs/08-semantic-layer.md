# Semantic Layer — Architecture & Trade-offs

## What is a Semantic Layer?

A semantic layer sits between raw data schemas and the NL-to-SQL engine. It provides **business context** that helps the LLM understand what columns mean, how tables relate, and what common questions look like — bridging the gap between technical database schemas and natural language.

In Databricks Genie, this role is played by **Unity Catalog** (column descriptions, tags, lineage) and **Trusted Assets** (curated queries, instructions). Data Genie implements an equivalent system using 8 dedicated SQLite tables (7 core + 1 instructions table).

---

## Architecture

```
User Question
    │
    ▼
┌──────────────────────┐      ┌──────────────────────────┐
│ Trusted Query Match  │◀─────│ semantic_trusted_queries  │
│ (fuzzy keyword)      │      └──────────────────────────┘
└──────────┬───────────┘
           │ no match
           ▼
┌──────────────────────┐      ┌──────────────────────────┐
│ LLM Prompt Builder   │◀─────│ semantic_column_descs    │
│                      │◀─────│ semantic_glossary        │
│ System prompt now    │◀─────│ semantic_metrics         │
│ includes:            │◀─────│ semantic_dimensions      │
│ - Column meanings    │◀─────│ semantic_filters         │
│ - Business terms     │◀─────│ semantic_joins           │
│ - Metric formulas    │◀─────│ semantic_instructions    │
│ - Filter shortcuts   │
│ - Join paths         │
│ - Instructions       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Generated SQL        │
│ (context-aware)      │
└──────────────────────┘
```

---

## Database Schema (7+1 Tables)

### 1. `semantic_column_descriptions` (50 rows seeded)

Stores human-readable descriptions and business-friendly names for every column.

| Column | Type | Purpose |
|--------|------|---------|
| `table_name` | TEXT | Which table this column belongs to |
| `column_name` | TEXT | Technical column name |
| `description` | TEXT | What the column means in plain English |
| `business_name` | TEXT | Business-friendly alias (e.g., `bonus_pct` → "Bonus (%)") |
| `data_format` | TEXT | Display hint (e.g., "currency", "percentage", "date") |

**Trade-off**: Stored per-column rather than per-table. This is more granular than necessary for simple schemas but essential for large enterprise schemas where column names like `amt_1` or `flg_x` are meaningless without descriptions.

### 2. `semantic_glossary` (14 entries seeded)

Maps business terminology to database objects with synonym support.

| Column | Type | Purpose |
|--------|------|---------|
| `term` | TEXT | Business term (e.g., "Revenue", "Headcount", "AOV") |
| `definition` | TEXT | What the term means |
| `mapped_table` | TEXT | Primary table for this concept |
| `mapped_column` | TEXT | Primary column (if applicable) |
| `synonyms` | TEXT | Comma-separated alternatives (e.g., "sales, income, earnings") |

**Trade-off**: Synonyms are stored as comma-separated text rather than a normalized many-to-many table. This simplifies queries and the API but limits per-synonym metadata. Acceptable for the current scale.

### 3. `semantic_metrics` (16 metrics seeded)

Pre-defined SQL aggregation expressions that the LLM can reference.

| Column | Type | Purpose |
|--------|------|---------|
| `name` | TEXT | Metric name (e.g., "Total Revenue", "Average Salary") |
| `description` | TEXT | What the metric measures |
| `table_name` | TEXT | Which table the metric applies to |
| `expression` | TEXT | SQL expression (e.g., `SUM(total_amount)`) |
| `format_type` | TEXT | How to display the result ("currency", "number", "percentage") |

**Trade-off**: Metrics are simple SQL expressions, not full queries. This keeps them composable (the LLM can combine them with GROUP BY, WHERE, etc.) but means they can't represent complex derived metrics that require subqueries or CTEs.

### 4. `semantic_dimensions` (18 dimensions seeded)

Common GROUP BY columns that the LLM should prefer for aggregation queries.

| Column | Type | Purpose |
|--------|------|---------|
| `name` | TEXT | Dimension name (e.g., "Continent", "Product Category") |
| `table_name` | TEXT | Which table |
| `column_name` | TEXT | Actual column to GROUP BY |
| `description` | TEXT | What this dimension represents |

**Trade-off**: Dimensions are simple column references, not hierarchies. Databricks supports dimension hierarchies (e.g., Year → Quarter → Month → Day). Flat dimensions are sufficient for our schema but would need hierarchy support for time-series-heavy datasets.

### 5. `semantic_filters` (17 filters seeded)

Pre-built WHERE clauses for common filter patterns.

| Column | Type | Purpose |
|--------|------|---------|
| `name` | TEXT | Filter name (e.g., "Active Employees", "Low Stock") |
| `table_name` | TEXT | Which table |
| `expression` | TEXT | SQL WHERE clause (e.g., `employment_status = 'Active'`) |
| `description` | TEXT | When to apply this filter |

**Trade-off**: Filters are static expressions, not parameterized templates. A filter like "orders in the last N days" would need template support (e.g., `order_date >= date('now', '-{N} days')`). For now, common fixed filters cover the most frequent use cases.

### 6. `semantic_joins` (1 join seeded)

Defines how tables can be joined together.

| Column | Type | Purpose |
|--------|------|---------|
| `left_table` | TEXT | Left side of the join |
| `right_table` | TEXT | Right side of the join |
| `join_type` | TEXT | JOIN type (INNER, LEFT, etc.) |
| `on_clause` | TEXT | JOIN condition |
| `description` | TEXT | When this join makes sense |

**Trade-off**: Only one join is defined (sales_orders ↔ product_inventory). The 4 datasets are intentionally independent to keep the NL-to-SQL problem tractable. In an enterprise system, this table would define the full join graph, potentially with join paths and cardinality hints.

### 7. `semantic_trusted_queries` (12 queries seeded)

Curated SQL for common questions — matched before the LLM is called.

| Column | Type | Purpose |
|--------|------|---------|
| `question` | TEXT | Natural language question pattern |
| `sql_query` | TEXT | Exact SQL to execute |
| `description` | TEXT | What the query returns |
| `table_name` | TEXT | Primary table involved |
| `is_parameterized` | INTEGER | Whether the query uses `{param}` template syntax |

**Trade-off**: Trusted queries use fuzzy keyword matching (60% keyword overlap threshold). This is fast and simple but may produce false positives for short questions or miss semantically equivalent but lexically different phrasings. Semantic embedding-based matching would be more accurate but requires a vector store.

**Parameterized queries**: When `is_parameterized = 1`, the `sql_query` field contains `{param}` placeholders (e.g., `WHERE region = '{region}'`). The engine auto-extracts parameter values from the user's natural language question via regex matching against known column values, then substitutes them into the template with single-quote escaping for SQL injection prevention.

### 8. `semantic_instructions` (0 rows by default, user-managed)

Per-space text rules that are injected into the SQL generator's LLM prompt to guide SQL generation.

| Column | Type | Purpose |
|--------|------|--------|
| `id` | INTEGER | Auto-incrementing primary key |
| `instruction` | TEXT | The rule text (e.g., "Revenue means net revenue after refunds") |
| `scope` | TEXT | "global" or "dataset" — determines applicability |
| `dataset_name` | TEXT | Which dataset this applies to (NULL for global) |
| `priority` | INTEGER | Ordering priority (higher = applied first) |
| `is_active` | INTEGER | Whether the instruction is currently active (1/0) |
| `created_at` | TIMESTAMP | When the instruction was created |

**Trade-off**: Instructions are plain text injected into the LLM prompt, not structured rules. This is flexible (any natural language guidance works) but unverifiable — the LLM may interpret instructions differently than intended. A production system might add validation or test-against-benchmark verification for new instructions.

---

## Design Decisions

### Why store semantic metadata in SQLite (same DB as data)?

| Alternative | Trade-off |
|-------------|-----------|
| **Separate metadata store (Redis, PostgreSQL)** | Better separation of concerns, easier to scale independently. But adds infrastructure complexity for a self-contained demo app. |
| **YAML/JSON config files** | Version-controllable, easy to edit. But no CRUD API, no runtime updates, harder to query programmatically. |
| **SQLite (chosen)** | Single-file deployment, consistent with the data store, supports full SQL queries on metadata. Trade-off: metadata and data are tightly coupled — migrating to a different data backend requires migrating semantic metadata too. |

### Why seed default data vs. empty schema?

The semantic layer ships with pre-populated metadata for all 4 datasets. This is intentional:
1. **Immediate value**: The LLM produces better SQL on first use without any configuration.
2. **Documentation by example**: Users can see what good semantic metadata looks like before adding their own.
3. **Testability**: Pre-seeded data makes it easy to verify the semantic layer is working correctly.

**Trade-off**: The seeded data is hardcoded in `_seed_default_semantic_data()`. Changes to the underlying datasets require updating the seed function. A production system would use a separate admin workflow for metadata management.

### Why prefix all tables with `semantic_`?

The `semantic_` prefix serves as a namespace to clearly separate metadata tables from data tables. The `get_all_tables()` function uses `name NOT LIKE 'semantic_%'` to exclude them from the dataset explorer and LLM schema prompt. This is simpler than maintaining a manual exclusion list.

---

## Integration Points

### 1. NL-to-SQL Engine (`nl_to_sql.py`)

- **`find_trusted_query(question)`**: Called before the LLM. Returns curated SQL if a match is found (≥60% keyword overlap).
- **`get_semantic_context_for_prompt()`**: Called when building the LLM prompt. Returns a formatted text block with all semantic metadata, injected into the system prompt under `## Semantic Layer (Business Context)`.

### 2. Backend API (`main.py`)

- **14 endpoints** under `/api/semantic/*` for reading and managing all 8 semantic entity types (7 core + instructions).
- **`init_semantic_layer()`**: Called during app startup (lifespan event) to create tables and seed defaults if empty.

### 4. Feedback & Benchmarking (`feedback.py`)

- **`init_feedback_tables()`**: Called during app startup to create `query_feedback`, `benchmark_cases`, and `benchmark_runs` tables, and seed 20 default benchmark test cases.
- **12 endpoints** under `/api/feedback/*` and `/api/benchmark/*` for submitting feedback, viewing stats, managing benchmark cases, running benchmarks, and viewing run history.

### 3. Frontend (`SemanticLayer.tsx`)

- **Sidebar tab** ("Semantic") with 6 sub-tabs: Columns, Glossary, Metrics, Filters, Joins, Queries.
- **Search**: Filters the active tab by matching against names, descriptions, expressions, and synonyms.
- **Trusted query click**: Clicking a trusted query sends it as a question to the chat.

---

## Comparison with Databricks Unity Catalog

| Capability | Databricks Unity Catalog | Data Genie Semantic Layer |
|------------|-------------------------|--------------------------|
| Column descriptions | Per-column comments in catalog | `semantic_column_descriptions` table |
| Tags / labels | Key-value tags on columns, tables | `data_format` field on column descriptions |
| Business glossary | Not built-in (third-party tools) | `semantic_glossary` with synonym support |
| Metric definitions | Not built-in (dbt metrics layer) | `semantic_metrics` with SQL expressions |
| Data lineage | Automatic lineage tracking | Not implemented |
| Access controls | Fine-grained RBAC | Not implemented |
| Trusted assets | Admin-curated queries + instructions | `semantic_trusted_queries` with fuzzy matching + parameterized `{param}` template syntax |
| Instructions | Per-space text rules for NL-to-SQL guidance | `semantic_instructions` with global/dataset scope and priority ordering |
| Discovery | Search across all catalog objects | Search bar in Semantic sidebar tab |
| Auto-profiling | Statistical profiling of columns | `semantic_column_stats` table with auto-profiled distinct counts, min/max, null rates, cardinality |
| Value dictionaries | Categorical value lookup for filter matching | `semantic_value_dictionary` table with auto-scanned column values and frequency counts |

---

## Seeded Data Summary

| Entity | Count | Example |
|--------|-------|---------|
| Column descriptions | 50 | `employees.bonus_pct` → "Bonus percentage based on performance" (aka "Bonus (%)") |
| Glossary entries | 14 | "Revenue" → `sales_orders.total_amount` (synonyms: sales, income, earnings) |
| Metrics | 16 | "Total Revenue" = `SUM(total_amount)` on `sales_orders` |
| Dimensions | 18 | "Continent" = `continent` column on `world_countries` |
| Filters | 17 | "Active Employees" = `employment_status = 'Active'` |
| Joins | 1 | `sales_orders.product_name = product_inventory.product_name` (LEFT JOIN) |
| Trusted queries | 12 | "What are the top 10 countries by GDP?" → `SELECT country, gdp_usd_billion FROM world_countries ORDER BY gdp_usd_billion DESC LIMIT 10` (includes parameterized templates) |
| Instructions | 0 (user-managed) | "Revenue means net revenue after refunds" (global scope), "Always use ROUND() for currency" (dataset scope) |
| Value dictionary | ~1062 | "Electronics" in `product_inventory.category` (frequency: 14) — auto-scanned on startup |
| Column stats | ~52 | `employees.salary`: distinct=147, min=30256.59, max=197641.0, null=0, categorical=false — auto-profiled on startup |
| Usage patterns | 0 (grows) | Tracks which tables/columns are queried together — builds up over time |

---

## Schema Retrieval Tables (3 additional tables)

Beyond the 7 core semantic tables, the schema retrieval engine adds 3 auto-populated tables:

### `semantic_value_dictionary` (~1062 rows, auto-populated)

Stores actual column values from categorical columns (distinct count < 100) for Level 1 value matching.

| Column | Type | Purpose |
|--------|------|--------|
| `table_name` | TEXT | Source table |
| `column_name` | TEXT | Source column |
| `sample_value` | TEXT | Original value (e.g., "Electronics") |
| `normalized_value` | TEXT | Lowercased for matching |
| `frequency` | INTEGER | How often this value appears |

**Trade-off**: Only categorical columns (distinct < 100) are indexed to avoid memory bloat. This means numeric columns and high-cardinality text columns (emails, IDs) are excluded.

### `semantic_column_stats` (~52 rows, auto-populated)

Stores auto-profiled statistics for every column across all datasets.

| Column | Type | Purpose |
|--------|------|--------|
| `table_name` | TEXT | Source table |
| `column_name` | TEXT | Source column |
| `data_type` | TEXT | Detected type (TEXT, INTEGER, REAL) |
| `distinct_count` | INTEGER | Number of unique values |
| `null_count` | INTEGER | Number of NULL values |
| `total_count` | INTEGER | Total rows |
| `min_value` | TEXT | Minimum value |
| `max_value` | TEXT | Maximum value |
| `avg_value` | REAL | Average (numeric columns only) |
| `is_categorical` | INTEGER | 1 if distinct < 100 |
| `sample_values` | TEXT | JSON array of example values |

### `schema_usage_patterns` (grows over time)

Records which tables and columns are used together in executed queries. Used for Level 5 usage-based boosting.

| Column | Type | Purpose |
|--------|------|--------|
| `table_name` | TEXT | Table used |
| `column_name` | TEXT | Column used (nullable) |
| `co_table` | TEXT | Co-occurring table |
| `co_column` | TEXT | Co-occurring column |
| `frequency` | INTEGER | How many times seen together |
| `last_used` | TIMESTAMP | Last query time |

---

## Future Improvements

1. **Admin UI**: Build a dedicated admin panel for managing semantic metadata (currently API-only for writes, sidebar for reads).
2. **Auto-discovery**: Use LLM to automatically generate column descriptions and glossary entries from data samples.
3. **Transformer embeddings**: Replace TF-IDF with `all-MiniLM-L6-v2` or similar for better semantic matching at scale.
4. ~~**Parameterized trusted queries**~~: **DONE** — Template syntax `{param}` with auto-extraction from natural language and SQL injection prevention via single-quote escaping.
5. **Metric composition**: Allow metrics to reference other metrics (e.g., "Profit Margin" = "Total Profit" / "Total Revenue").
6. **Version history**: Track changes to semantic metadata over time for audit and rollback.
7. **Import/export**: Support YAML/JSON import/export of semantic layer definitions for version control and migration.
8. **Adaptive signal weights**: Learn optimal retrieval signal weights from user feedback rather than using fixed weights.
