# Architecture Overview

## System Architecture

Data Genie is a full-stack application that simulates the core capabilities of Databricks Genie — an AI-powered natural language interface for querying structured data. The system uses a **Compound AI Pipeline** architecture with 7 independent stages, multi-turn conversation support, and agentic reasoning:

```
┌───────────────────────────────────────────────────────────────────────┐
│                          React Frontend                               │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐ │
│  │ Multi-Turn │ │  Chart   │ │ Results  │ │ Dataset │ │ Semantic  │ │
│  │ Chat UI    │ │  Engine  │ │  Table   │ │Explorer │ │ Layer     │ │
│  │ (sessions, │ │          │ │          │ │         │ │ Browser   │ │
│  │ follow-ups,│ │          │ │          │ │         │ │           │ │
│  │ pipeline)  │ │          │ │          │ │         │ │           │ │
│  └─────┬──────┘ └────┬─────┘ └────┬─────┘ └────┬───┘ └─────┬─────┘ │
│        └──────────────┴────────────┴────────────┘           │       │
│                          │ REST API (+ session_id)          │       │
└──────────────────────────┼──────────────────────────────────┼───────┘
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
│  │  │ (4 tbls) │ │        │ │          │ │ (7 tbls) │ │& Msgs  ││  │
│  │  └──────────┘ └────────┘ └──────────┘ └──────────┘ └────────┘│  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Compound AI Pipeline (7 Stages)

Unlike a single LLM call, Data Genie uses a multi-stage compound AI pipeline inspired by Databricks Genie's architecture. Each stage operates independently and passes results forward through a shared `PipelineContext` object (blackboard architecture):

| Stage | Name | Purpose |
|-------|------|---------|
| 0 | **Trusted Query Check** | Pre-LLM: matches known questions to curated SQL (instant, no LLM cost) |
| 1 | **Intent Classifier** | Categorizes question type (aggregation, ranking, trend, comparison, lookup, filter, distribution) |
| 2 | **Schema Retriever** | Semantically matches relevant tables/columns instead of dumping entire schema |
| 3 | **Context Assembler** | Pulls matching glossary terms, metrics, dimensions, and filters from semantic layer |
| 4 | **SQL Generator** | Generates SQL with focused, filtered context (LLM or pattern matcher) |
| 5 | **SQL Validator** | Validates SQL via EXPLAIN, auto-fixes syntax errors |
| 6 | **Result Summarizer** | Generates natural language summary of query results |
| 7 | **Follow-up Suggester** | Suggests related questions based on results and intent |

## High-Level Data Flow

1. **User asks a question** in natural language via the multi-turn chat UI (with `session_id`).
2. **Frontend sends the question** to `POST /api/ask` with optional `session_id` for conversation continuity.
3. **Compound AI Pipeline** processes the question through 7 stages:
   - **Trusted Query Check**: Checks for a pre-computed query match (instant result, no LLM cost).
   - **Intent Classifier**: Determines question type (aggregation, ranking, trend, etc.) using LLM or keyword matching.
   - **Schema Retriever**: Finds relevant tables/columns via semantic similarity instead of passing entire schema.
   - **Context Assembler**: Gathers matching glossary terms, metrics, dimensions, and filters from the semantic layer.
   - **SQL Generator**: Generates SQL with focused context (LLM with conversation history, or pattern matcher fallback).
   - **SQL Validator**: Validates via EXPLAIN; auto-fixes and retries if invalid.
   - **Result Summarizer**: Produces a natural language summary of results.
   - **Follow-up Suggester**: Generates related follow-up questions.
4. **Query execution engine** runs the generated SQL against SQLite (read-only SELECT queries only).
5. **Backend returns** enriched response with SQL, results, pipeline stage metadata, result summary, follow-ups, and session info.
6. **Frontend renders** the response with pipeline transparency, result summaries, follow-up chips, trusted query badges, and clarification prompts.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite | Zero-config, embedded, perfect for demo datasets. Avoids external DB dependency. |
| Backend | FastAPI (Python) | Async-first, auto-generated docs, excellent for data/AI workloads. |
| Frontend | React + Vite + Tailwind | Fast dev experience, component-based, utility-first styling. |
| LLM Integration | OpenAI API (optional) | Industry standard, reliable, with graceful fallback when unavailable. |
| Semantic Layer | SQLite tables + API | Business context metadata that enriches LLM prompts and provides trusted query shortcuts. |
| Charts | Recharts | React-native charting, declarative API, good default styling. |
| State Management | React useState | App state is simple enough; no need for Redux/Zustand overhead. |

## Directory Structure

```
genie-app/
├── docs/                          # Documentation (this folder)
├── genie-backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, routes, CORS, session endpoints
│   │   ├── compound_ai.py        # Compound AI pipeline (7 stages + session mgmt)
│   │   ├── database.py           # SQLite connection, schema, dataset loading
│   │   ├── nl_to_sql.py          # NL-to-SQL engine (LLM + fallback)
│   │   ├── semantic_layer.py     # Semantic layer (metadata, glossary, metrics)
│   │   └── models.py             # Pydantic request/response models
│   ├── pyproject.toml            # Python dependencies (Poetry)
│   └── .env                      # Environment variables
├── genie-frontend/
│   ├── src/
│   │   ├── App.tsx               # Main application shell
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
