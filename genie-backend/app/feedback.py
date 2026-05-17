"""
Feedback & Benchmarking — quality measurement and improvement loop.

Inspired by Databricks Genie's benchmarking and confidence voting:
1. Feedback Loop — thumbs up/down per response, accuracy tracking
2. Benchmarking — define expected Q&A pairs, run automated accuracy tests
"""

import json
import time
from datetime import datetime
from app.database import get_db, execute_query


# ---------------------------------------------------------------------------
# Schema: create feedback & benchmarking tables
# ---------------------------------------------------------------------------

def init_feedback_tables():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                session_id TEXT,
                question TEXT NOT NULL,
                sql_query TEXT,
                vote TEXT NOT NULL CHECK(vote IN ('up', 'down')),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                expected_sql TEXT NOT NULL,
                expected_result_pattern TEXT,
                dataset_name TEXT,
                tags TEXT,
                difficulty TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_cases INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                failed INTEGER NOT NULL,
                accuracy_pct REAL NOT NULL,
                duration_ms REAL NOT NULL,
                details TEXT NOT NULL
            )
        """)
    _seed_benchmark_cases()


# ---------------------------------------------------------------------------
# Seed: populate with default benchmark cases
# ---------------------------------------------------------------------------

def _seed_benchmark_cases():
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM benchmark_cases")
        if cursor.fetchone()["cnt"] > 0:
            return

        cases = [
            # world_countries
            ("What are the top 10 countries by GDP?",
             "SELECT country, gdp_usd_billion FROM world_countries ORDER BY gdp_usd_billion DESC LIMIT 10",
             '{"min_rows": 10, "max_rows": 10, "required_columns": ["country", "gdp_usd_billion"]}',
             "world_countries", "ranking,gdp", "easy"),
            ("What is the total population of Asia?",
             "SELECT SUM(population) as total_population FROM world_countries WHERE continent = 'Asia'",
             '{"min_rows": 1, "max_rows": 1, "required_columns": ["total_population"]}',
             "world_countries", "aggregation,filter", "easy"),
            ("Which continent has the highest average life expectancy?",
             "SELECT continent, ROUND(AVG(life_expectancy), 1) as avg_life_expectancy FROM world_countries GROUP BY continent ORDER BY avg_life_expectancy DESC LIMIT 1",
             '{"min_rows": 1, "max_rows": 1, "required_columns": ["continent"]}',
             "world_countries", "aggregation,ranking", "medium"),
            ("How many countries are in each continent?",
             "SELECT continent, COUNT(*) as country_count FROM world_countries GROUP BY continent ORDER BY country_count DESC",
             '{"min_rows": 2, "required_columns": ["continent", "country_count"]}',
             "world_countries", "aggregation,distribution", "easy"),
            ("List countries with literacy rate below 70%",
             "SELECT country, literacy_rate FROM world_countries WHERE literacy_rate < 70 ORDER BY literacy_rate ASC",
             '{"min_rows": 1, "required_columns": ["country", "literacy_rate"]}',
             "world_countries", "filter,lookup", "easy"),

            # sales_orders
            ("Show total revenue by product category",
             "SELECT product_category, SUM(total_amount) as total_revenue FROM sales_orders GROUP BY product_category ORDER BY total_revenue DESC",
             '{"min_rows": 4, "max_rows": 4, "required_columns": ["product_category"]}',
             "sales_orders", "aggregation,distribution", "easy"),
            ("What is the average order value?",
             "SELECT ROUND(AVG(total_amount), 2) as avg_order_value FROM sales_orders",
             '{"min_rows": 1, "max_rows": 1}',
             "sales_orders", "aggregation", "easy"),
            ("Show monthly revenue trend for 2024",
             "SELECT substr(order_date,1,7) as month, SUM(total_amount) as revenue FROM sales_orders WHERE order_date LIKE '2024%' GROUP BY month ORDER BY month",
             '{"min_rows": 1, "required_columns": ["month"]}',
             "sales_orders", "trend,aggregation", "medium"),
            ("Which region has the most cancelled orders?",
             "SELECT region, COUNT(*) as cancelled_count FROM sales_orders WHERE order_status = 'Cancelled' GROUP BY region ORDER BY cancelled_count DESC LIMIT 1",
             '{"min_rows": 1, "max_rows": 1, "required_columns": ["region"]}',
             "sales_orders", "filter,ranking", "medium"),
            ("Show profit margin by customer segment",
             "SELECT customer_segment, ROUND(SUM(profit) * 100.0 / SUM(total_amount), 2) as profit_margin FROM sales_orders GROUP BY customer_segment ORDER BY profit_margin DESC",
             '{"min_rows": 2, "required_columns": ["customer_segment", "profit_margin"]}',
             "sales_orders", "aggregation,distribution", "hard"),

            # employees
            ("What is the average salary by department?",
             "SELECT department, ROUND(AVG(salary), 2) as avg_salary FROM employees GROUP BY department ORDER BY avg_salary DESC",
             '{"min_rows": 2, "required_columns": ["department", "avg_salary"]}',
             "employees", "aggregation,distribution", "easy"),
            ("How many active employees are there?",
             "SELECT COUNT(*) as active_count FROM employees WHERE employment_status = 'Active'",
             '{"min_rows": 1, "max_rows": 1, "required_columns": ["active_count"]}',
             "employees", "filter,aggregation", "easy"),
            ("Who are the top 5 highest paid employees?",
             "SELECT first_name, last_name, salary FROM employees ORDER BY salary DESC LIMIT 5",
             '{"min_rows": 5, "max_rows": 5, "required_columns": ["first_name", "last_name", "salary"]}',
             "employees", "ranking", "easy"),
            ("Show average performance rating by office location",
             "SELECT office_location, ROUND(AVG(performance_rating), 2) as avg_rating FROM employees GROUP BY office_location ORDER BY avg_rating DESC",
             '{"min_rows": 2, "required_columns": ["office_location", "avg_rating"]}',
             "employees", "aggregation,distribution", "medium"),

            # product_inventory
            ("Which products are below reorder level?",
             "SELECT product_name, stock_quantity, reorder_level FROM product_inventory WHERE stock_quantity < reorder_level",
             '{"min_rows": 1, "required_columns": ["product_name", "stock_quantity", "reorder_level"]}',
             "product_inventory", "filter,lookup", "easy"),
            ("Show average product rating by category",
             "SELECT category, ROUND(AVG(rating), 2) as avg_rating FROM product_inventory GROUP BY category ORDER BY avg_rating DESC",
             '{"min_rows": 2, "required_columns": ["category", "avg_rating"]}',
             "product_inventory", "aggregation,distribution", "easy"),
            ("What is the total inventory value?",
             "SELECT SUM(unit_price * stock_quantity) as total_value FROM product_inventory",
             '{"min_rows": 1, "max_rows": 1}',
             "product_inventory", "aggregation", "easy"),
            ("Which brand has the most products?",
             "SELECT brand, COUNT(*) as product_count FROM product_inventory GROUP BY brand ORDER BY product_count DESC LIMIT 1",
             '{"min_rows": 1, "max_rows": 1, "required_columns": ["brand"]}',
             "product_inventory", "ranking,aggregation", "medium"),

            # Cross-dataset / harder
            ("Compare average salary across departments for active employees only",
             "SELECT department, ROUND(AVG(salary), 2) as avg_salary, COUNT(*) as employee_count FROM employees WHERE employment_status = 'Active' GROUP BY department ORDER BY avg_salary DESC",
             '{"min_rows": 2, "required_columns": ["department", "avg_salary"]}',
             "employees", "comparison,filter", "hard"),
            ("Show top 5 customers by total spending",
             "SELECT customer_name, SUM(total_amount) as total_spent FROM sales_orders GROUP BY customer_name ORDER BY total_spent DESC LIMIT 5",
             '{"min_rows": 5, "max_rows": 5, "required_columns": ["customer_name"]}',
             "sales_orders", "ranking,aggregation", "medium"),
        ]

        conn.executemany(
            "INSERT OR IGNORE INTO benchmark_cases (question, expected_sql, expected_result_pattern, dataset_name, tags, difficulty) VALUES (?, ?, ?, ?, ?, ?)",
            cases,
        )


# ---------------------------------------------------------------------------
# Feedback CRUD
# ---------------------------------------------------------------------------

def submit_feedback(query_id: str, question: str, vote: str,
                    sql_query: str | None = None,
                    session_id: str | None = None,
                    comment: str | None = None) -> dict:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO query_feedback
               (query_id, session_id, question, sql_query, vote, comment)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (query_id, session_id, question, sql_query, vote, comment),
        )
    return {"status": "ok"}


def get_feedback_stats() -> dict:
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN vote = 'up' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote = 'down' THEN 1 ELSE 0 END) as downvotes
            FROM query_feedback
        """)
        row = dict(cursor.fetchone())
        total = row["total"] or 0
        upvotes = row["upvotes"] or 0
        row["accuracy_pct"] = round(upvotes * 100.0 / total, 1) if total > 0 else 0.0

        # Recent feedback
        recent = conn.execute(
            "SELECT * FROM query_feedback ORDER BY created_at DESC LIMIT 20"
        )
        row["recent"] = [dict(r) for r in recent.fetchall()]

        # Per-intent accuracy (if we have intent data in the question patterns)
        return row


def get_all_feedback(limit: int = 100) -> list[dict]:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM query_feedback ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Benchmark CRUD
# ---------------------------------------------------------------------------

def get_benchmark_cases(dataset_name: str | None = None,
                        difficulty: str | None = None) -> list[dict]:
    with get_db() as conn:
        query = "SELECT * FROM benchmark_cases WHERE 1=1"
        params: list[str] = []
        if dataset_name:
            query += " AND dataset_name = ?"
            params.append(dataset_name)
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        query += " ORDER BY id"
        cursor = conn.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def upsert_benchmark_case(question: str, expected_sql: str,
                          expected_result_pattern: str | None = None,
                          dataset_name: str | None = None,
                          tags: str | None = None,
                          difficulty: str = "medium") -> dict:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO benchmark_cases
               (question, expected_sql, expected_result_pattern, dataset_name, tags, difficulty)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (question, expected_sql, expected_result_pattern, dataset_name, tags, difficulty),
        )
    return {"status": "ok"}


def delete_benchmark_case(question: str) -> dict:
    with get_db() as conn:
        conn.execute("DELETE FROM benchmark_cases WHERE question = ?", (question,))
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------

def run_benchmark(dataset_name: str | None = None,
                  difficulty: str | None = None) -> dict:
    """
    Run all benchmark cases and compare results.

    For each case:
    1. Execute the expected SQL to get ground truth
    2. Run the question through the compound AI pipeline
    3. Compare results (row count, columns, values)
    """
    from app.compound_ai import run_compound_pipeline

    cases = get_benchmark_cases(dataset_name, difficulty)
    if not cases:
        return {"error": "No benchmark cases found", "total": 0, "passed": 0,
                "failed": 0, "accuracy_pct": 0.0, "details": []}

    start = time.time()
    details = []
    passed = 0
    failed = 0

    for case in cases:
        case_result = _run_single_benchmark(case)
        details.append(case_result)
        if case_result["passed"]:
            passed += 1
        else:
            failed += 1

    total = len(cases)
    accuracy = round(passed * 100.0 / total, 1) if total > 0 else 0.0
    duration_ms = (time.time() - start) * 1000

    # Save run results
    with get_db() as conn:
        conn.execute(
            """INSERT INTO benchmark_runs
               (total_cases, passed, failed, accuracy_pct, duration_ms, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (total, passed, failed, accuracy, round(duration_ms, 1),
             json.dumps(details)),
        )

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "accuracy_pct": accuracy,
        "duration_ms": round(duration_ms, 1),
        "details": details,
    }


def _run_single_benchmark(case: dict) -> dict:
    """Run a single benchmark case and return pass/fail with details."""
    question = case["question"]
    expected_sql = case["expected_sql"]
    pattern_str = case.get("expected_result_pattern")

    result = {
        "question": question,
        "dataset": case.get("dataset_name"),
        "difficulty": case.get("difficulty"),
        "tags": case.get("tags"),
        "passed": False,
        "checks": [],
    }

    # Step 1: Get ground truth from expected SQL
    try:
        ground_truth = execute_query(expected_sql)
        if ground_truth["error"]:
            result["checks"].append({
                "check": "expected_sql_execution",
                "passed": False,
                "detail": f"Expected SQL failed: {ground_truth['error']}",
            })
            return result
        result["expected_row_count"] = ground_truth["row_count"]
        result["expected_columns"] = ground_truth["columns"]
    except Exception as e:
        result["checks"].append({
            "check": "expected_sql_execution",
            "passed": False,
            "detail": f"Expected SQL error: {str(e)}",
        })
        return result

    # Step 2: Run through pipeline
    try:
        pipeline_result = run_compound_pipeline(question)
        result["generated_sql"] = pipeline_result.get("sql_query", "")
        result["pipeline_row_count"] = pipeline_result.get("row_count", 0)
        result["pipeline_columns"] = pipeline_result.get("columns", [])
        result["pipeline_error"] = pipeline_result.get("error")
        result["is_trusted"] = pipeline_result.get("is_trusted", False)
    except Exception as e:
        result["checks"].append({
            "check": "pipeline_execution",
            "passed": False,
            "detail": f"Pipeline error: {str(e)}",
        })
        return result

    if pipeline_result.get("error"):
        result["checks"].append({
            "check": "pipeline_no_error",
            "passed": False,
            "detail": f"Pipeline returned error: {pipeline_result['error']}",
        })
        return result

    # Step 3: Compare results
    all_passed = True

    # Check: SQL was generated
    if not pipeline_result.get("sql_query"):
        result["checks"].append({
            "check": "sql_generated",
            "passed": False,
            "detail": "No SQL was generated",
        })
        return result
    result["checks"].append({
        "check": "sql_generated",
        "passed": True,
        "detail": "SQL was generated",
    })

    # Check: Row count comparison
    expected_rows = ground_truth["row_count"]
    actual_rows = pipeline_result["row_count"]

    if pattern_str:
        try:
            pattern = json.loads(pattern_str)
            min_rows = pattern.get("min_rows", 0)
            max_rows = pattern.get("max_rows", float("inf"))
            row_check = min_rows <= actual_rows <= max_rows
            result["checks"].append({
                "check": "row_count_in_range",
                "passed": row_check,
                "detail": f"Expected {min_rows}-{max_rows} rows, got {actual_rows}",
            })
            if not row_check:
                all_passed = False

            # Check required columns
            required_cols = pattern.get("required_columns", [])
            if required_cols:
                actual_cols = [c.lower() for c in pipeline_result.get("columns", [])]
                missing = [c for c in required_cols if c.lower() not in actual_cols]
                col_check = len(missing) == 0
                result["checks"].append({
                    "check": "required_columns",
                    "passed": col_check,
                    "detail": f"Missing columns: {missing}" if missing else "All required columns present",
                })
                if not col_check:
                    all_passed = False
        except json.JSONDecodeError:
            pass
    else:
        # Simple row count comparison (within 50% tolerance)
        if expected_rows == 0:
            row_check = actual_rows == 0
        else:
            ratio = actual_rows / expected_rows
            row_check = 0.5 <= ratio <= 2.0
        result["checks"].append({
            "check": "row_count_similar",
            "passed": row_check,
            "detail": f"Expected ~{expected_rows} rows, got {actual_rows}",
        })
        if not row_check:
            all_passed = False

    result["passed"] = all_passed
    return result


def get_benchmark_history(limit: int = 20) -> list[dict]:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, run_at, total_cases, passed, failed, accuracy_pct, duration_ms FROM benchmark_runs ORDER BY run_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]


def get_benchmark_run_detail(run_id: int) -> dict | None:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM benchmark_runs WHERE id = ?", (run_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["details"] = json.loads(result["details"])
        return result
