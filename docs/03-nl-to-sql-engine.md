# NL-to-SQL Engine — Trade-offs & Design Decisions

## Overview

The NL-to-SQL engine is the core intelligence layer of Data Genie. It converts natural language questions like "What are the top 10 countries by GDP?" into executable SQL queries. The engine has two modes:

1. **LLM mode** (when OpenAI API key is configured) — uses GPT models for accurate, context-aware SQL generation.
2. **Fallback mode** (no API key) — uses rule-based pattern matching for basic queries.

---

## LLM-Powered SQL Generation

### Prompt Engineering Strategy

```
System prompt structure:
1. Role definition ("You are an expert SQL analyst")
2. Full database schema (auto-generated from live DB)
3. Strict rules (SELECT-only, SQLite syntax, date formats)
4. Structured output format (JSON with sql, explanation, chart suggestion)
```

### Why this prompt structure

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Schema in system prompt** | The LLM needs to know exact table/column names to generate valid SQL. Auto-generating from the live DB ensures the prompt is always in sync with the actual schema. | Consumes tokens proportional to schema size. For very large schemas (100+ tables), this would need chunking or RAG-based schema retrieval. |
| **JSON output format** | Structured output enables reliable parsing. The frontend needs separate fields (SQL, explanation, chart config) not a free-text blob. | Slightly more complex prompt. Occasionally the LLM wraps JSON in markdown code fences — we handle this with regex stripping. |
| **Chart suggestion in same call** | Asking the LLM to suggest a visualization type alongside the SQL avoids a second API call. | The chart suggestion quality is "good enough" but not perfect. A dedicated visualization recommendation model would be more accurate but doubles latency and cost. |
| **Temperature = 0** | Deterministic output. Same question should produce the same SQL every time. | Loses creative/alternative query approaches. Acceptable trade-off for consistency. |
| **SELECT-only rule** | Safety boundary. Even if a user asks "delete all records", the LLM is instructed to refuse. | Limits functionality to read-only analytics. Write operations would need a separate, carefully guarded endpoint. |

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

**Trade-off**: This is defense-in-depth but not bulletproof. A production system should use a sandboxed query execution environment with a read-only database connection, query timeouts, and row limits. For a demo/POC, the current approach provides reasonable safety.

### API Key Storage

The OpenAI API key is stored in plaintext in the SQLite `settings` table. This is acceptable for a demo but would need encryption (e.g., using `cryptography.fernet`) or a secrets manager (AWS Secrets Manager, HashiCorp Vault) in production.

---

## Future Improvements

1. **Schema-aware RAG**: For large schemas, embed column descriptions and retrieve relevant tables based on the question, rather than sending the entire schema.
2. **Query validation**: Before executing, parse the generated SQL AST to verify it only accesses expected tables and columns.
3. **Query caching**: Cache LLM responses for identical questions to reduce cost and latency.
4. **Multi-turn context**: Pass previous Q&A pairs to the LLM so users can ask follow-up questions ("now filter that by Asia").
5. **Confidence scoring**: Have the LLM rate its confidence in the generated SQL, and show a warning for low-confidence queries.
