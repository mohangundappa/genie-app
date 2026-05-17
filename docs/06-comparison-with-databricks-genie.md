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
│  └──────┴───────┘  └───────┴───────┘  └──────┴───────┘  └─────┴─────┘  │
│         └────────────────┴─────────────────┴─────────────────┘        │
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
│  └──────┴───────┘  └──────────────┴──────────┘  └───────────────────┘  │
│         │                         │                                     │
│  ┌──────┴─────────────────────────┴────────────────────────────────────┐  │
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
└─────────────────────────────┴─────────────────────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────────────┐
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
└─────────────────────────────────────────────────────────────────────────────┘
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
| **Benchmarking** | Built-in tool to define expected answers for common questions and measure Genie accuracy over time. Tracks regressions when data or configuration changes. |

---

## Data Genie Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         React Frontend                                  │
│  ┌────────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐  │
│  │ Multi-turn     │ │  Chart   │ │ Results  │ │ Dataset │ │ Semantic │  │
│  │ Chat UI        │ │  Engine  │ │  Table   │ │ Explorer│ │ Layer    │  │
│  │ (sessions,     │ │ (Recharts│ │          │ │         │ │ Browser  │  │
│  │  follow-ups,   │ │  5 types)│ │          │ │         │ │ (6 tabs) │  │
│  │  clarification,│ │          │ │          │ │         │ │          │  │
│  │  pipeline view)│ │          │ │          │ │         │ │          │  │
│  └──────┴─────────┘ └────┴─────┘ └────┴─────┘ └────┴────┘ └────┴─────┘  │
│         └────────────────┴────────────┴───────────┘          │           │
│                          │ REST API                          │           │
└──────────────────────────┼─────────────────────────────────┴───────────┘
                           │                                   │
┌──────────────────────────┼─────────────────────────────────┼───────────┐
│                   FastAPI Backend                             │           │
│                          │                                   │           │
│  ┌───────────────────────┴────────────────────────────────┐  │           │
│  │   Compound AI Pipeline (8 stages)                      │  │           │
│  │                                                         │  │           │
│  │  ┌───────────────────┐    ┌───────────────────┐        │  │           │
│  │  │ 1. Trusted Query  │    │ 2. Intent         │        │  │           │
│  │  │    Fast Path      │    │    Classifier      │        │  │           │
│  │  │  (fuzzy match,    │    │  (LLM or keyword   │        │  │           │
│  │  │   instant SQL)    │    │   categorization)  │        │  │           │
│  │  └────────┴──────────┘    └────────┴───────────┘        │  │           │
│  │      match │                  no   │                    │  │           │
│  │            │                       ▼                    │  │           │
│  │            │           ┌───────────────────┐            │  │ ┌────────┐│
│  │            │           │ 3. Schema         │            │  │ │Semantic││
│  │            │           │    Retriever      │            │  │ │Layer   ││
│  │            │           │  (table scoring,  │<--semantic-┴--+ │CRUD   ││
│  │            │           │   col matching)   │                │API    ││
│  │            │           └────────┴──────────┘                │(11 ep)││
│  │            │                    │                       └────────┘│
│  │            │           ┌────────▼──────────┐                         │
│  │            │           │ 4. Context        │                         │
│  │            │           │    Assembler      │                         │
│  │            │           │  (glossary,       │                         │
│  │            │           │   metrics, dims,  │                         │
│  │            │           │   filters, joins) │                         │
│  │            │           └────────┴──────────┘                         │
│  │            │                    │                                  │
│  │            │           ┌────────▼──────────┐                         │
│  │            │           │ 5. SQL Generator  │                         │
│  │            │           │  (LLM + focused   │                         │
│  │            │           │   context, or     │                         │
│  │            │           │   pattern match)  │                         │
│  │            │           └────────┴──────────┘                         │
│  │            │                    │                                  │
│  │            │           ┌────────▼──────────┐                         │
│  │            │           │ 6. SQL Validator   │                         │
│  │            │           │  (EXPLAIN check,  │                         │
│  │            │           │   auto-fix loop)  │                         │
│  │            │           └────────┴──────────┘                         │
│  │            │                    │                                  │
│  │            │           ┌────────▼──────────┐                         │
│  │            └──────────►│ 7. Result         │                         │
│  │                        │    Summarizer     │                         │
│  │                        │  (NL summary of   │                         │
│  │                        │   query results)  │                         │
│  │                        └────────┴──────────┘                         │
│  │                                 │                                  │
│  │                        ┌────────▼──────────┐                         │
│  │                        │ 8. Follow-up      │                         │
│  │                        │    Suggester      │                         │
│  │                        │  (related Qs      │                         │
│  │                        │   based on        │                         │
│  │                        │   intent+results) │                         │
│  │                        └───────────────────┘                         │
│  └─────────────────────────────────────────────────────────┘                         │
│                          │                                               │
│  ┌───Session Management──┴─────────────────────────────────────────┐   │
│  │ conversation_sessions │ conversation_messages                      │   │
│  │ (multi-turn history, session tracking, clarification state)        │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                          │                                               │
│  ┌───────────────────────▼────────────────────────────────────────────┐   │
│  │                    SQLite Database (single file)                    │   │
│  │                                                                     │   │
│  │  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│  │  │ Data Tables  │ │ History  │ │ Settings │ │ Session Tables   │   │   │
│  │  │ (4 datasets) │ │          │ │          │ │ (conversations)  │   │   │
│  │  └──────────────┘ └──────────┘ └──────────┘ └──────────────────┘   │   │
│  │                                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │ Semantic Layer Tables (7)                                     │  │   │
│  │  │ column_descs | glossary | metrics | dimensions                │  │   │
│  │  │ filters | joins | trusted_queries                            │  │   │
│  │  └──────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

### Compound AI Pipeline Detail

| Stage | Component | Method | Purpose | How It Works (Example) |
|-------|-----------|--------|---------|----------------------|
| 1 | **Trusted Query Fast Path** | Fuzzy keyword matching (60% threshold) | Instantly return curated SQL for known questions — bypasses entire LLM pipeline | User asks *"What is total revenue?"* → fuzzy-matches trusted query *"total revenue"* (similarity 0.85) → returns pre-built `SELECT SUM(total_amount) FROM sales_orders` instantly without calling LLM |
| 2 | **Intent Classifier** | LLM-based (7 intent types) + keyword fallback | Categorizes question as aggregation, ranking, trend, comparison, lookup, filter, or distribution | User asks *"Which country has the highest GDP?"* → LLM classifies intent as **ranking** → extracts entities: `country`, `GDP` → keyword fallback detects "highest" as ranking signal if LLM unavailable |
| 3 | **Schema Retriever** | 6-level hybrid retrieval with weighted fusion | Finds relevant tables using value dictionaries, column stats, TF-IDF embedding search, LLM-assisted selection, usage patterns, and weighted score fusion | User asks *"Show Electronics revenue by region"* → Level 1: value dictionary matches "Electronics" in `product_category` column → Level 3: TF-IDF embedding finds "revenue" similar to `total_amount` → Level 6: hybrid ranker fuses all signals with weights (value_dict=0.25, embedding=0.20, keyword=0.15) → `sales_orders` wins with score 0.595 |
| 4 | **Context Assembler** | Semantic layer filtering | Pulls matching glossary, metrics, dimensions, filters, joins — scoped to relevant tables | For table `world_economics` → pulls glossary entry *"GDP = Gross Domestic Product, column: gdp"* + metric *"Total GDP = SUM(gdp)"* + dimension *"Country = GROUP BY country"* + filter *"Large Economies = gdp > 1000000000000"* → assembles focused context block |
| 5 | **SQL Generator** | LLM with focused context + pattern matcher fallback | Generates SQL using filtered schema + semantic context + conversation history | Sends to LLM: schema (`world_economics` only) + semantic context (GDP glossary, metrics) + conversation history (last 5 turns) + question → LLM generates `SELECT country, gdp FROM world_economics ORDER BY gdp DESC LIMIT 1` |
| 6 | **SQL Validator** | EXPLAIN check + auto-fix loop (2 retries) | Validates generated SQL before execution; LLM auto-fixes if invalid | Runs `EXPLAIN SELECT country, gdp FROM world_economics ORDER BY gdp DESC LIMIT 1` → SQLite returns query plan (valid) → proceeds to execute. If EXPLAIN fails (e.g., typo in column name), sends error back to LLM → LLM fixes the SQL → re-validates (up to 2 retries) |
| 7 | **Result Summarizer** | LLM-generated NL summary | Produces natural language summary with key insights from query results | Query returns `[{country: "United States", gdp: 21427700000000}]` → LLM generates summary: *"The United States has the highest GDP at $21.4 trillion, leading all countries in the dataset."* |
| 8 | **Follow-up Suggester** | Heuristic + LLM-based | Suggests related questions based on intent type and query results | Intent was **ranking** on `world_economics` → generates follow-ups: *"What are the top 5 countries by GDP?"*, *"How does GDP compare across continents?"*, *"What is the average GDP per capita?"* → displayed as clickable chips in the UI |

### Agentic Reasoning Features

| Feature | Implementation |
|---------|---------------|
| **Multi-turn conversations** | Session-based history stored in DB; last 5 turns passed to LLM for context |
| **Clarification questions** | Intent classifier detects ambiguous queries; asks user for clarification before generating SQL |
| **Follow-up suggestions** | Clickable suggestion chips generated after each response based on intent and results |
| **Session management** | Per-session message history with API endpoints for listing sessions and retrieving history |
| **Blackboard architecture** | Shared PipelineContext object passed through all 8 independent stages |

---

## Side-by-Side Architecture Comparison

| Layer | Databricks Genie | Data Genie | Key Difference |
|-------|-----------------|------------|----------------|
| **UI** | Genie UI + Dashboards + Mobile apps + Databricks One | React SPA (Multi-turn Chat + Pipeline Viewer + Charts + Sidebar) | Databricks has multiple consumption surfaces; Data Genie is a single chat-first interface with pipeline transparency |
| **AI Engine** | Compound AI system (proprietary multi-model orchestration, retrievers, rankers) | Compound AI pipeline (8 stages: trusted query check, intent classifier, schema retriever, context assembler, SQL generator, SQL validator, result summarizer, follow-up suggester) | Both use multi-stage pipelines. Databricks uses proprietary fine-tuned models; Data Genie simulates the architecture using OpenAI GPT + heuristic stages |
| **Pipeline Architecture** | Blackboard-style with proprietary orchestration | Blackboard-style with shared PipelineContext passed through independent stages | Similar pattern. Data Genie stages are modular and independently replaceable |
| **Intent Classification** | Proprietary classifier embedded in compound AI system | LLM-based classification (7 intent types) with keyword fallback | Data Genie supports: aggregation, ranking, trend, comparison, lookup, filter, distribution |
| **Schema Retrieval** | Intelligent schema matching using Unity Catalog metadata | Table/column scoring based on keyword matching + entity extraction from intent classifier | Databricks has richer metadata from Unity Catalog; Data Genie scores tables by keyword relevance |
| **Context Assembly** | Per-space Knowledge Store (col descriptions, synonyms, joins, measures, filters, dimensions, value dicts) | Filtered semantic context (column descriptions, glossary, metrics, dimensions, filters, joins — scoped to relevant tables only) | Similar metadata categories. Databricks scopes per-space; Data Genie filters per-query based on schema retriever output |
| **SQL Generation** | Proprietary fine-tuned NL-to-SQL model with org-specific training | OpenAI GPT with focused context from assembler + conversation history, pattern matcher fallback | Databricks model is specialized for SQL; Data Genie uses general-purpose LLM with rich prompt context |
| **SQL Validation** | Built into execution layer with error correction | EXPLAIN-based validation with auto-fix loop (up to 2 retries) | Data Genie validates before execution and attempts LLM-based fixes for invalid SQL |
| **Conversation** | Multi-turn with context retention + clarification questions | Multi-turn with session management, conversation history in DB, clarification questions for ambiguous queries | Both support multi-turn. Databricks has deeper context retention; Data Genie stores last 5 turns per session |
| **Result Summarization** | Natural language summaries of query results | LLM-generated natural language summaries with key insights from result data | Both provide NL summaries. Data Genie includes row counts, key values, and contextual observations |
| **Follow-up Suggestions** | Agentic follow-up questions based on conversation context | Intent-aware follow-up suggestions (heuristic + LLM-based) | Both suggest related questions. Data Genie generates follow-ups based on intent type and query results |
| **Trusted Assets** | Parameterized SQL queries + UDFs with "Trusted" badge on responses | Trusted query fast path with fuzzy matching (60% threshold) and "Trusted" badge (green shield icon) | Databricks supports parameterized queries and locked-down UDFs; Data Genie does fuzzy keyword matching against static curated queries |
| **Semantic Layer** | Knowledge Store (per-space: col descriptions, synonyms, joins with cardinality, measures, filters, dimensions, value dicts, prompt matching) | SQLite tables (column_descs, glossary, metrics, dimensions, filters, joins, trusted_queries) with CRUD API (11 endpoints) | Similar metadata categories. Databricks scopes per-space with value dictionaries; Data Genie has one global semantic layer |
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

1. **Compound AI simulation**: The 8-stage pipeline mirrors Databricks Genie's compound AI approach — intent classification, schema retrieval, context assembly, SQL generation, validation, summarization, and follow-ups — using open-source techniques rather than proprietary models.

2. **Multi-turn conversations**: Session-based conversation history with clarification questions for ambiguous queries and follow-up suggestions, similar to Databricks Genie's agentic reasoning.

3. **Pipeline transparency**: The expandable pipeline stages viewer shows exactly what each AI stage did, how long it took, and what it produced — providing full observability into the compound AI decision process. Databricks does not expose this level of pipeline detail to end users.

4. **Zero-dependency setup**: `poetry install && npm install && start`. No workspace, cluster, or catalog configuration needed.

5. **Cost**: Free to run (excluding OpenAI API costs of ~$0.001/question). Databricks requires a workspace subscription + compute costs.

6. **Fully open and customizable**: Every pipeline stage is modular and replaceable. Swap the intent classifier, plug in a different SQL generator, or add new validation rules without changing the rest of the pipeline. Databricks Genie is a managed service with configuration but no source-level customization.

7. **Offline-capable**: The fallback pattern matcher and keyword-based intent classifier work without any external API. Databricks requires internet + active Databricks workspace.

8. **SQL transparency**: Every response shows the generated SQL, educating users. Databricks shows SQL for trusted queries but is less focused on query education.

9. **Semantic layer browsability**: The frontend Semantic tab lets users explore column descriptions, glossary, metrics, filters — making the metadata visible and discoverable. Databricks Knowledge Store is configured by admins, not browsed by end users.

---

## What would be needed for production parity

### Must-have features

| Feature | Status | Effort | Approach |
|---------|--------|--------|----------|
| ~~Compound AI pipeline~~ | **DONE** | ~~High~~ | 8-stage pipeline: trusted query check, intent classifier, schema retriever, context assembler, SQL generator, SQL validator, result summarizer, follow-up suggester |
| ~~Multi-turn conversations~~ | **DONE** | ~~Medium~~ | Session management with conversation history stored in DB, last 5 turns passed to LLM |
| ~~Agentic reasoning~~ | **DONE** | ~~High~~ | Clarification questions for ambiguous queries, follow-up suggestions, multi-turn context |
| ~~Result summarization~~ | **DONE** | ~~Medium~~ | LLM-generated natural language summaries of query results |
| ~~SQL validation~~ | **DONE** | ~~Medium~~ | EXPLAIN-based validation with auto-fix loop (up to 2 retries) |
| ~~Column descriptions / metadata~~ | **DONE** | ~~Low~~ | Semantic layer with 7 tables now included in LLM prompts |
| Authentication & RBAC | Not started | High | Integrate OAuth 2.0; per-user permissions on datasets |
| Parameterized trusted queries | Not started | Medium | Template syntax in trusted queries; extract parameters from user questions |
| Benchmarking / quality monitoring | Not started | Medium | Define expected Q&A pairs; run automated accuracy tests |
| Feedback loop | Not started | Low | Thumbs up/down per response; store votes; use for tuning |
| Query caching | Not started | Low | Cache LLM responses keyed by (question, schema_hash) |
| Streaming responses | Not started | Medium | Use OpenAI streaming API + SSE to show SQL as it's generated |
| Data connectors | Not started | High | Add connectors for PostgreSQL, MySQL, Snowflake, BigQuery |
| Value dictionaries / entity matching | Not started | Medium | Store example column values to improve LLM matching for categorical data |

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
| Fine-tuned SQL model | High | Train a domain-specific NL-to-SQL model on organization query patterns |
| Confidence scoring | Medium | Score each response for accuracy/confidence, display to users |
| Per-space instructions | Low | Add text instruction support per dataset/space for domain-specific rules |

---

## Key Architectural Trade-off

Databricks Genie separates its architecture into four independent layers that scale independently:

1. **Presentation** (Genie UI, Dashboards, Mobile, One)
2. **AI** (Compound AI system, per-space configuration)
3. **Compute** (SQL Warehouses, Photon engine, auto-scaling)
4. **Storage + Governance** (Delta Lake, Unity Catalog)

Data Genie collapses these into two layers but simulates the AI layer's compound architecture:

1. **Presentation** (React SPA with multi-turn chat, pipeline stage viewer, follow-up suggestions)
2. **AI + Compute + Storage** (FastAPI with 8-stage compound AI pipeline + SQLite for both query execution and data storage)

The compound AI pipeline is the key architectural similarity — both systems use multiple specialized stages (intent classification, schema retrieval, context assembly, SQL generation, validation) rather than a single monolithic LLM call. The difference is in the implementation:

| Aspect | Databricks Genie | Data Genie |
|--------|-----------------|------------|
| **Models** | Proprietary, fine-tuned for SQL | OpenAI GPT (general-purpose) with rich prompt context |
| **Retrieval** | Unity Catalog metadata + per-space Knowledge Store | Keyword-based table scoring + semantic layer tables |
| **Validation** | Integrated with SQL Warehouse execution | EXPLAIN-based with LLM auto-fix |
| **Orchestration** | Proprietary multi-model orchestration | Sequential pipeline with shared PipelineContext (blackboard) |
| **Reasoning** | Deep agentic reasoning with clarification | Clarification for ambiguous queries + heuristic follow-ups |

This dramatically simplifies deployment and operation but limits scalability. The right choice depends entirely on the use case:

- **Data Genie**: Team of 1-50, datasets under 1M rows, exploratory analytics, learning tool, compound AI prototyping
- **Databricks Genie**: Enterprise, petabyte-scale data, governed access, audit requirements, multi-department deployment
