# Architecture Overview

## System Architecture

Data Genie is a full-stack application that simulates the core capabilities of Databricks Genie — an AI-powered natural language interface for querying structured data. The system uses a **Compound AI Pipeline** architecture with 8 independent stages, multi-turn conversation support, agentic reasoning, feedback collection, benchmarking, and per-space instructions:

```
┌───────────────────────────────────────────────────────────────────────┐
│                          React Frontend                               │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐ │
│  │ Multi-Turn │ │  Chart   │ │ Results  │ │ Dataset │ │ Semantic  │ │
│  │ Chat UI    │ │  Engine  │ │  Table   │ │Explorer │ │ Layer     │ │
│  │ (sessions, │ │          │ │          │ │         │ │ Browser   │ │
│  │ follow-ups,│ │          │ │          │ │         │ │           │ │
│  │ pipeline,  │ │          │ │          │ │         │ ├───────────┤ │
│  │ feedback)  │ │          │ │          │ │         │ │ Quality   │ │
│  └─────┬──────┘ └────┬─────┘ └────┬─────┘ └────┬───┘ │ Panel     │ │
│        └──────────────┴────────────┴────────────┘     │(feedback, │ │
│                          │ REST API (+ session_id     │benchmark, │ │
│                          │   + query_id)              │instruct.) │ │
│                          │                             └─────┬─────┘ │
└──────────────────────────┼───────────────────────────────────┼───────┘
                           │                                  │
┌──────────────────────────┼──────────────────────────────────┼───────┐
│                    FastAPI Backend                           │       │
│                                                             │       │
│  ┌────────────────── Compound AI Pipeline ────────────────┐ │       │
│  │                                                        │ │       │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐             │ │       │
│  │  │ Intent  │──▶│ Schema  │──▶│ Context │             │ │       │
│  │  │Classify │   │Retrieve │   │Assemble │             │ │       │
│  │  └─────────┘   └─────────┘   └────┬────┘             │ │       │
│  │                                   │                   │ │       │
│  │  ┌─────────┐   ┌─────────┐   ┌────▼────┐             │ │       │
│  │  │ Result  │◀──│   SQL   │◀──│  SQL    │             │ │       │
│  │  │Summarize│   │Validate │   │Generate │             │ │       │
│  │  └────┬────┘   └─────────┘   └─────────┘             │ │       │
│  │       │                                               │ │       │
│  │  ┌────▼────┐                                          │ ┌──┴────┐│
│  │  │Follow-up│    Trusted Query Fast Path ───────────▶  │ │Semanti││
│  │  │Suggest  │                                          │ │c Layer││
│  │  └─────────┘                                          │ │  API  ││
│  └───────────────────────────────────────────────────────┘ └───────┘│
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    SQLite Database                              │  │
│  │  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│  │
│  │  │ Datasets │ │History │ │ Settings │ │ Semantic │ │Sessions││  │
│  │  │ (4 tbls) │ │        │ │          │ │ (7+1 tbl)│ │& Msgs  ││  │
│  │  └──────────┘ └────────┘ └──────────┘ └──────────┘ └────────┘│  │
│  │                                                               │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ Quality Tables (3)                                       │ │  │
│  │  │ query_feedback | benchmark_cases | benchmark_runs         │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Compound AI Pipeline (8 Stages)

Unlike a single LLM call, Data Genie uses a multi-stage compound AI pipeline inspired by Databricks Genie's architecture. Each stage operates independently and passes results forward through a shared `PipelineContext` object (blackboard architecture). Each response includes a `query_id` (stored on `PipelineContext`) for feedback tracking:

| Stage | Name | Purpose |
|-------|------|---------|
| 0 | **Trusted Query Check** | Pre-LLM: matches known questions to curated SQL (instant, no LLM cost). Supports parameterized queries with `{param}` template syntax. |
| 1 | **Intent Classifier** | Categorizes question type (aggregation, ranking, trend, comparison, lookup, filter, distribution) |
| 2 | **Schema Retriever** | 6-level hybrid retrieval: value dictionaries, column stats, embedding search, LLM selection, usage patterns, weighted fusion |
| 3 | **Context Assembler** | Pulls matching glossary terms, metrics, dimensions, filters, and **active instructions** from semantic layer |
| 4 | **SQL Generator** | Generates SQL with focused, filtered context + per-space instructions (LLM or pattern matcher) |
| 5 | **SQL Validator** | Validates SQL via EXPLAIN, auto-fixes syntax errors |
| 6 | **Result Summarizer** | Generates natural language summary of query results |
| 7 | **Follow-up Suggester** | Suggests related questions based on results and intent |

## High-Level Data Flow

1. **User asks a question** in natural language via the multi-turn chat UI (with `session_id`).
2. **Frontend sends the question** to `POST /api/ask` with optional `session_id` for conversation continuity.
3. **Compound AI Pipeline** processes the question through 8 stages (assigning a `query_id` for feedback tracking):
   - **Trusted Query Check**: Checks for a pre-computed query match (instant result, no LLM cost). Supports parameterized queries (e.g., `WHERE region = '{region}'`) with auto-extraction from natural language.
   - **Intent Classifier**: Determines question type (aggregation, ranking, trend, etc.) using LLM or keyword matching.
   - **Schema Retriever**: Finds relevant tables/columns via semantic similarity instead of passing entire schema.
   - **Context Assembler**: Gathers matching glossary terms, metrics, dimensions, filters, and **active instructions** from the semantic layer.
   - **SQL Generator**: Generates SQL with focused context + per-space instructions (LLM with conversation history, or pattern matcher fallback).
   - **SQL Validator**: Validates via EXPLAIN; auto-fixes and retries if invalid.
   - **Result Summarizer**: Produces a natural language summary of results.
   - **Follow-up Suggester**: Generates related follow-up questions.
4. **Query execution engine** runs the generated SQL against SQLite (read-only SELECT queries only).
5. **Backend returns** enriched response with SQL, results, pipeline stage metadata, result summary, follow-ups, session info, and `query_id`.
6. **Frontend renders** the response with pipeline transparency, result summaries, follow-up chips, trusted query badges, clarification prompts, and **feedback buttons** (thumbs up/down).
7. **User provides feedback** via thumbs up/down buttons. Upvotes submit immediately; downvotes prompt for an optional comment before submission. Feedback is tracked per `query_id` and displayed in the Quality panel.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite | Zero-config, embedded, perfect for demo datasets. Avoids external DB dependency. |
| Backend | FastAPI (Python) | Async-first, auto-generated docs, excellent for data/AI workloads. |
| Frontend | React + Vite + Tailwind | Fast dev experience, component-based, utility-first styling. |
| LLM Integration | OpenAI API (optional) | Industry standard, reliable, with graceful fallback when unavailable. |
| Semantic Layer | SQLite tables + API | Business context metadata that enriches LLM prompts and provides trusted query shortcuts. |
| Feedback & Benchmarking | SQLite tables + API | User feedback (thumbs up/down), benchmark test cases, automated accuracy testing. |
| Per-Space Instructions | SQLite table + API | Text rules (global or dataset-scoped) injected into SQL generator prompt. |
| Charts | Recharts | React-native charting, declarative API, good default styling. |
| State Management | React useState | App state is simple enough; no need for Redux/Zustand overhead. |

## Directory Structure

```
genie-app/
├── docs/                          # Documentation (this folder)
├── genie-backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, routes, CORS, session endpoints
│   │   ├── compound_ai.py        # Compound AI pipeline (8 stages + session mgmt)
│   │   ├── schema_retriever.py   # 6-level hybrid schema retrieval engine
│   │   ├── database.py           # SQLite connection, schema, dataset loading
│   │   ├── nl_to_sql.py          # NL-to-SQL engine (LLM + fallback)
│   │   ├── semantic_layer.py     # Semantic layer (metadata, glossary, metrics, instructions)
│   │   ├── feedback.py           # Feedback collection + benchmarking engine
│   │   └── models.py             # Pydantic request/response models
│   ├── pyproject.toml            # Python dependencies (Poetry)
│   └── .env                      # Environment variables
├── genie-frontend/
│   ├── src/
│   │   ├── App.tsx               # Main app shell (chat, feedback buttons, quality panel)
│   │   ├── components/
│   │   │   ├── ChartView.tsx     # Multi-type chart renderer
│   │   │   ├── ResultsTable.tsx  # Tabular data display
│   │   │   ├── SqlDisplay.tsx    # SQL query viewer with copy
│   │   │   ├── DatasetExplorer.tsx # Sidebar dataset browser
│   │   │   ├── QueryHistory.tsx  # Past queries sidebar
│   │   │   ├── SemanticLayer.tsx # Semantic layer browser (columns, glossary, metrics, filters, joins, queries)
│   │   │   └── SettingsModal.tsx # API key / model configuration
│   │   ├── hooks/
│   │   │   └── useApi.ts         # API client wrapper
│   │   └── types/
│   │       └── index.ts          # TypeScript type definitions
│   ├── .env                      # Frontend env vars (API URL)
│   └── package.json              # Node dependencies
```
