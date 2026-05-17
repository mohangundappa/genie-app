"""
Compound AI Pipeline — simulates Databricks Genie's multi-model architecture.

Instead of a single LLM call, this module orchestrates a pipeline of AI stages:
1. Intent Classifier — categorizes the question type
2. Schema Retriever — finds relevant tables/columns
3. Context Assembler — pulls matching semantic metadata
4. SQL Generator — generates SQL with focused context
5. SQL Validator — validates via EXPLAIN, auto-fixes if needed
6. Result Summarizer — generates a natural language summary
7. Follow-up Suggester — suggests related questions

Each stage operates independently and passes results forward through a shared
PipelineContext object (blackboard architecture).
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from openai import OpenAI
from app.database import get_db, get_schema_for_prompt, get_setting, execute_query
from app.semantic_layer import (
    get_semantic_context_for_prompt,
    find_trusted_query,
    get_column_descriptions,
    get_glossary,
    get_metrics,
    get_dimensions,
    get_filters,
    get_joins,
)
from app.schema_retriever import (
    hybrid_retrieve_schema,
    record_usage,
    RetrievalResult,
)


# ---------------------------------------------------------------------------
# Pipeline data structures
# ---------------------------------------------------------------------------

@dataclass
class PipelineStage:
    name: str
    status: str = "pending"  # pending | running | completed | skipped | error
    duration_ms: float = 0.0
    output: dict = field(default_factory=dict)


@dataclass
class PipelineContext:
    question: str
    conversation_history: list[dict] = field(default_factory=list)
    session_id: str | None = None

    # Stage outputs
    intent: dict = field(default_factory=dict)
    relevant_tables: list[str] = field(default_factory=list)
    relevant_columns: list[dict] = field(default_factory=list)
    retrieval_result: RetrievalResult | None = None
    semantic_context: str = ""
    sql: str = ""
    explanation: str = ""
    chart_config: dict | None = None
    is_trusted: bool = False
    validation_result: dict = field(default_factory=dict)
    result_summary: str = ""
    follow_ups: list[str] = field(default_factory=list)
    clarification: str | None = None
    needs_clarification: bool = False

    # Pipeline metadata
    stages: list[PipelineStage] = field(default_factory=list)
    total_duration_ms: float = 0.0
    error: str | None = None


# ---------------------------------------------------------------------------
# Stage 1: Intent Classifier
# ---------------------------------------------------------------------------

INTENT_TYPES = {
    "aggregation": ["total", "sum", "count", "average", "avg", "mean", "how many",
                     "how much", "aggregate", "overall"],
    "ranking": ["top", "bottom", "highest", "lowest", "best", "worst", "most",
                "least", "greatest", "largest", "smallest", "rank"],
    "trend": ["trend", "over time", "by month", "by year", "by quarter",
              "monthly", "yearly", "quarterly", "growth", "change", "timeline"],
    "comparison": ["compare", "vs", "versus", "difference", "between",
                   "relative", "more than", "less than"],
    "lookup": ["show", "list", "display", "find", "get", "what is", "who is",
               "where is", "which", "details"],
    "filter": ["where", "only", "active", "inactive", "above", "below",
               "greater", "less", "between", "status"],
    "distribution": ["distribution", "breakdown", "by category", "by type",
                     "by region", "by department", "grouped", "per"],
}


def classify_intent(ctx: PipelineContext, client: OpenAI | None) -> None:
    stage = PipelineStage(name="intent_classifier")
    stage.status = "running"
    start = time.time()

    q_lower = ctx.question.lower()

    if client:
        try:
            response = client.chat.completions.create(
                model=_get_model(),
                messages=[
                    {"role": "system", "content": (
                        "Classify the user's data question. Respond with JSON only:\n"
                        '{"intent": "<type>", "entities": ["<entity1>", ...], '
                        '"ambiguous": <true/false>, "clarification_needed": "<question or null>"}\n\n'
                        "Intent types: aggregation, ranking, trend, comparison, lookup, filter, distribution\n"
                        "Entities: extract table names, column names, business terms, numeric thresholds.\n"
                        "Set ambiguous=true if the question is vague or could map to multiple tables/columns.\n"
                        "If ambiguous, suggest a clarification_needed question to ask the user."
                    )},
                    {"role": "user", "content": ctx.question},
                ],
                temperature=0,
                max_tokens=300,
            )
            content = response.choices[0].message.content or ""
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
            ctx.intent = json.loads(content)

            if ctx.intent.get("ambiguous") and ctx.intent.get("clarification_needed"):
                # Check conversation history — if user already answered a clarification, don't re-ask
                if not ctx.conversation_history:
                    ctx.needs_clarification = True
                    ctx.clarification = ctx.intent["clarification_needed"]
        except Exception:
            # Fall back to keyword-based classification
            ctx.intent = _keyword_classify(q_lower)
    else:
        ctx.intent = _keyword_classify(q_lower)

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed"
    stage.output = ctx.intent
    ctx.stages.append(stage)


def _keyword_classify(q_lower: str) -> dict:
    scores: dict[str, int] = {}
    entities: list[str] = []
    for intent_type, keywords in INTENT_TYPES.items():
        score = sum(1 for kw in keywords if kw in q_lower)
        if score > 0:
            scores[intent_type] = score

    best_intent = max(scores, key=scores.get) if scores else "lookup"

    # Extract simple entities
    table_keywords = {
        "country": "world_countries", "countries": "world_countries",
        "population": "world_countries", "gdp": "world_countries",
        "sales": "sales_orders", "order": "sales_orders", "revenue": "sales_orders",
        "profit": "sales_orders", "customer": "sales_orders",
        "employee": "employees", "salary": "employees", "department": "employees",
        "product": "product_inventory", "inventory": "product_inventory",
        "stock": "product_inventory",
    }
    for kw, table in table_keywords.items():
        if kw in q_lower and table not in entities:
            entities.append(table)

    return {
        "intent": best_intent,
        "entities": entities,
        "ambiguous": False,
        "clarification_needed": None,
    }


# ---------------------------------------------------------------------------
# Stage 2: Schema Retriever (Hybrid — 6-level retrieval)
# ---------------------------------------------------------------------------

def retrieve_schema(ctx: PipelineContext, client: OpenAI | None = None) -> None:
    stage = PipelineStage(name="schema_retriever")
    stage.status = "running"
    start = time.time()

    # Use hybrid retrieval with all 6 levels
    retrieval = hybrid_retrieve_schema(
        question=ctx.question,
        intent=ctx.intent,
        client=client,
        use_llm=client is not None,
    )

    ctx.relevant_tables = retrieval.tables
    ctx.relevant_columns = retrieval.relevant_columns
    ctx.retrieval_result = retrieval

    # Build signal summary for stage output
    signal_counts = {
        name: len(scores)
        for name, scores in retrieval.retrieval_signals.items()
        if scores
    }

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed"
    stage.output = {
        "tables": retrieval.tables,
        "table_scores": retrieval.table_scores,
        "column_count": len(retrieval.relevant_columns),
        "value_matches": len(retrieval.value_matches),
        "filter_hints": retrieval.filter_hints,
        "signals_used": signal_counts,
        "method": retrieval.method_summary,
    }
    ctx.stages.append(stage)


# ---------------------------------------------------------------------------
# Stage 3: Context Assembler
# ---------------------------------------------------------------------------

def assemble_context(ctx: PipelineContext) -> None:
    stage = PipelineStage(name="context_assembler")
    stage.status = "running"
    start = time.time()

    parts = []
    q_lower = ctx.question.lower()

    # Column descriptions (filtered to relevant tables)
    if ctx.relevant_columns:
        parts.append("## Column Descriptions")
        current_table = None
        for col in ctx.relevant_columns:
            if col["table_name"] != current_table:
                current_table = col["table_name"]
                parts.append(f"\n### Table: {current_table}")
            biz = f' (business name: "{col["business_name"]}")' if col.get("business_name") else ""
            fmt = f" [format: {col['data_format']}]" if col.get("data_format") else ""
            parts.append(f"- {col['column_name']}: {col['description']}{biz}{fmt}")

    # Value matches from hybrid retriever (Level 1)
    if ctx.retrieval_result and ctx.retrieval_result.value_matches:
        parts.append("\n## Value Matches (exact data values found in question)")
        for vm in ctx.retrieval_result.value_matches:
            parts.append(f"- {vm['detail']}")

    # Filter hints from LLM schema selection (Level 4)
    if ctx.retrieval_result and ctx.retrieval_result.filter_hints:
        parts.append("\n## Filter Hints (suggested WHERE clauses)")
        for fh in ctx.retrieval_result.filter_hints:
            parts.append(f"- {fh}")

    # Column statistics for relevant tables (Level 2)
    if ctx.retrieval_result and ctx.retrieval_result.column_stats:
        parts.append("\n## Column Statistics (data profiling)")
        for cs in ctx.retrieval_result.column_stats:
            stat_parts = [f"{cs['table_name']}.{cs['column_name']}"]
            if cs.get('distinct_count') is not None:
                stat_parts.append(f"distinct={cs['distinct_count']}")
            if cs.get('min_value') is not None and cs.get('max_value') is not None:
                stat_parts.append(f"range=[{cs['min_value']}..{cs['max_value']}]")
            if cs.get('is_categorical'):
                stat_parts.append("categorical")
                if cs.get('sample_values'):
                    try:
                        samples = json.loads(cs['sample_values'])
                        stat_parts.append(f"values={samples[:5]}")
                    except Exception:
                        pass
            parts.append(f"- {' | '.join(stat_parts)}")

    # Glossary (filtered by relevance)
    glossary = get_glossary()
    relevant_glossary = []
    for g in glossary:
        term_lower = g["term"].lower()
        synonyms = (g.get("synonyms") or "").lower()
        if (term_lower in q_lower or
            any(s.strip() in q_lower for s in synonyms.split(",") if s.strip()) or
            (g.get("mapped_table") and g["mapped_table"] in ctx.relevant_tables)):
            relevant_glossary.append(g)

    if relevant_glossary:
        parts.append("\n## Business Glossary (matching terms)")
        for g in relevant_glossary:
            synonyms = f" (also known as: {g['synonyms']})" if g.get("synonyms") else ""
            mapping = ""
            if g.get("mapped_table") and g.get("mapped_column"):
                mapping = f" -> {g['mapped_table']}.{g['mapped_column']}"
            elif g.get("mapped_table"):
                mapping = f" -> {g['mapped_table']}"
            parts.append(f"- **{g['term']}**: {g['definition']}{mapping}{synonyms}")

    # Metrics (filtered to relevant tables)
    metrics = get_metrics()
    relevant_metrics = [m for m in metrics if m["table_name"] in ctx.relevant_tables]
    if relevant_metrics:
        parts.append("\n## Metrics (use these exact expressions)")
        for m in relevant_metrics:
            parts.append(f"- **{m['name']}** ({m['table_name']}): `{m['expression']}` - {m['description']}")

    # Dimensions (filtered to relevant tables)
    dimensions = get_dimensions()
    relevant_dims = [d for d in dimensions if d["table_name"] in ctx.relevant_tables]
    if relevant_dims:
        parts.append("\n## Dimensions (GROUP BY columns)")
        for d in relevant_dims:
            parts.append(f"- **{d['name']}** ({d['table_name']}): `{d['column_name']}`")

    # Filters (filtered to relevant tables)
    filters = get_filters()
    relevant_filters = [f for f in filters if f["table_name"] in ctx.relevant_tables]
    if relevant_filters:
        parts.append("\n## Filters")
        for f in relevant_filters:
            parts.append(f"- **{f['name']}** ({f['table_name']}): `{f['expression']}`")

    # Joins (only if multiple tables are involved)
    if len(ctx.relevant_tables) > 1:
        joins = get_joins()
        relevant_joins = [
            j for j in joins
            if j["left_table"] in ctx.relevant_tables or j["right_table"] in ctx.relevant_tables
        ]
        if relevant_joins:
            parts.append("\n## Join Relationships")
            for j in relevant_joins:
                parts.append(f"- {j['left_table']} {j['join_type']} JOIN {j['right_table']} ON {j['on_clause']}")

    ctx.semantic_context = "\n".join(parts)

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed"
    stage.output = {
        "context_length": len(ctx.semantic_context),
        "glossary_terms_matched": len(relevant_glossary),
        "metrics_included": len(relevant_metrics),
        "dimensions_included": len(relevant_dims),
        "filters_included": len(relevant_filters),
    }
    ctx.stages.append(stage)


# ---------------------------------------------------------------------------
# Stage 4: SQL Generator
# ---------------------------------------------------------------------------

SQL_GENERATOR_PROMPT = """You are an expert SQL analyst in a compound AI pipeline. You convert natural language questions into SQLite SQL queries.

You have access to these tables:
{schema}

## Semantic Layer (filtered for this question)
{semantic_context}

{conversation_context}

Rules:
1. ONLY generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, or any DDL.
2. Use proper SQLite syntax.
3. Use single quotes for string literals.
4. Use exact column names from the schema.
5. Dates are TEXT in 'YYYY-MM-DD' format.
6. For "top"/"best", use ORDER BY with LIMIT.
7. Use aggregation functions when appropriate.
8. Use GROUP BY when aggregating across categories.
9. Always alias computed columns.
10. Map business terms using the glossary and metrics above.
11. Use pre-defined filter expressions when they match user intent.
12. If a trusted SQL pattern matches, prefer it.

Respond with JSON:
{{"sql": "<query>", "explanation": "<1-2 sentences>", "chart_type": "<bar|line|pie|area|scatter|none>", "x_axis": "<col>", "y_axis": ["<col>"], "chart_title": "<title>"}}"""


def generate_sql(ctx: PipelineContext, client: OpenAI | None) -> None:
    stage = PipelineStage(name="sql_generator")
    stage.status = "running"
    start = time.time()

    # Build schema for relevant tables only
    schema = _get_filtered_schema(ctx.relevant_tables)

    # Build conversation context for multi-turn
    conv_context = ""
    if ctx.conversation_history:
        conv_context = "## Conversation History (for context)\n"
        for msg in ctx.conversation_history[-5:]:  # Last 5 turns
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                conv_context += f"User: {content}\n"
            elif msg.get("sql"):
                conv_context += f"Assistant generated SQL: {msg['sql']}\n"

    if not client:
        # Fall back to pattern matcher
        from app.nl_to_sql import handle_without_llm
        result = handle_without_llm(ctx.question, schema)
        ctx.sql = result["sql"]
        ctx.explanation = result["explanation"]
        ctx.chart_config = result.get("chart_config")
        stage.duration_ms = (time.time() - start) * 1000
        stage.status = "completed"
        stage.output = {"method": "pattern_matcher", "sql": ctx.sql}
        ctx.stages.append(stage)
        return

    prompt = SQL_GENERATOR_PROMPT.format(
        schema=schema,
        semantic_context=ctx.semantic_context,
        conversation_context=conv_context,
    )

    try:
        messages = [{"role": "system", "content": prompt}]

        # Add conversation history as chat messages for multi-turn
        for msg in ctx.conversation_history[-5:]:
            if msg.get("role") == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif msg.get("role") == "assistant" and msg.get("content"):
                messages.append({"role": "assistant", "content": msg["content"]})

        messages.append({"role": "user", "content": ctx.question})

        response = client.chat.completions.create(
            model=_get_model(),
            messages=messages,
            temperature=0,
            max_tokens=1000,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        result = json.loads(content)
        ctx.sql = result.get("sql", "")
        ctx.explanation = result.get("explanation", "")
        chart_type = result.get("chart_type", "none")
        if chart_type != "none":
            ctx.chart_config = {
                "chart_type": chart_type,
                "x_axis": result.get("x_axis", ""),
                "y_axis": result.get("y_axis", []),
                "chart_title": result.get("chart_title", ""),
            }

        stage.output = {"method": "llm", "sql": ctx.sql}
    except json.JSONDecodeError as e:
        ctx.error = f"Failed to parse LLM response: {e}"
        stage.output = {"method": "llm", "error": str(e)}
    except Exception as e:
        ctx.error = f"LLM error: {e}"
        stage.output = {"method": "llm", "error": str(e)}

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed" if not ctx.error else "error"
    ctx.stages.append(stage)


def _get_filtered_schema(tables: list[str]) -> str:
    with get_db() as conn:
        parts = []
        for table in tables:
            try:
                col_cursor = conn.execute(f"PRAGMA table_info('{table}')")
                columns = col_cursor.fetchall()
                if columns:
                    cols = ", ".join([f"{c['name']} ({c['type']})" for c in columns])
                    count_cursor = conn.execute(f"SELECT COUNT(*) as cnt FROM '{table}'")
                    row_count = count_cursor.fetchone()["cnt"]
                    parts.append(f"Table: {table} ({row_count} rows)\n  Columns: {cols}")
            except Exception:
                continue
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Stage 5: SQL Validator
# ---------------------------------------------------------------------------

def validate_sql(ctx: PipelineContext, client: OpenAI | None) -> None:
    stage = PipelineStage(name="sql_validator")
    stage.status = "running"
    start = time.time()

    if not ctx.sql:
        stage.status = "skipped"
        stage.output = {"reason": "no SQL to validate"}
        ctx.stages.append(stage)
        return

    # Safety check
    sql_upper = ctx.sql.strip().upper()
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        ctx.error = "Generated SQL is not a SELECT query"
        stage.status = "error"
        stage.output = {"error": "not a SELECT query"}
        ctx.stages.append(stage)
        return

    # Try EXPLAIN to validate syntax
    try:
        with get_db() as conn:
            conn.execute(f"EXPLAIN QUERY PLAN {ctx.sql}")
        ctx.validation_result = {"valid": True, "fixed": False}
        stage.output = {"valid": True, "fixed": False}
    except Exception as explain_error:
        error_msg = str(explain_error)
        ctx.validation_result = {"valid": False, "error": error_msg}

        # Try to auto-fix with LLM
        if client:
            try:
                fix_response = client.chat.completions.create(
                    model=_get_model(),
                    messages=[
                        {"role": "system", "content": (
                            "The following SQL query has an error. Fix it and return ONLY the corrected SQL query, "
                            "no explanation, no markdown, just the raw SQL.\n\n"
                            f"Error: {error_msg}\n\n"
                            f"Available tables and schemas:\n{_get_filtered_schema(ctx.relevant_tables)}"
                        )},
                        {"role": "user", "content": ctx.sql},
                    ],
                    temperature=0,
                    max_tokens=500,
                )
                fixed_sql = fix_response.choices[0].message.content or ""
                fixed_sql = fixed_sql.strip()
                if fixed_sql.startswith("```"):
                    fixed_sql = re.sub(r"^```(?:sql)?\n?", "", fixed_sql)
                    fixed_sql = re.sub(r"\n?```$", "", fixed_sql)

                # Verify the fix
                with get_db() as conn:
                    conn.execute(f"EXPLAIN QUERY PLAN {fixed_sql}")

                ctx.sql = fixed_sql
                ctx.validation_result = {"valid": True, "fixed": True, "original_error": error_msg}
                stage.output = {"valid": True, "fixed": True}
            except Exception:
                ctx.validation_result = {"valid": False, "error": error_msg, "fix_failed": True}
                stage.output = {"valid": False, "fix_failed": True}
        else:
            stage.output = {"valid": False, "error": error_msg}

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed"
    ctx.stages.append(stage)


# ---------------------------------------------------------------------------
# Stage 6: Result Summarizer
# ---------------------------------------------------------------------------

def summarize_results(ctx: PipelineContext, client: OpenAI | None, rows: list[dict], columns: list[str]) -> None:
    stage = PipelineStage(name="result_summarizer")
    stage.status = "running"
    start = time.time()

    if not rows:
        ctx.result_summary = "The query returned no results."
        stage.status = "completed"
        stage.output = {"summary": ctx.result_summary}
        stage.duration_ms = (time.time() - start) * 1000
        ctx.stages.append(stage)
        return

    row_count = len(rows)

    if client:
        try:
            # Send a sample of results for summarization
            sample = rows[:10]
            sample_str = json.dumps(sample, default=str, indent=2)

            response = client.chat.completions.create(
                model=_get_model(),
                messages=[
                    {"role": "system", "content": (
                        "You are a data analyst. Summarize the query results in 1-2 natural language sentences. "
                        "Highlight key findings, trends, or notable values. Be concise and specific with numbers. "
                        "Do not describe the SQL or the query itself — just the findings."
                    )},
                    {"role": "user", "content": (
                        f"Question: {ctx.question}\n"
                        f"Total rows: {row_count}\n"
                        f"Columns: {', '.join(columns)}\n"
                        f"Sample data (first {len(sample)} rows):\n{sample_str}"
                    )},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            ctx.result_summary = response.choices[0].message.content or ""
            ctx.result_summary = ctx.result_summary.strip()
        except Exception:
            ctx.result_summary = f"Returned {row_count} row{'s' if row_count != 1 else ''}."
    else:
        # Simple heuristic summary
        if row_count == 1 and len(columns) <= 3:
            vals = [f"{k}: {v}" for k, v in rows[0].items()]
            ctx.result_summary = f"Result: {', '.join(vals)}"
        else:
            ctx.result_summary = f"Returned {row_count} row{'s' if row_count != 1 else ''}."

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed"
    stage.output = {"summary": ctx.result_summary}
    ctx.stages.append(stage)


# ---------------------------------------------------------------------------
# Stage 7: Follow-up Suggester
# ---------------------------------------------------------------------------

def suggest_follow_ups(ctx: PipelineContext, client: OpenAI | None) -> None:
    stage = PipelineStage(name="follow_up_suggester")
    stage.status = "running"
    start = time.time()

    if client:
        try:
            response = client.chat.completions.create(
                model=_get_model(),
                messages=[
                    {"role": "system", "content": (
                        "Based on the user's data question and the tables available, suggest 3 natural follow-up "
                        "questions they might want to ask next. Return a JSON array of strings.\n"
                        f"Available tables: {', '.join(ctx.relevant_tables)}\n"
                        "Keep questions concise and actionable. Vary the type (drill-down, compare, trend, etc)."
                    )},
                    {"role": "user", "content": (
                        f"Original question: {ctx.question}\n"
                        f"Result summary: {ctx.result_summary}"
                    )},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            content = response.choices[0].message.content or ""
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
            ctx.follow_ups = json.loads(content)
            if not isinstance(ctx.follow_ups, list):
                ctx.follow_ups = []
        except Exception:
            ctx.follow_ups = _heuristic_follow_ups(ctx)
    else:
        ctx.follow_ups = _heuristic_follow_ups(ctx)

    stage.duration_ms = (time.time() - start) * 1000
    stage.status = "completed"
    stage.output = {"follow_ups": ctx.follow_ups}
    ctx.stages.append(stage)


def _heuristic_follow_ups(ctx: PipelineContext) -> list[str]:
    follow_ups = []
    intent = ctx.intent.get("intent", "lookup")
    tables = ctx.relevant_tables

    suggestions_map = {
        "world_countries": [
            "What are the top 5 countries by life expectancy?",
            "Compare GDP per capita across continents",
            "Show population distribution by continent",
        ],
        "sales_orders": [
            "Show monthly revenue trend",
            "What is the profit margin by product category?",
            "Which region has the highest average order value?",
        ],
        "employees": [
            "What is the average salary by department?",
            "Show employee count by office location",
            "Who are the top performers with rating above 4.5?",
        ],
        "product_inventory": [
            "Which products are below reorder level?",
            "Show total stock value by warehouse",
            "What are the highest rated products?",
        ],
    }

    for table in tables[:2]:
        if table in suggestions_map:
            for s in suggestions_map[table]:
                if s.lower() != ctx.question.lower() and len(follow_ups) < 3:
                    follow_ups.append(s)

    return follow_ups[:3]


# ---------------------------------------------------------------------------
# Conversation Session Management
# ---------------------------------------------------------------------------

def init_conversation_tables():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sql_query TEXT,
                result_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES conversation_sessions(id)
            )
        """)


def get_conversation_history(session_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, sql_query as sql FROM conversation_messages "
            "WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_conversation_message(session_id: str, role: str, content: str,
                               sql_query: str | None = None,
                               result_summary: str | None = None):
    with get_db() as conn:
        # Ensure session exists
        conn.execute(
            "INSERT OR IGNORE INTO conversation_sessions (id) VALUES (?)",
            (session_id,),
        )
        conn.execute(
            "INSERT INTO conversation_messages (session_id, role, content, sql_query, result_summary) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, sql_query, result_summary),
        )
        conn.execute(
            "UPDATE conversation_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )


def get_all_sessions() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT s.id, s.created_at, s.updated_at, "
            "(SELECT content FROM conversation_messages WHERE session_id = s.id AND role = 'user' ORDER BY created_at ASC LIMIT 1) as first_question, "
            "(SELECT COUNT(*) FROM conversation_messages WHERE session_id = s.id) as message_count "
            "FROM conversation_sessions s ORDER BY s.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Main Pipeline Orchestrator
# ---------------------------------------------------------------------------

def _get_client() -> OpenAI | None:
    api_key = get_setting("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _get_model() -> str:
    return get_setting("openai_model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def run_compound_pipeline(question: str, session_id: str | None = None) -> dict:
    """
    Run the full compound AI pipeline.

    Returns a dict with:
    - All fields from AskResponse (backward compatible)
    - pipeline_stages: list of stage metadata
    - result_summary: NL summary of results
    - follow_ups: suggested follow-up questions
    - session_id: conversation session ID
    - is_trusted: whether a trusted query was used
    - needs_clarification: whether clarification is needed
    - clarification: the clarification question (if needed)
    """
    pipeline_start = time.time()
    client = _get_client()

    # Initialize context
    ctx = PipelineContext(question=question, session_id=session_id)

    # Load conversation history if session exists
    if session_id:
        ctx.conversation_history = get_conversation_history(session_id)

    # Save user message to conversation
    if session_id:
        save_conversation_message(session_id, "user", question)

    # --- Stage 0: Check Trusted Queries (fast path) ---
    trusted_stage = PipelineStage(name="trusted_query_check")
    trusted_stage.status = "running"
    trusted_start = time.time()

    trusted = find_trusted_query(question)
    if trusted:
        ctx.sql = trusted["sql_query"]
        ctx.explanation = f"[Trusted Query] {trusted.get('description', 'Matched a curated query pattern')}"
        ctx.is_trusted = True

        # Still suggest chart for trusted queries
        sql_upper = trusted["sql_query"].upper()
        if "GROUP BY" in sql_upper:
            sql_lower = trusted["sql_query"].lower()
            chart_type = "line" if ("substr(order_date" in sql_lower or "month" in sql_lower) else "bar"
            ctx.chart_config = {
                "chart_type": chart_type,
                "x_axis": "",
                "y_axis": [],
                "chart_title": trusted.get("description", ""),
            }

        trusted_stage.duration_ms = (time.time() - trusted_start) * 1000
        trusted_stage.status = "completed"
        trusted_stage.output = {"matched": True, "question": trusted["question"]}
        ctx.stages.append(trusted_stage)

        # Execute and continue to summarizer/follow-ups
        query_result = execute_query(ctx.sql)
        if query_result["error"]:
            ctx.error = query_result["error"]
        else:
            # Run summarizer and follow-up suggester
            summarize_results(ctx, client, query_result["rows"], query_result["columns"])
            suggest_follow_ups(ctx, client)

            # Save assistant response
            if session_id:
                save_conversation_message(
                    session_id, "assistant", ctx.explanation,
                    sql_query=ctx.sql, result_summary=ctx.result_summary,
                )

        ctx.total_duration_ms = (time.time() - pipeline_start) * 1000
        return _build_response(ctx, query_result if not ctx.error else None)

    trusted_stage.duration_ms = (time.time() - trusted_start) * 1000
    trusted_stage.status = "completed"
    trusted_stage.output = {"matched": False}
    ctx.stages.append(trusted_stage)

    # --- Stage 1: Intent Classification ---
    classify_intent(ctx, client)

    # Check if clarification is needed
    if ctx.needs_clarification:
        ctx.total_duration_ms = (time.time() - pipeline_start) * 1000
        if session_id:
            save_conversation_message(
                session_id, "assistant", ctx.clarification or "",
            )
        return _build_clarification_response(ctx)

    # --- Stage 2: Schema Retrieval (Hybrid 6-level) ---
    retrieve_schema(ctx, client)

    # --- Stage 3: Context Assembly ---
    assemble_context(ctx)

    # --- Stage 4: SQL Generation ---
    generate_sql(ctx, client)

    if ctx.error:
        ctx.total_duration_ms = (time.time() - pipeline_start) * 1000
        return _build_response(ctx, None)

    # --- Stage 5: SQL Validation ---
    validate_sql(ctx, client)

    if not ctx.sql:
        ctx.total_duration_ms = (time.time() - pipeline_start) * 1000
        return _build_response(ctx, None)

    # --- Execute Query ---
    query_result = execute_query(ctx.sql)

    if query_result["error"]:
        ctx.error = query_result["error"]
        ctx.total_duration_ms = (time.time() - pipeline_start) * 1000
        return _build_response(ctx, None)

    # --- Stage 6: Result Summarization ---
    summarize_results(ctx, client, query_result["rows"], query_result["columns"])

    # --- Stage 7: Follow-up Suggestions ---
    suggest_follow_ups(ctx, client)

    # Save assistant response
    if session_id:
        save_conversation_message(
            session_id, "assistant", ctx.explanation,
            sql_query=ctx.sql, result_summary=ctx.result_summary,
        )

    # --- Record usage patterns for future retrieval (Level 5) ---
    try:
        record_usage(ctx.sql, ctx.relevant_tables)
    except Exception:
        pass  # Non-critical, don't fail pipeline

    ctx.total_duration_ms = (time.time() - pipeline_start) * 1000
    return _build_response(ctx, query_result)


def _build_response(ctx: PipelineContext, query_result: dict | None) -> dict:
    stages_data = []
    for s in ctx.stages:
        stages_data.append({
            "name": s.name,
            "status": s.status,
            "duration_ms": round(s.duration_ms, 1),
            "output": s.output,
        })

    return {
        # Backward-compatible fields
        "question": ctx.question,
        "sql_query": ctx.sql,
        "columns": query_result["columns"] if query_result else [],
        "rows": query_result["rows"] if query_result else [],
        "row_count": query_result["row_count"] if query_result else 0,
        "chart_config": ctx.chart_config,
        "explanation": ctx.explanation,
        "error": ctx.error,
        # Compound AI additions
        "pipeline_stages": stages_data,
        "total_duration_ms": round(ctx.total_duration_ms, 1),
        "result_summary": ctx.result_summary,
        "follow_ups": ctx.follow_ups,
        "session_id": ctx.session_id,
        "is_trusted": ctx.is_trusted,
        "needs_clarification": False,
        "clarification": None,
        "intent": ctx.intent,
    }


def _build_clarification_response(ctx: PipelineContext) -> dict:
    stages_data = []
    for s in ctx.stages:
        stages_data.append({
            "name": s.name,
            "status": s.status,
            "duration_ms": round(s.duration_ms, 1),
            "output": s.output,
        })

    return {
        "question": ctx.question,
        "sql_query": "",
        "columns": [],
        "rows": [],
        "row_count": 0,
        "chart_config": None,
        "explanation": "",
        "error": None,
        "pipeline_stages": stages_data,
        "total_duration_ms": round(ctx.total_duration_ms, 1),
        "result_summary": "",
        "follow_ups": [],
        "session_id": ctx.session_id,
        "is_trusted": False,
        "needs_clarification": True,
        "clarification": ctx.clarification,
        "intent": ctx.intent,
    }
