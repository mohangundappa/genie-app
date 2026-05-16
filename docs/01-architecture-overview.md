# Architecture Overview

## System Architecture

Data Genie is a full-stack application that mimics the core capabilities of Databricks Genie — an AI-powered natural language interface for querying structured data. The system follows a clean client-server architecture:

```
┌──────────────────────────────────────────────────────────────────┐
│                         React Frontend                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐ │
│  │ Chat UI  │ │  Chart   │ │ Results  │ │ Dataset │ │Semantic │ │
│  │          │ │  Engine  │ │  Table   │ │Explorer │ │ Layer   │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ │Browser  │ │
│       └─────────────┴────────────┴────────────┘      └────┬────┘ │
│                         │ REST API                        │      │
└─────────────────────────┼────────────────────────────────┼──────┘
                          │                                │
┌─────────────────────────┼────────────────────────────────┼──────┐
│                  FastAPI Backend                          │      │
│  ┌──────────┐  ┌────────┴───┐  ┌──────────────────┐  ┌──┴────┐ │
│  │ API      │  │ NL-to-SQL  │  │ Query Execution  │  │Semantic│ │
│  │ Routes   │  │ Engine     │◀─┤ Engine           │  │ Layer  │ │
│  └────┬─────┘  └─────┬──────┘  └────┬────────────┘  │ API    │ │
│       │              │▲             │                └──┬─────┘ │
│       │              │└─semantic────────────────────────┘       │
│  ┌────┴──────────────┴──────────────┴────────────────────────┐  │
│  │                    SQLite Database                         │  │
│  │  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐  │  │
│  │  │ Datasets │ │History │ │ Settings │ │ Semantic Layer │  │  │
│  │  │ (4 tbls) │ │        │ │          │ │   (7 tables)   │  │  │
│  │  └──────────┘ └────────┘ └──────────┘ └────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## High-Level Data Flow

1. **User asks a question** in natural language via the chat UI.
2. **Frontend sends the question** to `POST /api/ask` on the backend.
3. **Backend's NL-to-SQL engine** converts the question to a SQL query:
   - First, checks for a **trusted query** match in the semantic layer (instant result, no LLM needed).
   - If an OpenAI API key is configured, it uses GPT to generate precise SQL, enriched with **semantic layer context** (column descriptions, glossary terms, metric definitions, filters, and join relationships).
   - If no key is configured, it falls back to a rule-based pattern matcher.
4. **Query execution engine** runs the generated SQL against SQLite (read-only SELECT queries only).
5. **Backend returns** the SQL query, results, explanation, and a chart configuration suggestion.
6. **Frontend renders** the response as a conversational message with SQL display, data table, and interactive charts.

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
│   │   ├── main.py               # FastAPI app, routes, CORS
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
