import json
import os
import re
from openai import OpenAI
from app.database import get_schema_for_prompt, get_setting
from app.semantic_layer import get_semantic_context_for_prompt, find_trusted_query


SYSTEM_PROMPT = """You are an expert SQL analyst. You convert natural language questions into SQLite SQL queries.

You have access to a SQLite database with the following schema:

{schema}

## Semantic Layer (Business Context)

The following semantic layer provides business-friendly names, metric definitions, glossary terms, 
pre-defined filters, and trusted SQL patterns. Use this context to correctly interpret business 
terminology and generate accurate queries.

{semantic_context}

Rules:
1. ONLY generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, or any DDL statements.
2. Use proper SQLite syntax.
3. Always use single quotes for string literals.
4. Be careful with column names - use exact names from the schema.
5. For date comparisons, dates are stored as TEXT in 'YYYY-MM-DD' format.
6. When asked about "top" or "best", use ORDER BY with LIMIT.
7. Use aggregation functions (SUM, AVG, COUNT, MIN, MAX) when appropriate.
8. Use GROUP BY when aggregating across categories.
9. Always alias computed columns for readability.
10. When a user mentions a business term (e.g., "revenue", "headcount", "AOV"), refer to the Business Glossary and Metrics definitions above to map it to the correct column and expression.
11. When a pre-defined filter matches the user's intent (e.g., "active employees", "low stock"), use the exact filter expression from the Semantic Layer.
12. If a Trusted SQL Example closely matches the question, prefer using that pattern.

Respond with a JSON object containing:
- "sql": The SQL query string
- "explanation": A brief explanation of what the query does (1-2 sentences)
- "chart_type": One of "bar", "line", "pie", "area", "scatter", or "none" - suggest a chart type that best visualizes the result
- "x_axis": The column name to use for x-axis (or category in pie chart)
- "y_axis": The column name(s) to use for y-axis (or value in pie chart), as a list of strings
- "chart_title": A title for the chart

Only respond with the JSON object, no other text."""


def get_openai_client() -> OpenAI | None:
    api_key = get_setting("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def get_model() -> str:
    return get_setting("openai_model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def nl_to_sql(question: str, schema: str) -> dict:
    # First, check if there's a trusted query that matches
    trusted = find_trusted_query(question)
    if trusted:
        return {
            "sql": trusted["sql_query"],
            "explanation": f"[Trusted Query] {trusted['description'] or 'Matched a curated query pattern'}",
            "chart_config": _suggest_chart_for_trusted(trusted),
            "error": None,
        }

    client = get_openai_client()
    if not client:
        return handle_without_llm(question, schema)

    model = get_model()
    semantic_context = get_semantic_context_for_prompt()
    prompt = SYSTEM_PROMPT.format(schema=schema, semantic_context=semantic_context)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
            max_tokens=1000,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        result = json.loads(content)
        return {
            "sql": result.get("sql", ""),
            "explanation": result.get("explanation", ""),
            "chart_config": {
                "chart_type": result.get("chart_type", "none"),
                "x_axis": result.get("x_axis", ""),
                "y_axis": result.get("y_axis", []),
                "chart_title": result.get("chart_title", ""),
            }
            if result.get("chart_type", "none") != "none"
            else None,
            "error": None,
        }
    except json.JSONDecodeError as e:
        return {
            "sql": "",
            "explanation": "",
            "chart_config": None,
            "error": f"Failed to parse LLM response: {e}",
        }
    except Exception as e:
        return {
            "sql": "",
            "explanation": "",
            "chart_config": None,
            "error": f"LLM error: {e}",
        }


def handle_without_llm(question: str, schema: str) -> dict:
    """Fallback: pattern-match common questions to SQL queries."""
    q = question.lower().strip()

    # Parse which table the question is about
    table_map = {
        "country": "world_countries",
        "countries": "world_countries",
        "population": "world_countries",
        "gdp": "world_countries",
        "continent": "world_countries",
        "sales": "sales_orders",
        "order": "sales_orders",
        "orders": "sales_orders",
        "revenue": "sales_orders",
        "profit": "sales_orders",
        "customer": "sales_orders",
        "product_category": "sales_orders",
        "employee": "employees",
        "employees": "employees",
        "salary": "employees",
        "department": "employees",
        "hire": "employees",
        "inventory": "product_inventory",
        "stock": "product_inventory",
        "product": "product_inventory",
        "sku": "product_inventory",
        "warehouse": "product_inventory",
    }

    target_table = None
    for keyword, table in table_map.items():
        if keyword in q:
            target_table = table
            break

    if not target_table:
        target_table = "sales_orders"

    # Common query patterns
    if any(w in q for w in ["how many", "count", "total number"]):
        if "by" in q:
            group_col = _guess_group_column(q, target_table)
            sql = f"SELECT {group_col}, COUNT(*) as count FROM {target_table} GROUP BY {group_col} ORDER BY count DESC"
            explanation = f"Count of records grouped by {group_col}"
            chart = {"chart_type": "bar", "x_axis": group_col, "y_axis": ["count"], "chart_title": explanation}
        else:
            sql = f"SELECT COUNT(*) as total_count FROM {target_table}"
            explanation = f"Total count of records in {target_table}"
            chart = None
    elif any(w in q for w in ["average", "avg", "mean"]):
        num_col = _guess_numeric_column(q, target_table)
        group_col = _guess_group_column(q, target_table)
        if group_col:
            sql = f"SELECT {group_col}, ROUND(AVG({num_col}), 2) as avg_{num_col} FROM {target_table} GROUP BY {group_col} ORDER BY avg_{num_col} DESC"
            explanation = f"Average {num_col} by {group_col}"
            chart = {"chart_type": "bar", "x_axis": group_col, "y_axis": [f"avg_{num_col}"], "chart_title": explanation}
        else:
            sql = f"SELECT ROUND(AVG({num_col}), 2) as avg_{num_col} FROM {target_table}"
            explanation = f"Average {num_col}"
            chart = None
    elif any(w in q for w in ["top", "highest", "largest", "most", "best", "greatest"]):
        num_col = _guess_numeric_column(q, target_table)
        limit = _extract_number(q) or 10
        name_col = _guess_name_column(target_table)
        sql = f"SELECT {name_col}, {num_col} FROM {target_table} ORDER BY {num_col} DESC LIMIT {limit}"
        explanation = f"Top {limit} by {num_col}"
        chart = {"chart_type": "bar", "x_axis": name_col, "y_axis": [num_col], "chart_title": explanation}
    elif any(w in q for w in ["bottom", "lowest", "smallest", "least", "worst"]):
        num_col = _guess_numeric_column(q, target_table)
        limit = _extract_number(q) or 10
        name_col = _guess_name_column(target_table)
        sql = f"SELECT {name_col}, {num_col} FROM {target_table} ORDER BY {num_col} ASC LIMIT {limit}"
        explanation = f"Bottom {limit} by {num_col}"
        chart = {"chart_type": "bar", "x_axis": name_col, "y_axis": [num_col], "chart_title": explanation}
    elif any(w in q for w in ["sum", "total"]) and "number" not in q:
        num_col = _guess_numeric_column(q, target_table)
        group_col = _guess_group_column(q, target_table)
        if group_col:
            sql = f"SELECT {group_col}, ROUND(SUM({num_col}), 2) as total_{num_col} FROM {target_table} GROUP BY {group_col} ORDER BY total_{num_col} DESC"
            explanation = f"Total {num_col} by {group_col}"
            chart = {"chart_type": "bar", "x_axis": group_col, "y_axis": [f"total_{num_col}"], "chart_title": explanation}
        else:
            sql = f"SELECT ROUND(SUM({num_col}), 2) as total_{num_col} FROM {target_table}"
            explanation = f"Total {num_col}"
            chart = None
    elif "show" in q or "list" in q or "all" in q or "display" in q:
        sql = f"SELECT * FROM {target_table} LIMIT 100"
        explanation = f"Showing records from {target_table} (limited to 100)"
        chart = None
    else:
        sql = f"SELECT * FROM {target_table} LIMIT 25"
        explanation = f"Showing sample records from {target_table}"
        chart = None

    return {
        "sql": sql,
        "explanation": explanation + " (Note: For more accurate results, configure your OpenAI API key in Settings)",
        "chart_config": chart,
        "error": None,
    }


def _guess_group_column(q: str, table: str) -> str:
    group_maps = {
        "world_countries": {"continent": "continent", "region": "continent", "currency": "currency"},
        "sales_orders": {"region": "region", "category": "product_category", "segment": "customer_segment", "city": "city", "customer": "customer_name", "status": "order_status", "product": "product_category", "year": "substr(order_date,1,4)", "month": "substr(order_date,1,7)"},
        "employees": {"department": "department", "office": "office_location", "location": "office_location", "status": "employment_status", "title": "job_title", "job": "job_title"},
        "product_inventory": {"category": "category", "brand": "brand", "supplier": "supplier", "warehouse": "warehouse_location"},
    }
    mapping = group_maps.get(table, {})
    for keyword, col in mapping.items():
        if keyword in q:
            return col
    defaults = {
        "world_countries": "continent",
        "sales_orders": "product_category",
        "employees": "department",
        "product_inventory": "category",
    }
    return defaults.get(table, "id")


def _guess_numeric_column(q: str, table: str) -> str:
    num_maps = {
        "world_countries": {"population": "population", "gdp": "gdp_usd_billion", "area": "area_sq_km", "life": "life_expectancy", "literacy": "literacy_rate"},
        "sales_orders": {"revenue": "total_amount", "amount": "total_amount", "profit": "profit", "quantity": "quantity", "price": "unit_price", "discount": "discount", "shipping": "shipping_cost", "sales": "total_amount"},
        "employees": {"salary": "salary", "bonus": "bonus_pct", "rating": "performance_rating", "performance": "performance_rating"},
        "product_inventory": {"price": "unit_price", "cost": "cost_price", "stock": "stock_quantity", "quantity": "stock_quantity", "rating": "rating", "review": "reviews_count"},
    }
    mapping = num_maps.get(table, {})
    for keyword, col in mapping.items():
        if keyword in q:
            return col
    defaults = {
        "world_countries": "population",
        "sales_orders": "total_amount",
        "employees": "salary",
        "product_inventory": "stock_quantity",
    }
    return defaults.get(table, "id")


def _guess_name_column(table: str) -> str:
    name_map = {
        "world_countries": "country",
        "sales_orders": "customer_name",
        "employees": "first_name || ' ' || last_name",
        "product_inventory": "product_name",
    }
    return name_map.get(table, "id")


def _extract_number(q: str) -> int | None:
    import re
    match = re.search(r'\b(\d+)\b', q)
    return int(match.group(1)) if match else None


def _suggest_chart_for_trusted(trusted: dict) -> dict | None:
    """Suggest a chart config for a trusted query based on SQL analysis."""
    sql = trusted["sql_query"].upper()
    if "GROUP BY" not in sql:
        return None
    # Simple heuristic: if it has GROUP BY, suggest a bar chart
    sql_lower = trusted["sql_query"].lower()
    if "substr(order_date" in sql_lower or "month" in sql_lower:
        chart_type = "line"
    else:
        chart_type = "bar"
    return {
        "chart_type": chart_type,
        "x_axis": "",
        "y_axis": [],
        "chart_title": trusted.get("description", ""),
    }
