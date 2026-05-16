# Comparison with Databricks Genie

## Databricks Genie Architecture

Databricks Genie is part of the **AI/BI** product suite, built on a **compound AI system** — multiple AI components (models, retrievers, rankers) working together rather than a single LLM. It is tightly integrated into the Databricks Data Intelligence Platform.

### Core Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Genie UI / Databricks One                        │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ Conversational│  │  AI/BI        │  │  Databricks  │  │  Mobile   │  │
│  │ Chat (Spaces) │  │  Dashboards   │  │  Apps        │  │ iOS/Android│ │
│  └──────┬───────┘  └───────┬───────┘  └──────┬───────┘  └─────┬─────┘  │
│         └──────────────────┴─────────────────┴─────────────────┘        │
│                                    │                                    │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                    Compound AI System                                   │
│                                    │                                    │
│  ┌──────────────┐  ┌──────────────┴──────────┐  ┌───────────────────┐  │
│  │ Genie Space  │  │ NL-to-SQL Engine        │  │ Agentic Reasoning │  │
│  │ Resolution   │  │ (proprietary, fine-tuned │  │ (clarification,   │  │
│  │ (selects the │  │  on SQL + org context)   │  │  follow-ups,      │  │
│  │  best space) │  │                          │  │  multi-turn)      │  │
│  └──────┬───────┘  └──────────────┬──────────┘  └───────────────────┘  │
│         │                         │                                     │
│  ┌──────┴─────────────────────────┴──────────────────────────────────┐  │
│  │                    Genie Space (per-domain)                        │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐                │  │
│  │  │ Knowledge   │ │ Trusted      │ │ Instructions │                │  │
│  │  │ Store       │ │ Assets       │ │ (text rules) │                │  │
│  │  │ ┌─────────┐ │ │ ┌──────────┐ │ │              │                │  │
│  │  │ │Col descs│ │ │ │Param SQL │ │ └──────────────┘                │  │
│  │  │ │Synonyms │ │ │ │queries   │ │                                 │  │
│  │  │ │Joins    │ │ │ │(verified)│ │ ┌──────────────┐                │  │
│  │  │ │Measures │ │ │ ├──────────┤ │ │ Benchmarking │                │  │
│  │  │ │Filters  │ │ │ │UDF       │ │ │ & Feedback   │                │  │
│  │  │ │Dimensions│ │ │ │functions │ │ │ (confidence  │                │  │
│  │  │ │Value    │ │ │ │(locked   │ │ │  voting)     │                │  │
│  │  │ │ dicts   │ │ │ │ logic)   │ │ └──────────────┘                │  │
│  │  │ └─────────┘ │ │ └──────────┘ │                                 │  │
│  │  └─────────────┘ └──────────────┘                                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────────┐
│                   Data Intelligence Platform                            │
│                              │                                          │
│  ┌──────────────┐  ┌────────┴────────┐  ┌──────────────────┐           │
│  │ Unity Catalog│  │ SQL Warehouse   │  │ Delta Lake       │           │
│  │ ┌──────────┐ │  │ (Photon engine, │  │ (petabyte-scale  │           │
│  │ │Metadata  │ │  │  auto-scaling,  │  │  storage,        │           │
│  │ │Lineage   │ │  │  serverless)    │  │  ACID, time      │           │
│  │ │RBAC/ACLs │ │  │                 │  │  travel)         │           │
│  │ │Metric    │ │  └─────────────────┘  └──────────────────┘           │
│  │ │ Views    │ │                                                       │
│  │ │Tags      │ │                                                       │
│  │ └──────────┘ │                                                       │
│  └──────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Concepts

| Concept | Description |
|---------|-------------|
| **Compound AI System** | Multiple AI models + retrievers + rankers working together — not a single LLM call. Includes agentic reasoning for clarification and multi-turn conversation. |
| **Genie Spaces** | Domain-specific workspaces configured by data analysts. Each space has its own datasets, instructions, knowledge store, and trusted assets. Limits: 100 instructions + 200 knowledge store snippets per space. |
| **Knowledge Store** | Per-space semantic metadata: table/column descriptions, synonyms, join relationships with cardinality, SQL expressions (measures, filters, dimensions), value dictionaries, prompt matching rules. |
| **Trusted Assets** | Parameterized SQL queries and Unity Catalog UDFs that produce verified answers with a "Trusted" badge. Users can see and edit parameters but not the underlying SQL logic. |
| **Unity Catalog** | Central governance layer providing metadata, data lineage, RBAC, tags, and metric views. Semantic metadata in Genie Spaces is scoped locally and does not modify Unity Catalog. |
| **SQL Warehouses** | Photon-powered query execution engine with auto-scaling. Separates compute from storage (Delta Lake). |
| **Metric Views** | Centralized metric definitions (measures, dimensions, certifications) in Unity Catalog. Auto-materialized for performance. Shared across Genie, dashboards, and notebooks. |
| **Benchmarking** | Built-in tool to define expected answers for common questions and measure Genie's accuracy over time. Tracks regressions when data or configuration changes. |

---

## Data Genie Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         React Frontend                               │
│  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ │
│  │ Chat UI      │ │  Chart   │ │ Results  │ │ Dataset │ │Semantic│ │
│  │ (single-turn)│ │  Engine  │ │  Table   │ │Explorer │ │ Layer  │ │
│  │              │ │ (Recharts│ │          │ │         │ │Browser │ │
│  │              │ │  5 types)│ │          │ │         │ │(6 tabs)│ │
│  └──────┬───────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └───┬────┘ │
│         └──────────────┴────────────┴────────────┘           │      │
│                         │ REST API                           │      │
└─────────────────────────┼────────────────────────────────────┼──────┘
                          │                                    │
┌─────────────────────────┼────────────────────────────────────┼──────┐
│                  FastAPI Backend                              │      │
│                         │                                    │      │
│  ┌──────────────────────┼────────────────┐       ┌───────────┴────┐ │
│  │       NL-to-SQL Pipeline              │       │  Semantic Layer│ │
│  │                      │                │       │  CRUD API      │ │
│  │  ┌───────────────────▼──────────────┐ │       │  (11 endpoints)│ │
│  │  │ 1. Trusted Query Match           │ │       └───────┬────────┘ │
│  │  │    (fuzzy keyword, 60% threshold)│ │               │          │
│  │  └──────────┬──────────┬────────────┘ │               │          │
│  │        match │          │ no match     │               │          │
│  │             │          │              │               │          │
│  │  ┌──────────▼┐  ┌──────▼───────────┐ │               │          │
│  │  │ Return    │  │ 2. LLM Call      │ │               │          │
│  │  │ curated   │  │ (OpenAI GPT +    │◀───semantic─────┘          │
│  │  │ SQL       │  │  schema +        │ │  context                 │
│  │  │ instantly │  │  semantic layer  │ │                           │
│  │  └───────────┘  │  context in      │ │                           │
│  │                 │  system prompt)  │ │                           │
│  │                 └──────┬───────────┘ │                           │
│  │                   no API key         │                           │
│  │                 ┌──────▼───────────┐ │                           │
│  │                 │ 3. Fallback      │ │                           │
│  │                 │ Pattern Matcher  │ │                           │
│  │                 │ (rule-based,     │ │                           │
│  │                 │  no LLM needed)  │ │                           │
│  │                 └─────────────────┘ │                           │
│  └────────────────────────────────────┘                            │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐   │
│  │                    SQLite Database (single file)             │   │
│  │                                                              │   │
│  │  ┌──────────────┐ ┌────────┐ ┌──────────┐                   │   │
│  │  │ Data Tables  │ │History │ │ Settings │                   │   │
│  │  │ (4 datasets) │ │        │ │          │                   │   │
│  │  └──────────────┘ └────────┘ └──────────┘                   │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │ Semantic Layer Tables (7)                             │    │   │
│  │  │ column_descs | glossary | metrics | dimensions       │    │   │
│  │  │ filters | joins | trusted_queries                    │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

---

## Side-by-Side Architecture Comparison

| Layer | Databricks Genie | Data Genie | Key Difference |
|-------|-----------------|------------|----------------|
| **UI** | Genie UI + Dashboards + Mobile apps + Databricks One | React SPA (Chat + Charts + Sidebar) | Databricks has multiple consumption surfaces; Data Genie is a single chat-first interface |
| **AI Engine** | Compound AI system (multiple models, retrievers, rankers, agentic reasoning) | Single OpenAI API call + fallback pattern matcher | Databricks uses proprietary multi-model orchestration; Data Genie uses a single general-purpose LLM |
| **Conversation** | Multi-turn with context retention + clarification questions | Single-turn (each question independent) | Databricks tracks conversation state and asks follow-ups; Data Genie treats each question in isolation |
| **Semantic Layer** | Knowledge Store (per-space: col descriptions, synonyms, joins with cardinality, measures, filters, dimensions, value dicts, prompt matching) | SQLite tables (column_descs, glossary, metrics, dimensions, filters, joins, trusted_queries) | Similar metadata categories. Databricks scopes per-space; Data Genie has one global semantic layer. Databricks adds value dictionaries and prompt matching. |
| **Trusted Assets** | Parameterized SQL queries + UDFs with "Trusted" badge on responses | Trusted queries with fuzzy keyword matching and instant curated result | Databricks supports parameterized queries and locked-down UDFs with explicit "Trusted" labeling; Data Genie does simple keyword matching against static queries |
| **Instructions** | Per-space text instructions + usage guidance on queries | Not implemented (semantic context in LLM prompt serves a similar role) | Databricks supports explicit natural language rules per space; Data Genie embeds all context in the system prompt |
| **Governance** | Unity Catalog (RBAC, lineage, tags, audit logs, metric views) | None | Major gap — no access control, lineage, or audit trail |
| **Query Execution** | SQL Warehouses + Photon engine (auto-scaling, serverless) | SQLite (embedded, single-writer) | Databricks scales to petabytes with distributed compute; Data Genie is limited to single-digit GB datasets |
| **Data Storage** | Delta Lake (ACID, time travel, petabyte-scale, open format) | SQLite file (single file, MB-scale) | Completely different scale and capability |
| **Metrics** | Metric Views in Unity Catalog (centralized, auto-materialized, shared across tools) | semantic_metrics table (SQL expressions, per-table) | Databricks metrics are governed platform objects; Data Genie metrics are simple expressions stored in SQLite |
| **Quality** | Benchmarking tool (define expected answers, track accuracy over time, detect regressions) | Not implemented | No systematic quality measurement in Data Genie |
| **Feedback** | Confidence voting (thumbs up/down per response), used to improve Genie | Not implemented | No feedback loop in Data Genie |
| **Deployment** | Managed SaaS (Databricks workspace) | Self-hosted (Fly.io / local) | Databricks is fully managed; Data Genie requires manual deployment |
| **Cost** | Pay-per-DBU ($0.22+/DBU for SQL Serverless) + seat licensing | Free (open-source) + OpenAI API costs (~$0.001-0.01 per question) | Data Genie is dramatically cheaper for small-scale use |

---

## What Data Genie does well (relative to its scope)

1. **Zero-dependency setup**: `poetry install && npm install && start`. No workspace, cluster, or catalog configuration needed.

2. **Cost**: Free to run (excluding OpenAI API costs of ~$0.001/question). Databricks requires a workspace subscription + compute costs.

3. **Fully open and customizable**: Every component is modifiable. Databricks Genie is a managed service with configuration but no source-level customization.

4. **Offline-capable**: The fallback pattern matcher works without any external API. Databricks requires internet + active Databricks workspace.

5. **SQL transparency**: Every response shows the generated SQL, educating users. Databricks shows SQL for trusted queries but is less focused on query education.

6. **Semantic layer browsability**: The frontend Semantic tab lets users explore column descriptions, glossary, metrics, filters — making the metadata visible and discoverable. Databricks Knowledge Store is configured by admins, not browsed by end users.

---

## What would be needed for production parity

### Must-have features

| Feature | Effort | Approach |
|---------|--------|----------|
| Multi-turn conversations | Medium | Pass conversation history to LLM; add session management |
| Authentication & RBAC | High | Integrate OAuth 2.0; per-user permissions on datasets |
| ~~Column descriptions / metadata~~ | ~~Low~~ | **DONE** — Semantic layer with 7 tables now included in LLM prompts |
| Parameterized trusted queries | Medium | Template syntax in trusted queries; extract parameters from user questions |
| Benchmarking / quality monitoring | Medium | Define expected Q&A pairs; run automated accuracy tests |
| Feedback loop | Low | Thumbs up/down per response; store votes; use for tuning |
| Query caching | Low | Cache LLM responses keyed by (question, schema_hash) |
| Streaming responses | Medium | Use OpenAI streaming API + SSE to show SQL as it's generated |
| Data connectors | High | Add connectors for PostgreSQL, MySQL, Snowflake, BigQuery |
| Value dictionaries / entity matching | Medium | Store example column values to improve LLM matching for categorical data |

### Nice-to-have features

| Feature | Effort | Approach |
|---------|--------|----------|
| Multiple Genie Spaces | High | Scope semantic metadata per-space; add space management UI |
| Dashboard builder | High | Pinnable queries that auto-refresh on a grid layout |
| Metric Views (centralized) | Medium | Shared metric definitions across spaces with materialization |
| Scheduled reports | Medium | Cron-based query execution with email/Slack delivery |
| Query suggestions based on schema | Medium | LLM generates likely questions from table metadata |
| Export (CSV, Excel, PDF) | Low | Server-side export endpoints |
| Admin panel for semantic layer | Medium | CRUD UI for semantic metadata (API exists; needs dedicated admin UI) |
| Agentic reasoning | High | Multi-step query planning; clarification questions when ambiguous |

---

## Key Architectural Trade-off

Databricks Genie separates its architecture into four independent layers that scale independently:

1. **Presentation** (Genie UI, Dashboards, Mobile, One)
2. **AI** (Compound AI system, per-space configuration)
3. **Compute** (SQL Warehouses, Photon engine, auto-scaling)
4. **Storage + Governance** (Delta Lake, Unity Catalog)

Data Genie collapses all four into two layers:

1. **Presentation** (React SPA)
2. **Everything else** (FastAPI + SQLite — AI engine, query execution, data storage, and semantic metadata all in a single process with a single database file)

This dramatically simplifies deployment and operation but limits scalability. The right choice depends entirely on the use case:

- **Data Genie**: Team of 1-50, datasets under 1M rows, exploratory analytics, learning tool
- **Databricks Genie**: Enterprise, petabyte-scale data, governed access, audit requirements, multi-department deployment
