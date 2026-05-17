# NL-to-SQL Engine — Trade-offs & Design Decisions

## Overview

The NL-to-SQL engine is the core intelligence layer of Data Genie. It converts natural language questions like "What are the top 10 countries by GDP?" into executable SQL queries. The engine has two modes:

1. **Trusted query mode** — checks for a fuzzy match against curated SQL queries in the semantic layer. Instant result, no LLM call needed.
2. **LLM mode** (when OpenAI API key is configured) — uses GPT models for accurate, context-aware SQL generation, enriched with semantic layer context.
3. **Fallback mode** (no API key) — uses rule-based pattern matching for basic queries.

---

## LLM-Powered SQL Generation

### Prompt Engineering Strategy

```
System prompt structure:
1. Role definition ("You are an expert SQL analyst")
2. Full database schema (auto-generated from live DB)
3. Semantic layer context (column descriptions, glossary, metrics, dimensions, filters, joins, trusted queries)
4. Strict rules (SELECT-only, SQLite syntax, date formats, use semantic layer terms)
5. Structured output format (JSON with sql, explanation, chart suggestion)
```

### Why this prompt structure

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Schema in system prompt** | The LLM needs to know exact table/column names to generate valid SQL. Auto-generating from the live DB ensures the prompt is always in sync with the actual schema. | Consumes tokens proportional to schema size. For very large schemas (100+ tables), this would need chunking or RAG-based schema retrieval. |
| **Semantic layer in system prompt** | Including column descriptions, business glossary, metric definitions, and pre-defined filters gives the LLM rich business context to correctly interpret terms like "revenue", "headcount", or "AOV". | Increases prompt token usage (~500-800 extra tokens). For very large semantic layers (100+ metrics), this would need relevance-based filtering or RAG retrieval. Currently acceptable for 4 tables. |
| **JSON output format** | Structured output enables reliable parsing. The frontend needs separate fields (SQL, explanation, chart config) not a free-text blob. | Slightly more complex prompt. Occasionally the LLM wraps JSON in markdown code fences — we handle this with regex stripping. |
| **Chart suggestion in same call** | Asking the LLM to suggest a visualization type alongside the SQL avoids a second API call. | The chart suggestion quality is "good enough" but not perfect. A dedicated visualization recommendation model would be more accurate but doubles latency and cost. |
| **Temperature = 0** | Deterministic output. Same question should produce the same SQL every time. | Loses creative/alternative query approaches. Acceptable trade-off for consistency. |
| **SELECT-only rule** | Safety boundary. Even if a user asks "delete all records", the LLM is instructed to refuse. | Limits functionality to read-only analytics. Write operations would need a separate, carefully guarded endpoint. |
| **Trusted query matching before LLM** | Common questions get instant, curated SQL results without an LLM call. Reduces cost and latency for known question patterns. | Requires manual curation of trusted queries. Fuzzy matching may occasionally match incorrectly. Only covers pre-defined patterns. |

### Model Selection

| Model | Speed | Cost | SQL Quality | Recommendation |
|-------|-------|------|-------------|----------------|
| `gpt-4o-mini` (default) | ~1s | $0.15/1M input | Very good for standard queries | Best balance of speed, cost, and quality for most users |
| `gpt-4o` | ~2s | $2.50/1M input | Excellent, handles complex JOINs | Use for complex analytical queries |
| `gpt-4-turbo` | ~3s | $10/1M input | Excellent | Legacy, generally prefer gpt-4o |
| `gpt-3.5-turbo` | ~0.5s | $0.50/1M input | Good for simple queries | Use when cost is primary concern |

**Trade-off**: We default to `gpt-4o-mini` because most data questions are straightforward aggregations, filters, and sorts. The cost difference between mini and full GPT-4o is ~17x, which matters at scale. Users can switch models in Settings.

### Why OpenAI over alternatives

| Alternative | Trade-off |
|-------------|-----------|
| **Anthropic Claude** | Comparable SQL quality but smaller ecosystem for structured output. OpenAI's JSON mode is more reliable. Could be added as an option. |
| **Local LLM (Ollama/llama.cpp)** | No API costs, full privacy. But requires GPU for acceptable speed, and SQL generation quality is significantly worse with smaller models. Not viable for a deployed web app. |
| **Fine-tuned model** | Best SQL quality for our specific schema. But requires training data collection, ongoing maintenance, and hosting infrastructure. Massive overkill for a demo with 4 tables. |
| **Specialized text-to-SQL models (NSQL, SQLCoder)** | Purpose-built for SQL generation, often competitive with GPT-4. But limited availability as APIs, harder to host, and don't provide chart suggestions or explanations. |

---

## Semantic Layer Integration

The NL-to-SQL engine integrates with the semantic layer at two points:

### 1. Trusted Query Matching (Pre-LLM)

Before calling the LLM, the engine checks if the user's question matches a **trusted query** in the semantic layer. This uses fuzzy keyword matching — if 60%+ of the question's keywords overlap with a trusted query's keywords, it returns the curated SQL directly.

```
User: "Show total revenue by product category"
  → Matches trusted query: "total sales by product category"
  → Returns curated SQL instantly (no LLM call)
```

#### Parameterized Trusted Queries

Trusted queries support a `{param}` template syntax for queries that vary by a single dimension. Parameters are auto-extracted from the user's natural language question via regex matching against known column values.

```
Template: "SELECT region, SUM(total_amount) FROM sales_orders WHERE region = '{region}' GROUP BY region"
User: "Show revenue in Asia"
  → Extracts region="Asia" from question
  → Substitutes into template: WHERE region = 'Asia'
  → Returns parameterized result instantly
```

**SQL injection prevention**: Parameter values are sanitized by escaping single quotes (`'` → `''`) before substitution into the SQL template. This prevents crafted inputs like `East' UNION SELECT ...` from breaking out of the string literal.

**Trade-off**: Fuzzy matching is simple but not perfect. It may miss semantically similar but lexically different questions ("What do we sell the most of?" won't match "total sales by category"). A semantic embedding-based matcher would be more accurate but adds complexity and latency. Parameterized queries use regex-based extraction rather than proper SQL parameterized statements (`?` placeholders), which is less robust but simpler to implement with dynamic template syntax.

### 2. Prompt Enrichment (During LLM Call)

When a question reaches the LLM, the system prompt includes a `## Semantic Layer (Business Context)` section containing:

- **Column descriptions**: What each column means in business terms (e.g., `bonus_pct` = "Bonus percentage based on performance")
- **Business glossary**: Term mappings with synonyms (e.g., "Revenue" → `sales_orders.total_amount`, synonyms: "sales, income, earnings")
- **Metric definitions**: Pre-built SQL expressions (e.g., "Total Revenue" = `SUM(total_amount)`)
- **Dimension columns**: Common GROUP BY candidates per table
- **Pre-defined filters**: Ready-made WHERE clauses (e.g., "Active Employees" = `employment_status = 'Active'`)
- **Join relationships**: How to correctly join tables (e.g., `sales_orders.product_name = product_inventory.product_name`)
- **Per-space instructions**: Active text rules (global or dataset-scoped) that guide SQL generation (e.g., "Revenue means net revenue after refunds", "Always use ROUND() for currency values")

The LLM prompt includes additional rules instructing it to:
- Map business terms to the correct columns using the glossary
- Use pre-defined filter expressions when applicable
- Prefer trusted query patterns when they closely match
- Follow all active per-space instructions

**Trade-off**: Including the full semantic context increases prompt size by ~500-800 tokens. For our 4-table schema this is acceptable, but for a 100-table enterprise schema, the semantic context would need to be filtered by relevance (e.g., only include metadata for tables mentioned in the question). Per-space instructions add further tokens but are typically short text rules (~10-50 tokens each).

See [08-semantic-layer.md](./08-semantic-layer.md) for full architecture details.

---

## Fallback Pattern Matcher

### Why include a fallback at all?

The fallback exists so the app is **immediately usable without any configuration**. A user can clone the repo, start it up, and ask questions right away. This dramatically improves the onboarding experience.

### How it works

```
User question
    │
    ▼
┌──────────────┐     ┌─────────────────┐
│ Keyword scan │────▶│ Identify target  │
│ for table    │     │ table            │
└──────────────┘     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ Pattern match   │
                     │ query type      │
                     └────────┬────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │ COUNT/     │  │ TOP/      │  │ SUM/      │
        │ GROUP BY   │  │ ORDER BY  │  │ AVG/      │
        └────────────┘  └───────────┘  │ aggregate │
                                       └───────────┘
```

### Pattern matching strategy

1. **Table detection**: Scan question for keywords mapped to tables (e.g., "salary" → `employees`, "GDP" → `world_countries`).
2. **Query type detection**: Match against patterns like "how many", "top N", "average", "total", "show/list".
3. **Column guessing**: Based on keywords, guess the most likely numeric column (for aggregation) and grouping column.
4. **SQL template**: Fill in a pre-defined SQL template with the detected components.

### Trade-offs of the fallback

| Aspect | Pro | Con |
|--------|-----|-----|
| **Accuracy** | Handles ~60-70% of common questions correctly | Fails on complex queries, JOINs, multi-step logic, or ambiguous phrasing |
| **Speed** | Instant (no API call) | — |
| **Cost** | Free | — |
| **Transparency** | Adds a note suggesting OpenAI key for better results | May frustrate users with incorrect results |
| **Maintenance** | Requires manual updates when datasets change | Each new table needs new keyword mappings |

### What the fallback cannot do
- Multi-table JOINs
- Subqueries
- Complex date arithmetic ("sales in the last 30 days")
- Conditional aggregation ("average salary for engineers hired after 2020")
- Understanding synonyms or rephrased questions
- Handling negation ("countries NOT in Asia")

---

## Security Considerations

### SQL Injection Prevention

The NL-to-SQL engine does NOT use parameterized queries for the generated SQL (since the entire query is dynamic). Instead, we rely on:

1. **SELECT-only enforcement**: `execute_query()` checks that the SQL starts with `SELECT` or `WITH` before executing. This prevents data modification.
2. **LLM instruction**: The system prompt explicitly instructs the model to only generate SELECT queries.
3. **SQLite's single-statement execution**: `conn.execute()` only runs one statement, preventing multi-statement injection (`;DROP TABLE...` won't work).
4. **Parameterized query sanitization**: For trusted queries with `{param}` templates, user-supplied parameter values are sanitized by escaping single quotes (`'` → `''`) before string substitution. This prevents breakout from string literals in the SQL template.

**Trade-off**: This is defense-in-depth but not bulletproof. The parameterized query sanitization escapes single quotes but does not use proper SQL `?` placeholders (which would be more robust). A production system should use a sandboxed query execution environment with a read-only database connection, query timeouts, and row limits. For a demo/POC, the current approach provides reasonable safety.

### API Key Storage

The OpenAI API key is stored in plaintext in the SQLite `settings` table. This is acceptable for a demo but would need encryption (e.g., using `cryptography.fernet`) or a secrets manager (AWS Secrets Manager, HashiCorp Vault) in production.

---

## 6-Level Hybrid Schema Retrieval

The compound AI pipeline now includes a **6-level hybrid schema retriever** (`schema_retriever.py`) that replaces the old hard-coded keyword matching. Instead of dumping the entire schema to the LLM, it intelligently selects relevant tables using multiple signals:

| Level | Signal | Method | Weight |
|-------|--------|--------|--------|
| 1 | **Value Dictionaries** | Matches actual column values in the question (e.g., "Electronics" → `product_category`) | 0.25 |
| 2 | **Column Statistics** | Auto-profiles distinct counts, min/max, null rates, cardinality | (context enrichment) |
| 3 | **Embedding Search** | TF-IDF word vectors for semantic similarity (no external model deps) | 0.20 |
| 4 | **LLM-Assisted Selection** | Cheap gpt-4o-mini call for ambiguous schema resolution | 0.15 |
| 5 | **Usage Patterns** | Learns co-occurring table/column pairs from past queries | 0.05 |
| 6 | **Hybrid Ranker** | Weighted fusion of all signals with configurable weights | — |

**How it works:**
1. Each signal independently scores tables/columns
2. Scores are normalized and combined using weighted fusion
3. Tables scoring ≥20% of the top score are included
4. Selected tables + value matches + filter hints are passed to the Context Assembler

**Trade-off**: The TF-IDF embedding approach is dependency-free and fast (~10ms) but less powerful than transformer-based embeddings (e.g., `all-MiniLM-L6-v2`). For 4 tables this is more than sufficient; a production system with 100+ tables would benefit from a proper embedding model. The embedding index is cached in memory after first build.

---

## Future Improvements

1. **Transformer embeddings**: Replace TF-IDF with `all-MiniLM-L6-v2` or similar for better semantic matching at scale.
2. **Query validation**: Before executing, parse the generated SQL AST to verify it only accesses expected tables and columns.
3. **Query caching**: Cache LLM responses for identical questions to reduce cost and latency.
4. **Confidence scoring**: Have the LLM rate its confidence in the generated SQL, and show a warning for low-confidence queries.
5. **Auto-generated semantic metadata**: Use LLM to automatically generate column descriptions and glossary entries from data samples, reducing manual curation effort.
6. **Adaptive signal weights**: Learn optimal signal weights from user feedback (correct/incorrect query results) rather than using fixed weights.
7. **Cross-table usage patterns**: Track which tables are frequently queried together to improve JOIN suggestions.
8. **Proper SQL parameterization**: Replace string substitution in parameterized trusted queries with SQLite `?` placeholders for stronger SQL injection prevention.
