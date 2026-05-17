# Quick Start & Configuration Guide

## Prerequisites

- **Python 3.12+** with [Poetry](https://python-poetry.org/)
- **Node.js 18+** with npm
- **OpenAI API key** (optional — app works without it using pattern-matching fallback)

---

## Local Development Setup

### 1. Start the Backend

```bash
cd genie-backend
poetry install
poetry run fastapi dev app/main.py --port 8000
```

The backend will:
- Create a `genie.db` SQLite database file
- Load all 4 sample datasets (world_countries, sales_orders, employees, product_inventory)
- Initialize the semantic layer with metadata for all datasets (column descriptions, glossary, metrics, dimensions, filters, joins, trusted queries, instructions)
- Initialize **feedback and benchmarking** tables (query_feedback, benchmark_cases, benchmark_runs) and seed 20 benchmark test cases
- Auto-scan categorical columns and build the **value dictionary** (~1000 entries)
- Auto-profile all columns and build **column statistics** (~52 profiles)
- Initialize the **usage patterns** table for query history learning
- Start the API server at `http://localhost:8000`
- Serve interactive API docs at `http://localhost:8000/docs`

### 2. Start the Frontend

```bash
cd genie-frontend
npm install
npm run dev
```

The frontend will start at `http://localhost:5173`.

### 3. Configure OpenAI (Optional)

**Option A — Via the UI:**
1. Click "Settings" in the bottom-left sidebar.
2. Enter your OpenAI API key.
3. Select a model (default: `gpt-4o-mini`).
4. Click Save.

**Option B — Via environment variable:**
Create a `.env` file in the `genie-backend/` directory:
```
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

**Option C — Skip it:**
The app works without an API key using a rule-based pattern matcher. You'll see a note in responses suggesting you configure a key for better results.

---

## Loaded Datasets

| Dataset | Table Name | Rows | Description |
|---------|-----------|------|-------------|
| World Countries | `world_countries` | 50 | Country demographics: population, GDP, area, life expectancy, literacy rate |
| Sales Orders | `sales_orders` | 500 | E-commerce transactions: dates, customers, products, regions, revenue, profit |
| Employees | `employees` | 150 | HR data: departments, salaries, performance ratings, office locations |
| Product Inventory | `product_inventory` | 40 | Stock management: SKUs, pricing, stock levels, suppliers, warehouses |

---

## Example Questions to Try

### World Countries
- "What are the top 10 countries by GDP?"
- "Show average life expectancy by continent"
- "Which countries have a literacy rate below 70%?"
- "Total population by continent"

### Sales Orders
- "Show total revenue by product category"
- "What are the top 5 customers by total spending?"
- "Average order value by region"
- "Monthly revenue trend for 2024"

### Employees
- "What is the average salary by department?"
- "How many employees are in each office?"
- "Show employees with performance rating above 4.5"
- "Department headcount breakdown"

### Product Inventory
- "Which products are below reorder level?"
- "Show average product rating by category"
- "Total stock value by warehouse"
- "Top 10 products by number of reviews"

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /healthz` | — | Health check |
| `GET /api/datasets` | — | List all datasets with schemas |
| `GET /api/datasets/{name}` | — | Dataset details + sample data |
| `GET /api/datasets/{name}/sample?limit=50` | — | Sample rows from a dataset |
| `POST /api/ask` | `{"question": "..."}` | Ask a natural language question |
| `POST /api/query` | `{"sql": "SELECT ..."}` | Execute raw SQL (SELECT only) |
| `GET /api/history?limit=50` | — | Recent query history |
| `GET /api/settings` | — | Current settings (masked API key) |
| `POST /api/settings` | `{"openai_api_key": "...", "openai_model": "..."}` | Update settings |
| `GET /api/suggested-questions` | — | Curated starter questions |
| `GET /api/schema` | — | Full database schema as text |
| `GET /api/semantic` | — | Full semantic layer summary (columns, glossary, metrics, dimensions, filters, joins, trusted queries) |
| `GET /api/semantic/columns?table_name=X` | — | Column descriptions (optional table filter) |
| `GET /api/semantic/glossary` | — | Business glossary entries |
| `POST /api/semantic/glossary` | `{"term": "...", "definition": "...", ...}` | Add/update glossary entry |
| `DELETE /api/semantic/glossary/{term}` | — | Remove glossary entry |
| `GET /api/semantic/metrics?table_name=X` | — | Metric definitions (optional table filter) |
| `POST /api/semantic/metrics` | `{"name": "...", "expression": "...", ...}` | Add/update metric |
| `DELETE /api/semantic/metrics/{name}?table_name=X` | — | Remove metric |
| `GET /api/semantic/dimensions?table_name=X` | — | Dimension columns |
| `GET /api/semantic/filters?table_name=X` | — | Pre-defined filters |
| `GET /api/semantic/joins` | — | Join relationships |
| `GET /api/semantic/trusted-queries?table_name=X` | — | Trusted SQL queries |
| `POST /api/semantic/trusted-queries` | `{"question": "...", "sql_query": "...", ...}` | Add/update trusted query |
| `DELETE /api/semantic/trusted-queries?question=X` | — | Remove trusted query |
| `GET /api/semantic/value-dictionary?table_name=X` | — | Auto-scanned column values with frequency (optional table filter) |
| `GET /api/semantic/column-stats?table_name=X` | — | Auto-profiled column statistics (optional table filter) |
| `GET /api/semantic/instructions?dataset_name=X` | — | Per-space instructions (optional dataset filter) |
| `POST /api/semantic/instructions` | `{"instruction": "...", "scope": "global", ...}` | Add/update instruction |
| `DELETE /api/semantic/instructions/{id}` | — | Remove instruction |
| `POST /api/feedback` | `{"query_id": "...", "question": "...", "vote": "up"}` | Submit feedback (up/down) |
| `GET /api/feedback/stats` | — | Feedback accuracy stats and recent entries |
| `GET /api/feedback?limit=100` | — | List all feedback entries |
| `GET /api/benchmark/cases?dataset_name=X&difficulty=Y` | — | List benchmark test cases |
| `POST /api/benchmark/cases` | `{"question": "...", "expected_sql": "...", ...}` | Add/update benchmark case |
| `DELETE /api/benchmark/cases?question=X` | — | Remove benchmark case |
| `POST /api/benchmark/run?dataset_name=X&difficulty=Y` | — | Run benchmark suite |
| `GET /api/benchmark/history?limit=20` | — | Benchmark run history |
| `GET /api/benchmark/runs/{id}` | — | Benchmark run detail with per-case results |

---

## Adding Custom Datasets

To add your own dataset:

1. Open `genie-backend/app/database.py`
2. Add a new `CREATE TABLE` statement and data insertion in the `load_sample_datasets()` function.
3. Update the keyword mappings in `genie-backend/app/schema_retriever.py` (in `TABLE_KEYWORDS`) to support the new table in fallback keyword matching.
4. Restart the backend — the new dataset will appear automatically in the sidebar, and the schema retriever will auto-scan the new table's values and column statistics.

If using the LLM mode (with OpenAI API key), no changes to `nl_to_sql.py` are needed — the LLM reads the schema dynamically.

### Adding Semantic Metadata for New Datasets

After adding a dataset, enrich the semantic layer for better query accuracy:

1. **Column descriptions**: Use the `POST /api/semantic/glossary` endpoint or add entries in `semantic_layer.py`'s `_seed_default_semantic_data()` function.
2. **Metrics**: Define common aggregations (e.g., `SUM(amount)`, `AVG(score)`) via `POST /api/semantic/metrics`.
3. **Trusted queries**: Add curated SQL for common questions via `POST /api/semantic/trusted-queries`.
4. **Glossary**: Map business terms to columns via `POST /api/semantic/glossary`.

See [08-semantic-layer.md](./08-semantic-layer.md) for full details on the semantic layer architecture.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `./genie.db` (local), `/data/app.db` (deployed) | SQLite database file path |
| `OPENAI_API_KEY` | — | OpenAI API key (can also set via UI) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `VITE_API_URL` | `http://localhost:8000` | Backend API URL (frontend build-time) |
