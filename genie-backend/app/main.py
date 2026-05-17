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
from app.compound_ai import (
    run_compound_pipeline,
    init_conversation_tables,
    get_all_sessions,
    get_conversation_history,
)
from app.schema_retriever import (
    init_value_dictionary,
    init_column_stats,
    init_usage_patterns,
    get_value_dictionary,
    get_column_stats,
)
from app.semantic_layer import (
    init_semantic_layer,
    get_full_semantic_summary,
    get_column_descriptions,
    get_glossary,
    get_metrics,
    get_dimensions,
    get_filters,
    get_joins,
    get_trusted_queries,
    upsert_glossary_entry,
    upsert_metric,
    upsert_trusted_query,
    delete_glossary_entry,
    delete_metric,
    delete_trusted_query,
)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_semantic_layer()
    init_conversation_tables()
    init_value_dictionary()
    init_column_stats()
    init_usage_patterns()
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
    # Use compound AI pipeline
    result = run_compound_pipeline(
        question=request.question,
        session_id=request.session_id,
    )

    # Save to query history
    if result.get("sql_query"):
        summary = f"Returned {result['row_count']} rows"
        save_query_history(
            question=request.question,
            sql_query=result["sql_query"],
            result_summary=summary,
            chart_config=json.dumps(result["chart_config"]) if result.get("chart_config") else None,
            dataset_name=request.dataset,
        )

    return AskResponse(
        question=result["question"],
        sql_query=result["sql_query"],
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        chart_config=result["chart_config"],
        explanation=result["explanation"],
        error=result["error"],
        pipeline_stages=result["pipeline_stages"],
        total_duration_ms=result["total_duration_ms"],
        result_summary=result["result_summary"],
        follow_ups=result["follow_ups"],
        session_id=result["session_id"],
        is_trusted=result["is_trusted"],
        needs_clarification=result["needs_clarification"],
        clarification=result["clarification"],
        intent=result["intent"],
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


# ---------------------------------------------------------------------------
# Conversation Session endpoints
# ---------------------------------------------------------------------------

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": get_all_sessions()}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    messages = get_conversation_history(session_id)
    return {"session_id": session_id, "messages": messages}


# ---------------------------------------------------------------------------
# Semantic Layer endpoints
# ---------------------------------------------------------------------------

@app.get("/api/semantic")
async def get_semantic_layer():
    return get_full_semantic_summary()


@app.get("/api/semantic/columns")
async def get_semantic_columns(table_name: str | None = None):
    return {"columns": get_column_descriptions(table_name)}


@app.get("/api/semantic/glossary")
async def get_semantic_glossary():
    return {"glossary": get_glossary()}


@app.post("/api/semantic/glossary")
async def add_glossary_entry(payload: dict):
    upsert_glossary_entry(
        term=payload["term"],
        definition=payload["definition"],
        mapped_table=payload.get("mapped_table"),
        mapped_column=payload.get("mapped_column"),
        synonyms=payload.get("synonyms"),
    )
    return {"status": "ok"}


@app.delete("/api/semantic/glossary/{term}")
async def remove_glossary_entry(term: str):
    delete_glossary_entry(term)
    return {"status": "ok"}


@app.get("/api/semantic/metrics")
async def get_semantic_metrics(table_name: str | None = None):
    return {"metrics": get_metrics(table_name)}


@app.post("/api/semantic/metrics")
async def add_metric(payload: dict):
    upsert_metric(
        name=payload["name"],
        description=payload["description"],
        table_name=payload["table_name"],
        expression=payload["expression"],
        format_type=payload.get("format_type", "number"),
    )
    return {"status": "ok"}


@app.delete("/api/semantic/metrics/{name}")
async def remove_metric(name: str, table_name: str):
    delete_metric(name, table_name)
    return {"status": "ok"}


@app.get("/api/semantic/dimensions")
async def get_semantic_dimensions(table_name: str | None = None):
    return {"dimensions": get_dimensions(table_name)}


@app.get("/api/semantic/filters")
async def get_semantic_filters(table_name: str | None = None):
    return {"filters": get_filters(table_name)}


@app.get("/api/semantic/joins")
async def get_semantic_joins():
    return {"joins": get_joins()}


@app.get("/api/semantic/value-dictionary")
async def get_semantic_value_dictionary(table_name: str | None = None):
    return {"value_dictionary": get_value_dictionary(table_name)}


@app.get("/api/semantic/column-stats")
async def get_semantic_column_stats(table_name: str | None = None):
    return {"column_stats": get_column_stats(table_name)}


@app.get("/api/semantic/trusted-queries")
async def get_semantic_trusted_queries(table_name: str | None = None):
    return {"trusted_queries": get_trusted_queries(table_name)}


@app.post("/api/semantic/trusted-queries")
async def add_trusted_query(payload: dict):
    upsert_trusted_query(
        question=payload["question"],
        sql_query=payload["sql_query"],
        description=payload.get("description"),
        table_name=payload.get("table_name"),
        is_parameterized=payload.get("is_parameterized", 0),
    )
    return {"status": "ok"}


@app.delete("/api/semantic/trusted-queries")
async def remove_trusted_query(question: str):
    delete_trusted_query(question)
    return {"status": "ok"}
