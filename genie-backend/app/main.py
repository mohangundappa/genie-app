import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    execute_query,
    get_all_tables,
    get_query_history,
    get_schema_for_prompt,
    get_setting,
    get_table_sample,
    init_db,
    save_query_history,
    set_setting,
)
from app.models import AskRequest, AskResponse, SettingsUpdate
from app.nl_to_sql import nl_to_sql

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Data Genie", lifespan=lifespan)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/datasets")
async def list_datasets():
    tables = get_all_tables()
    return {"datasets": tables}


@app.get("/api/datasets/{table_name}")
async def get_dataset_details(table_name: str):
    tables = get_all_tables()
    table = next((t for t in tables if t["name"] == table_name), None)
    if not table:
        raise HTTPException(status_code=404, detail="Dataset not found")
    sample = get_table_sample(table_name, limit=10)
    return {"dataset": table, "sample_data": sample}


@app.get("/api/datasets/{table_name}/sample")
async def get_dataset_sample(table_name: str, limit: int = 50):
    tables = get_all_tables()
    table = next((t for t in tables if t["name"] == table_name), None)
    if not table:
        raise HTTPException(status_code=404, detail="Dataset not found")
    sample = get_table_sample(table_name, limit=limit)
    return {"data": sample, "columns": table["columns"]}


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    schema = get_schema_for_prompt()
    result = nl_to_sql(request.question, schema)

    if result.get("error") and not result.get("sql"):
        return AskResponse(
            question=request.question,
            sql_query="",
            columns=[],
            rows=[],
            row_count=0,
            chart_config=None,
            explanation="",
            error=result["error"],
        )

    sql = result["sql"]
    query_result = execute_query(sql)

    if query_result["error"]:
        return AskResponse(
            question=request.question,
            sql_query=sql,
            columns=[],
            rows=[],
            row_count=0,
            chart_config=None,
            explanation=result.get("explanation", ""),
            error=query_result["error"],
        )

    chart_config = result.get("chart_config")
    summary = f"Returned {query_result['row_count']} rows"

    save_query_history(
        question=request.question,
        sql_query=sql,
        result_summary=summary,
        chart_config=json.dumps(chart_config) if chart_config else None,
        dataset_name=request.dataset,
    )

    return AskResponse(
        question=request.question,
        sql_query=sql,
        columns=query_result["columns"],
        rows=query_result["rows"],
        row_count=query_result["row_count"],
        chart_config=chart_config,
        explanation=result.get("explanation", ""),
        error=None,
    )


@app.post("/api/query")
async def run_raw_query(payload: dict):
    sql = payload.get("sql", "")
    if not sql.strip().upper().startswith("SELECT") and not sql.strip().upper().startswith("WITH"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    result = execute_query(sql)
    if result["error"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/history")
async def get_history(limit: int = 50):
    history = get_query_history(limit)
    return {"history": history}


@app.get("/api/settings")
async def get_settings():
    api_key = get_setting("openai_api_key")
    model = get_setting("openai_model") or "gpt-4o-mini"
    return {
        "has_api_key": bool(api_key),
        "api_key_preview": f"sk-...{api_key[-4:]}" if api_key and len(api_key) > 4 else None,
        "model": model,
    }


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    if settings.openai_api_key is not None:
        set_setting("openai_api_key", settings.openai_api_key)
    if settings.openai_model is not None:
        set_setting("openai_model", settings.openai_model)
    return {"status": "ok"}


@app.get("/api/suggested-questions")
async def get_suggested_questions():
    return {
        "questions": [
            {"text": "What are the top 10 countries by GDP?", "dataset": "world_countries", "icon": "globe"},
            {"text": "Show total sales by product category", "dataset": "sales_orders", "icon": "shopping-cart"},
            {"text": "What is the average salary by department?", "dataset": "employees", "icon": "users"},
            {"text": "Which products are low in stock?", "dataset": "product_inventory", "icon": "package"},
            {"text": "Show revenue trend by month", "dataset": "sales_orders", "icon": "trending-up"},
            {"text": "Top 5 countries by population in Asia", "dataset": "world_countries", "icon": "bar-chart"},
            {"text": "How many employees are in each office?", "dataset": "employees", "icon": "building"},
            {"text": "Show profit by region", "dataset": "sales_orders", "icon": "pie-chart"},
        ]
    }


@app.get("/api/schema")
async def get_full_schema():
    return {"schema": get_schema_for_prompt(), "tables": get_all_tables()}
