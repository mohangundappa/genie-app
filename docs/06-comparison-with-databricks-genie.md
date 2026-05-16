# Comparison with Databricks Genie

## What Databricks Genie does

Databricks Genie is an AI-powered assistant within the Databricks Lakehouse Platform that allows users to interact with their data using natural language. Key capabilities:

1. **Natural language to SQL** — converts questions to Spark SQL.
2. **Data visualization** — auto-generates charts and dashboards.
3. **Schema awareness** — understands Unity Catalog metadata, column descriptions, and data lineage.
4. **Conversation memory** — multi-turn conversations with context retention.
5. **Guardrails** — enterprise security, RBAC, query governance, and audit logging.
6. **Trusted assets** — admins curate "trusted" tables, queries, and instructions.
7. **Scale** — operates on petabyte-scale data via Spark.

---

## Feature Comparison

| Feature | Databricks Genie | Data Genie (This Project) | Gap |
|---------|-----------------|--------------------------|-----|
| Natural language to SQL | Proprietary model, fine-tuned on SQL | OpenAI GPT + fallback pattern matcher | Quality gap for complex queries; our fallback covers basics |
| Database support | Spark SQL, Unity Catalog | SQLite | Our approach is self-contained but limited to GBs, not TBs |
| Schema awareness | Full catalog metadata, column descriptions, tags | Semantic layer with column descriptions, business glossary, metrics, dimensions, filters, joins | Comparable metadata coverage for configured tables; no data lineage or automated discovery |
| Chart suggestions | AI-driven, multiple chart types | LLM-suggested, 5 chart types | Similar approach, fewer chart options |
| Conversation memory | Multi-turn with context | Single-turn (each question is independent) | Significant UX gap for follow-up questions |
| Authentication | SCIM, SSO, RBAC | None | Production requirement, not implemented |
| Trusted assets | Admin-curated queries and instructions | Trusted queries with fuzzy matching + semantic layer metadata | Similar concept; admin UI for curation is API-only (no dedicated admin panel yet) |
| Query governance | Audit logs, query review, cost controls | Query history only | No governance framework |
| Data scale | Petabytes (Spark clusters) | Megabytes (SQLite) | Different target use cases |
| Deployment | Databricks workspace (managed) | Self-hosted (Fly.io) | More control, more operational burden |

---

## What Data Genie does well (relative to its scope)

1. **Zero-dependency setup**: Unlike Databricks (which requires a workspace, cluster, and Unity Catalog), Data Genie works with `poetry install && npm install && start`.

2. **Cost**: Free to run (excluding OpenAI API costs). Databricks Genie requires a Databricks workspace ($0.22/DBU for SQL Serverless).

3. **Customizable**: Open-source, every component can be modified. Databricks Genie is a managed service with limited customization.

4. **Offline-capable**: The fallback pattern matcher works without any external API. Databricks Genie requires internet connectivity.

5. **Learning tool**: The SQL display educates users about query construction. Databricks Genie focuses more on results than query transparency.

---

## What would be needed for production parity

### Must-have features

| Feature | Effort Estimate | Approach |
|---------|----------------|----------|
| Multi-turn conversations | Medium | Pass conversation history to LLM; add session management |
| Authentication & RBAC | High | Integrate OAuth 2.0; per-user permissions on datasets |
| ~~Column descriptions / metadata~~ | ~~Low~~ | ~~Add a `column_descriptions` table; include in LLM prompt~~ **DONE** — Semantic layer with 7 tables (column descriptions, glossary, metrics, dimensions, filters, joins, trusted queries) now included in LLM prompts |
| Query caching | Low | Cache LLM responses keyed by (question, schema_hash) |
| Streaming responses | Medium | Use OpenAI streaming API + SSE to show SQL as it's generated |
| Data connectors | High | Add connectors for PostgreSQL, MySQL, Snowflake, BigQuery |

### Nice-to-have features

| Feature | Effort Estimate | Approach |
|---------|----------------|----------|
| Dashboard builder | High | Pinnable queries that auto-refresh on a grid layout |
| Scheduled reports | Medium | Cron-based query execution with email/Slack delivery |
| Query suggestions based on schema | Medium | LLM generates likely questions from table metadata |
| Export (CSV, Excel, PDF) | Low | Server-side export endpoints |
| Collaborative annotations | Medium | Shared notes on queries/charts |
| Admin panel for trusted queries | Medium | CRUD API exists; needs a dedicated admin UI (currently browsable in Semantic sidebar tab) |

---

## Architectural differences

### Databricks Genie's architecture (inferred)
```
User → Genie UI → Proprietary NL model → Spark SQL → Delta Lake → Results → Auto-viz
         ↑                                    ↑
    Unity Catalog metadata              Spark compute cluster
    (column descriptions,               (auto-scaling,
     trusted assets,                     photon engine)
     lineage info)
```

### Data Genie's architecture
```
User → React Chat UI → Trusted Query Match? → [yes] → Curated SQL → Results → Recharts
              ↑               ↓ [no]
         Schema auto-gen    OpenAI API (with semantic context) → SQLite Query → Results
         + Semantic Layer         ↑
         (from live DB)     Fallback pattern matcher (no API needed)
```

### Key architectural trade-off
Databricks Genie separates **compute** (Spark clusters) from **storage** (Delta Lake) and **metadata** (Unity Catalog). This enables independent scaling of each layer.

Data Genie collapses all three into a single SQLite file. This dramatically simplifies deployment and operation but limits scalability. The right choice depends entirely on the use case:
- **Data Genie**: Team of 1-50, datasets under 1M rows, exploratory analytics
- **Databricks Genie**: Enterprise, petabyte-scale data, governed access, audit requirements
