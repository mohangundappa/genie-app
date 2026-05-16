"""
Semantic Layer — the bridge between raw data and business meaning.

Inspired by Databricks Genie's knowledge store, this module provides:
1. Column descriptions — human-readable descriptions for every column
2. Business glossary — maps business terms/synonyms to technical column names
3. Metrics (measures) — pre-defined SQL calculations (e.g., "total revenue" = SUM(total_amount))
4. Dimensions — columns used for grouping/slicing
5. Filters — pre-defined filter expressions (e.g., "active employees" = employment_status = 'Active')
6. Join relationships — how tables relate to each other
7. Trusted queries (SQL examples) — curated queries for common questions
"""

import json
from app.database import get_db


# ---------------------------------------------------------------------------
# Schema: create semantic layer tables
# ---------------------------------------------------------------------------

def init_semantic_layer():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_column_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                description TEXT NOT NULL,
                business_name TEXT,
                data_format TEXT,
                UNIQUE(table_name, column_name)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                definition TEXT NOT NULL,
                mapped_table TEXT,
                mapped_column TEXT,
                synonyms TEXT,
                UNIQUE(term)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                table_name TEXT NOT NULL,
                expression TEXT NOT NULL,
                format_type TEXT DEFAULT 'number',
                UNIQUE(name, table_name)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_dimensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                description TEXT,
                UNIQUE(name, table_name)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                table_name TEXT NOT NULL,
                expression TEXT NOT NULL,
                description TEXT,
                UNIQUE(name, table_name)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_joins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                left_table TEXT NOT NULL,
                right_table TEXT NOT NULL,
                join_type TEXT DEFAULT 'INNER',
                on_clause TEXT NOT NULL,
                description TEXT,
                UNIQUE(left_table, right_table)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_trusted_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                sql_query TEXT NOT NULL,
                description TEXT,
                table_name TEXT,
                is_parameterized INTEGER DEFAULT 0,
                UNIQUE(question)
            )
        """)
    _seed_default_semantic_data()


# ---------------------------------------------------------------------------
# Seed: populate with default semantic metadata for our 4 datasets
# ---------------------------------------------------------------------------

def _seed_default_semantic_data():
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM semantic_column_descriptions")
        if cursor.fetchone()["cnt"] > 0:
            return

        # ---- Column descriptions ----
        column_descriptions = [
            # world_countries
            ("world_countries", "id", "Unique identifier for each country record", "Country ID", None),
            ("world_countries", "country", "Official name of the country", "Country Name", None),
            ("world_countries", "continent", "Continent where the country is located", "Continent", None),
            ("world_countries", "population", "Total population count of the country", "Population", "integer"),
            ("world_countries", "area_sq_km", "Total land area in square kilometers", "Land Area (sq km)", "decimal"),
            ("world_countries", "gdp_usd_billion", "Gross Domestic Product in billions of US dollars", "GDP (USD Billions)", "currency"),
            ("world_countries", "life_expectancy", "Average life expectancy in years at birth", "Life Expectancy (years)", "decimal"),
            ("world_countries", "literacy_rate", "Percentage of population aged 15+ who can read and write", "Literacy Rate (%)", "percentage"),
            ("world_countries", "capital", "Capital city of the country", "Capital City", None),
            ("world_countries", "currency", "Official currency code", "Currency Code", None),
            # sales_orders
            ("sales_orders", "id", "Unique order identifier", "Order ID", None),
            ("sales_orders", "order_date", "Date when the order was placed (YYYY-MM-DD format)", "Order Date", "date"),
            ("sales_orders", "customer_name", "Name of the business/customer who placed the order", "Customer", None),
            ("sales_orders", "customer_segment", "Business segment classification of the customer", "Customer Segment", None),
            ("sales_orders", "region", "Geographic sales region (East, West, Central, South)", "Sales Region", None),
            ("sales_orders", "city", "City where the order was shipped to", "City", None),
            ("sales_orders", "product_category", "High-level product category (Electronics, Office Supplies, Furniture, Software)", "Product Category", None),
            ("sales_orders", "product_name", "Specific product name", "Product Name", None),
            ("sales_orders", "quantity", "Number of units ordered", "Quantity", "integer"),
            ("sales_orders", "unit_price", "Price per unit in USD", "Unit Price (USD)", "currency"),
            ("sales_orders", "discount", "Discount percentage applied to the order", "Discount (%)", "percentage"),
            ("sales_orders", "total_amount", "Total order value after discount in USD", "Total Revenue (USD)", "currency"),
            ("sales_orders", "profit", "Net profit from the order in USD", "Profit (USD)", "currency"),
            ("sales_orders", "shipping_cost", "Cost of shipping in USD", "Shipping Cost (USD)", "currency"),
            ("sales_orders", "order_status", "Current order status (Delivered, Shipped, Processing, Cancelled)", "Order Status", None),
            # employees
            ("employees", "id", "Unique employee identifier", "Employee ID", None),
            ("employees", "first_name", "Employee's first name", "First Name", None),
            ("employees", "last_name", "Employee's last name", "Last Name", None),
            ("employees", "email", "Employee's work email address", "Email", None),
            ("employees", "department", "Department the employee belongs to", "Department", None),
            ("employees", "job_title", "Employee's job title/position", "Job Title", None),
            ("employees", "salary", "Annual base salary in USD", "Salary (USD)", "currency"),
            ("employees", "hire_date", "Date the employee was hired (YYYY-MM-DD format)", "Hire Date", "date"),
            ("employees", "office_location", "Office/city where the employee works", "Office Location", None),
            ("employees", "employment_status", "Current employment status (Active, On Leave, Terminated)", "Employment Status", None),
            ("employees", "performance_rating", "Annual performance rating on a scale of 1.0 to 5.0", "Performance Rating", "decimal"),
            ("employees", "bonus_pct", "Bonus percentage based on performance", "Bonus (%)", "percentage"),
            # product_inventory
            ("product_inventory", "id", "Unique product identifier", "Product ID", None),
            ("product_inventory", "product_name", "Name of the product", "Product Name", None),
            ("product_inventory", "sku", "Stock Keeping Unit — unique inventory tracking code", "SKU", None),
            ("product_inventory", "category", "Product category classification", "Category", None),
            ("product_inventory", "brand", "Brand/manufacturer name", "Brand", None),
            ("product_inventory", "unit_price", "Selling price per unit in USD", "Selling Price (USD)", "currency"),
            ("product_inventory", "cost_price", "Wholesale/cost price per unit in USD", "Cost Price (USD)", "currency"),
            ("product_inventory", "stock_quantity", "Current stock quantity in warehouse", "Stock Quantity", "integer"),
            ("product_inventory", "reorder_level", "Minimum stock level that triggers reorder", "Reorder Level", "integer"),
            ("product_inventory", "supplier", "Name of the product supplier", "Supplier", None),
            ("product_inventory", "warehouse_location", "Warehouse where the product is stored", "Warehouse", None),
            ("product_inventory", "rating", "Average customer rating on a scale of 1.0 to 5.0", "Customer Rating", "decimal"),
            ("product_inventory", "reviews_count", "Total number of customer reviews", "Review Count", "integer"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_column_descriptions (table_name, column_name, description, business_name, data_format) VALUES (?, ?, ?, ?, ?)",
            column_descriptions,
        )

        # ---- Business Glossary ----
        glossary_entries = [
            ("Revenue", "Total sales amount from orders after discounts", "sales_orders", "total_amount", "sales,income,turnover,top line"),
            ("Profit", "Net profit after deducting costs from revenue", "sales_orders", "profit", "earnings,margin,net income,bottom line"),
            ("GDP", "Gross Domestic Product — total economic output of a country in billions USD", "world_countries", "gdp_usd_billion", "gross domestic product,economic output,national income"),
            ("Headcount", "Total number of employees", "employees", None, "employee count,staff count,workforce size,FTE"),
            ("Salary", "Annual base compensation in USD", "employees", "salary", "compensation,pay,wage,base pay"),
            ("Performance Rating", "Annual employee performance score from 1.0 (low) to 5.0 (high)", "employees", "performance_rating", "rating,review score,evaluation"),
            ("AOV", "Average Order Value — mean total_amount per order", "sales_orders", "total_amount", "average order value,avg order,basket size"),
            ("Stock Level", "Current quantity of product available in warehouse", "product_inventory", "stock_quantity", "inventory level,on hand,available stock,quantity on hand"),
            ("Reorder Point", "Minimum stock quantity that triggers a replenishment order", "product_inventory", "reorder_level", "reorder level,min stock,safety stock"),
            ("Churn", "Employees with status 'Terminated'", "employees", "employment_status", "attrition,turnover,terminated"),
            ("Customer Segment", "Classification of customers by business type (Consumer, Corporate, Small Business, Home Office)", "sales_orders", "customer_segment", "segment,customer type,buyer type"),
            ("Discount Rate", "Percentage discount applied to an order (0 to 0.3)", "sales_orders", "discount", "discount percentage,markdown,price reduction"),
            ("Life Expectancy", "Average number of years a person is expected to live at birth", "world_countries", "life_expectancy", "lifespan,longevity,average age"),
            ("Literacy", "Percentage of adults who can read and write", "world_countries", "literacy_rate", "literacy rate,education rate,reading rate"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_glossary (term, definition, mapped_table, mapped_column, synonyms) VALUES (?, ?, ?, ?, ?)",
            glossary_entries,
        )

        # ---- Metrics (Measures) ----
        metrics = [
            ("Total Revenue", "Sum of all order amounts", "sales_orders", "SUM(total_amount)", "currency"),
            ("Total Profit", "Sum of all order profits", "sales_orders", "SUM(profit)", "currency"),
            ("Order Count", "Total number of orders", "sales_orders", "COUNT(*)", "integer"),
            ("Average Order Value", "Mean order amount across all orders", "sales_orders", "ROUND(AVG(total_amount), 2)", "currency"),
            ("Profit Margin", "Profit as a percentage of revenue", "sales_orders", "ROUND(SUM(profit) * 100.0 / SUM(total_amount), 2)", "percentage"),
            ("Average Salary", "Mean annual salary across employees", "employees", "ROUND(AVG(salary), 2)", "currency"),
            ("Total Headcount", "Count of all employees", "employees", "COUNT(*)", "integer"),
            ("Active Headcount", "Count of active (non-terminated) employees", "employees", "COUNT(CASE WHEN employment_status = 'Active' THEN 1 END)", "integer"),
            ("Average Rating", "Mean performance rating across employees", "employees", "ROUND(AVG(performance_rating), 2)", "decimal"),
            ("Total Population", "Sum of population across countries", "world_countries", "SUM(population)", "integer"),
            ("Average GDP", "Mean GDP across countries", "world_countries", "ROUND(AVG(gdp_usd_billion), 2)", "currency"),
            ("Average Life Expectancy", "Mean life expectancy across countries", "world_countries", "ROUND(AVG(life_expectancy), 1)", "decimal"),
            ("Total Stock Value", "Total value of inventory at selling price", "product_inventory", "SUM(unit_price * stock_quantity)", "currency"),
            ("Total Stock Cost", "Total cost value of inventory", "product_inventory", "SUM(cost_price * stock_quantity)", "currency"),
            ("Items Below Reorder", "Count of products below their reorder level", "product_inventory", "COUNT(CASE WHEN stock_quantity < reorder_level THEN 1 END)", "integer"),
            ("Average Customer Rating", "Mean product rating across all products", "product_inventory", "ROUND(AVG(rating), 2)", "decimal"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_metrics (name, description, table_name, expression, format_type) VALUES (?, ?, ?, ?, ?)",
            metrics,
        )

        # ---- Dimensions ----
        dimensions = [
            ("Continent", "world_countries", "continent", "Geographic continent grouping"),
            ("Country", "world_countries", "country", "Individual country"),
            ("Currency", "world_countries", "currency", "Currency code used by the country"),
            ("Product Category", "sales_orders", "product_category", "High-level product grouping"),
            ("Customer Segment", "sales_orders", "customer_segment", "Business type of the customer"),
            ("Sales Region", "sales_orders", "region", "Geographic sales territory"),
            ("City", "sales_orders", "city", "Shipping destination city"),
            ("Order Status", "sales_orders", "order_status", "Current fulfillment status"),
            ("Order Year", "sales_orders", "substr(order_date,1,4)", "Year extracted from order date"),
            ("Order Month", "sales_orders", "substr(order_date,1,7)", "Year-month extracted from order date"),
            ("Department", "employees", "department", "Organizational department"),
            ("Office Location", "employees", "office_location", "Work location/city"),
            ("Job Title", "employees", "job_title", "Employee role/position"),
            ("Employment Status", "employees", "employment_status", "Active, On Leave, or Terminated"),
            ("Product Category (Inventory)", "product_inventory", "category", "Inventory product grouping"),
            ("Brand", "product_inventory", "brand", "Product manufacturer/brand"),
            ("Supplier", "product_inventory", "supplier", "Product supplier"),
            ("Warehouse", "product_inventory", "warehouse_location", "Storage warehouse location"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_dimensions (name, table_name, column_name, description) VALUES (?, ?, ?, ?)",
            dimensions,
        )

        # ---- Filters ----
        filters = [
            ("Active Employees", "employees", "employment_status = 'Active'", "Only currently active employees"),
            ("Terminated Employees", "employees", "employment_status = 'Terminated'", "Only terminated employees"),
            ("High Performers", "employees", "performance_rating >= 4.0", "Employees with rating 4.0 or above"),
            ("Low Performers", "employees", "performance_rating < 3.0", "Employees with rating below 3.0"),
            ("Delivered Orders", "sales_orders", "order_status = 'Delivered'", "Only delivered/completed orders"),
            ("Cancelled Orders", "sales_orders", "order_status = 'Cancelled'", "Only cancelled orders"),
            ("High Value Orders", "sales_orders", "total_amount > 500", "Orders over $500"),
            ("Discounted Orders", "sales_orders", "discount > 0", "Orders that received a discount"),
            ("Profitable Orders", "sales_orders", "profit > 0", "Orders with positive profit"),
            ("Loss-Making Orders", "sales_orders", "profit < 0", "Orders with negative profit (losses)"),
            ("Low Stock", "product_inventory", "stock_quantity < reorder_level", "Products below reorder level"),
            ("Out of Stock", "product_inventory", "stock_quantity = 0", "Products with zero stock"),
            ("Top Rated Products", "product_inventory", "rating >= 4.5", "Products rated 4.5 or above"),
            ("Asian Countries", "world_countries", "continent = 'Asia'", "Countries in Asia"),
            ("European Countries", "world_countries", "continent = 'Europe'", "Countries in Europe"),
            ("African Countries", "world_countries", "continent = 'Africa'", "Countries in Africa"),
            ("Large Countries", "world_countries", "population > 100000000", "Countries with over 100M population"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_filters (name, table_name, expression, description) VALUES (?, ?, ?, ?)",
            filters,
        )

        # ---- Join Relationships ----
        joins = [
            ("sales_orders", "product_inventory", "LEFT", "sales_orders.product_name = product_inventory.product_name", "Join sales orders with product inventory to get stock and pricing details"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_joins (left_table, right_table, join_type, on_clause, description) VALUES (?, ?, ?, ?, ?)",
            joins,
        )

        # ---- Trusted Queries (SQL Examples) ----
        trusted_queries = [
            ("What are the top 10 countries by GDP?",
             "SELECT country, gdp_usd_billion FROM world_countries ORDER BY gdp_usd_billion DESC LIMIT 10",
             "Top 10 countries ranked by GDP in billions USD", "world_countries", 0),
            ("Show total revenue by product category",
             "SELECT product_category, ROUND(SUM(total_amount), 2) as total_revenue FROM sales_orders GROUP BY product_category ORDER BY total_revenue DESC",
             "Revenue breakdown by product category", "sales_orders", 0),
            ("What is the average salary by department?",
             "SELECT department, ROUND(AVG(salary), 2) as avg_salary FROM employees GROUP BY department ORDER BY avg_salary DESC",
             "Average salary across departments", "employees", 0),
            ("Which products are below reorder level?",
             "SELECT product_name, stock_quantity, reorder_level, (reorder_level - stock_quantity) as deficit FROM product_inventory WHERE stock_quantity < reorder_level ORDER BY deficit DESC",
             "Products needing restocking", "product_inventory", 0),
            ("Show monthly revenue trend",
             "SELECT substr(order_date,1,7) as month, ROUND(SUM(total_amount), 2) as revenue FROM sales_orders GROUP BY month ORDER BY month",
             "Revenue over time by month", "sales_orders", 0),
            ("What is the profit margin by region?",
             "SELECT region, ROUND(SUM(profit) * 100.0 / SUM(total_amount), 2) as profit_margin_pct FROM sales_orders GROUP BY region ORDER BY profit_margin_pct DESC",
             "Profit margin percentage by sales region", "sales_orders", 0),
            ("Show employee count by department and status",
             "SELECT department, employment_status, COUNT(*) as count FROM employees GROUP BY department, employment_status ORDER BY department, count DESC",
             "Headcount by department broken down by employment status", "employees", 0),
            ("What is the average life expectancy by continent?",
             "SELECT continent, ROUND(AVG(life_expectancy), 1) as avg_life_expectancy FROM world_countries GROUP BY continent ORDER BY avg_life_expectancy DESC",
             "Life expectancy comparison across continents", "world_countries", 0),
            ("Show total stock value by warehouse",
             "SELECT warehouse_location, ROUND(SUM(unit_price * stock_quantity), 2) as total_value FROM product_inventory GROUP BY warehouse_location ORDER BY total_value DESC",
             "Inventory value by warehouse location", "product_inventory", 0),
            ("Who are the highest paid employees?",
             "SELECT first_name || ' ' || last_name as employee, department, salary FROM employees ORDER BY salary DESC LIMIT 10",
             "Top 10 employees by salary", "employees", 0),
            ("Show order distribution by customer segment",
             "SELECT customer_segment, COUNT(*) as order_count, ROUND(SUM(total_amount), 2) as total_revenue, ROUND(AVG(total_amount), 2) as avg_order_value FROM sales_orders GROUP BY customer_segment ORDER BY total_revenue DESC",
             "Order volume and revenue by customer segment", "sales_orders", 0),
            ("Compare GDP per capita across continents",
             "SELECT continent, ROUND(SUM(gdp_usd_billion * 1000000000.0) / SUM(population), 2) as gdp_per_capita FROM world_countries GROUP BY continent ORDER BY gdp_per_capita DESC",
             "GDP per capita by continent", "world_countries", 0),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semantic_trusted_queries (question, sql_query, description, table_name, is_parameterized) VALUES (?, ?, ?, ?, ?)",
            trusted_queries,
        )


# ---------------------------------------------------------------------------
# Read: retrieve semantic layer data for various purposes
# ---------------------------------------------------------------------------

def get_semantic_context_for_prompt(table_name: str | None = None) -> str:
    """Build a rich semantic context string to include in the LLM system prompt."""
    parts = []

    with get_db() as conn:
        # Column descriptions
        if table_name:
            cols = conn.execute(
                "SELECT * FROM semantic_column_descriptions WHERE table_name = ? ORDER BY table_name, column_name",
                (table_name,),
            ).fetchall()
        else:
            cols = conn.execute(
                "SELECT * FROM semantic_column_descriptions ORDER BY table_name, column_name"
            ).fetchall()

        if cols:
            parts.append("## Column Descriptions")
            current_table = None
            for col in cols:
                if col["table_name"] != current_table:
                    current_table = col["table_name"]
                    parts.append(f"\n### Table: {current_table}")
                biz_name = f" (business name: \"{col['business_name']}\")" if col["business_name"] else ""
                fmt = f" [format: {col['data_format']}]" if col["data_format"] else ""
                parts.append(f"- {col['column_name']}: {col['description']}{biz_name}{fmt}")

        # Business glossary
        if table_name:
            glossary = conn.execute(
                "SELECT * FROM semantic_glossary WHERE mapped_table = ? ORDER BY term",
                (table_name,),
            ).fetchall()
        else:
            glossary = conn.execute("SELECT * FROM semantic_glossary ORDER BY term").fetchall()

        if glossary:
            parts.append("\n## Business Glossary")
            for g in glossary:
                synonyms = f" (also known as: {g['synonyms']})" if g["synonyms"] else ""
                mapping = ""
                if g["mapped_table"] and g["mapped_column"]:
                    mapping = f" → {g['mapped_table']}.{g['mapped_column']}"
                elif g["mapped_table"]:
                    mapping = f" → {g['mapped_table']}"
                parts.append(f"- **{g['term']}**: {g['definition']}{mapping}{synonyms}")

        # Metrics
        if table_name:
            metrics = conn.execute(
                "SELECT * FROM semantic_metrics WHERE table_name = ? ORDER BY name",
                (table_name,),
            ).fetchall()
        else:
            metrics = conn.execute("SELECT * FROM semantic_metrics ORDER BY table_name, name").fetchall()

        if metrics:
            parts.append("\n## Pre-defined Metrics (use these exact expressions when asked)")
            for m in metrics:
                parts.append(f"- **{m['name']}** ({m['table_name']}): `{m['expression']}` — {m['description']}")

        # Dimensions
        if table_name:
            dims = conn.execute(
                "SELECT * FROM semantic_dimensions WHERE table_name = ? ORDER BY name",
                (table_name,),
            ).fetchall()
        else:
            dims = conn.execute("SELECT * FROM semantic_dimensions ORDER BY table_name, name").fetchall()

        if dims:
            parts.append("\n## Dimensions (common GROUP BY columns)")
            for d in dims:
                parts.append(f"- **{d['name']}** ({d['table_name']}): `{d['column_name']}` — {d['description'] or ''}")

        # Filters
        if table_name:
            filters = conn.execute(
                "SELECT * FROM semantic_filters WHERE table_name = ? ORDER BY name",
                (table_name,),
            ).fetchall()
        else:
            filters = conn.execute("SELECT * FROM semantic_filters ORDER BY table_name, name").fetchall()

        if filters:
            parts.append("\n## Pre-defined Filters (use when user mentions these concepts)")
            for f in filters:
                parts.append(f"- **{f['name']}** ({f['table_name']}): `{f['expression']}` — {f['description'] or ''}")

        # Join relationships
        joins = conn.execute("SELECT * FROM semantic_joins ORDER BY left_table").fetchall()
        if joins:
            parts.append("\n## Join Relationships")
            for j in joins:
                parts.append(f"- {j['left_table']} {j['join_type']} JOIN {j['right_table']} ON {j['on_clause']} — {j['description'] or ''}")

        # Trusted queries
        if table_name:
            queries = conn.execute(
                "SELECT * FROM semantic_trusted_queries WHERE table_name = ? ORDER BY question",
                (table_name,),
            ).fetchall()
        else:
            queries = conn.execute("SELECT * FROM semantic_trusted_queries ORDER BY question").fetchall()

        if queries:
            parts.append("\n## Trusted SQL Examples (prefer these patterns for matching questions)")
            for q in queries:
                parts.append(f"- Q: \"{q['question']}\"")
                parts.append(f"  SQL: `{q['sql_query']}`")

    return "\n".join(parts)


def get_column_descriptions(table_name: str | None = None) -> list[dict]:
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_column_descriptions WHERE table_name = ? ORDER BY column_name",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM semantic_column_descriptions ORDER BY table_name, column_name"
            ).fetchall()
        return [dict(r) for r in rows]


def get_glossary() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM semantic_glossary ORDER BY term").fetchall()
        return [dict(r) for r in rows]


def get_metrics(table_name: str | None = None) -> list[dict]:
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_metrics WHERE table_name = ? ORDER BY name",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM semantic_metrics ORDER BY table_name, name").fetchall()
        return [dict(r) for r in rows]


def get_dimensions(table_name: str | None = None) -> list[dict]:
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_dimensions WHERE table_name = ? ORDER BY name",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM semantic_dimensions ORDER BY table_name, name").fetchall()
        return [dict(r) for r in rows]


def get_filters(table_name: str | None = None) -> list[dict]:
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_filters WHERE table_name = ? ORDER BY name",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM semantic_filters ORDER BY table_name, name").fetchall()
        return [dict(r) for r in rows]


def get_joins() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM semantic_joins ORDER BY left_table").fetchall()
        return [dict(r) for r in rows]


def get_trusted_queries(table_name: str | None = None) -> list[dict]:
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_trusted_queries WHERE table_name = ? ORDER BY question",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM semantic_trusted_queries ORDER BY question").fetchall()
        return [dict(r) for r in rows]


def find_trusted_query(question: str) -> dict | None:
    """Try to find a trusted query that closely matches the user's question."""
    with get_db() as conn:
        q_lower = question.lower().strip().rstrip("?").strip()
        rows = conn.execute("SELECT * FROM semantic_trusted_queries").fetchall()
        for row in rows:
            stored_q = row["question"].lower().strip().rstrip("?").strip()
            if q_lower == stored_q or q_lower in stored_q or stored_q in q_lower:
                return dict(row)
        return None


# ---------------------------------------------------------------------------
# Write: CRUD operations for semantic layer management
# ---------------------------------------------------------------------------

def upsert_column_description(table_name: str, column_name: str, description: str,
                               business_name: str | None = None, data_format: str | None = None):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO semantic_column_descriptions
               (table_name, column_name, description, business_name, data_format)
               VALUES (?, ?, ?, ?, ?)""",
            (table_name, column_name, description, business_name, data_format),
        )


def upsert_glossary_entry(term: str, definition: str, mapped_table: str | None = None,
                           mapped_column: str | None = None, synonyms: str | None = None):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO semantic_glossary
               (term, definition, mapped_table, mapped_column, synonyms)
               VALUES (?, ?, ?, ?, ?)""",
            (term, definition, mapped_table, mapped_column, synonyms),
        )


def upsert_metric(name: str, description: str, table_name: str, expression: str, format_type: str = "number"):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO semantic_metrics
               (name, description, table_name, expression, format_type)
               VALUES (?, ?, ?, ?, ?)""",
            (name, description, table_name, expression, format_type),
        )


def upsert_trusted_query(question: str, sql_query: str, description: str | None = None,
                          table_name: str | None = None, is_parameterized: int = 0):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO semantic_trusted_queries
               (question, sql_query, description, table_name, is_parameterized)
               VALUES (?, ?, ?, ?, ?)""",
            (question, sql_query, description, table_name, is_parameterized),
        )


def delete_glossary_entry(term: str):
    with get_db() as conn:
        conn.execute("DELETE FROM semantic_glossary WHERE term = ?", (term,))


def delete_metric(name: str, table_name: str):
    with get_db() as conn:
        conn.execute("DELETE FROM semantic_metrics WHERE name = ? AND table_name = ?", (name, table_name))


def delete_trusted_query(question: str):
    with get_db() as conn:
        conn.execute("DELETE FROM semantic_trusted_queries WHERE question = ?", (question,))


def get_full_semantic_summary() -> dict:
    """Return a complete summary of the semantic layer for the API."""
    return {
        "column_descriptions": get_column_descriptions(),
        "glossary": get_glossary(),
        "metrics": get_metrics(),
        "dimensions": get_dimensions(),
        "filters": get_filters(),
        "joins": get_joins(),
        "trusted_queries": get_trusted_queries(),
    }
