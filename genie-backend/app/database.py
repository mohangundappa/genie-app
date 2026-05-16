import sqlite3
import os
import json
from contextlib import contextmanager

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "genie.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                sql_query TEXT NOT NULL,
                result_summary TEXT,
                chart_config TEXT,
                dataset_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
    load_sample_datasets()


def get_all_tables() -> list[dict]:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('query_history', 'settings')"
        )
        tables = []
        for row in cursor.fetchall():
            table_name = row["name"]
            col_cursor = conn.execute(f"PRAGMA table_info('{table_name}')")
            columns = [
                {"name": col["name"], "type": col["type"], "nullable": not col["notnull"]}
                for col in col_cursor.fetchall()
            ]
            count_cursor = conn.execute(f"SELECT COUNT(*) as cnt FROM '{table_name}'")
            row_count = count_cursor.fetchone()["cnt"]
            tables.append({
                "name": table_name,
                "columns": columns,
                "row_count": row_count,
            })
        return tables


def get_table_sample(table_name: str, limit: int = 10) -> list[dict]:
    with get_db() as conn:
        cursor = conn.execute(f"SELECT * FROM '{table_name}' LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


def execute_query(sql: str) -> dict:
    with get_db() as conn:
        try:
            cursor = conn.execute(sql)
            if sql.strip().upper().startswith("SELECT") or sql.strip().upper().startswith("WITH"):
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return {"columns": columns, "rows": rows, "row_count": len(rows), "error": None}
            else:
                return {"columns": [], "rows": [], "row_count": 0, "error": "Only SELECT queries are allowed."}
        except Exception as e:
            return {"columns": [], "rows": [], "row_count": 0, "error": str(e)}


def save_query_history(question: str, sql_query: str, result_summary: str, chart_config: str | None, dataset_name: str | None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO query_history (question, sql_query, result_summary, chart_config, dataset_name) VALUES (?, ?, ?, ?, ?)",
            (question, sql_query, result_summary, chart_config, dataset_name),
        )


def get_query_history(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM query_history ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_setting(key: str) -> str | None:
    with get_db() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def get_schema_for_prompt() -> str:
    tables = get_all_tables()
    schema_parts = []
    for table in tables:
        cols = ", ".join([f"{c['name']} ({c['type']})" for c in table["columns"]])
        schema_parts.append(f"Table: {table['name']} ({table['row_count']} rows)\n  Columns: {cols}")
    return "\n\n".join(schema_parts)


def load_sample_datasets():
    with get_db() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='world_countries'")
        if cursor.fetchone():
            return

        # Dataset 1: World Countries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS world_countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country TEXT NOT NULL,
                continent TEXT NOT NULL,
                population BIGINT,
                area_sq_km REAL,
                gdp_usd_billion REAL,
                life_expectancy REAL,
                literacy_rate REAL,
                capital TEXT,
                currency TEXT
            )
        """)
        countries_data = [
            ("United States", "North America", 331002651, 9833520, 25462.7, 78.9, 99.0, "Washington D.C.", "USD"),
            ("China", "Asia", 1439323776, 9596961, 17963.2, 76.1, 96.8, "Beijing", "CNY"),
            ("India", "Asia", 1380004385, 3287263, 3385.1, 69.7, 74.4, "New Delhi", "INR"),
            ("Indonesia", "Asia", 273523615, 1904569, 1186.1, 71.7, 95.7, "Jakarta", "IDR"),
            ("Pakistan", "Asia", 220892340, 881913, 348.3, 67.3, 59.1, "Islamabad", "PKR"),
            ("Brazil", "South America", 212559417, 8515767, 1920.1, 75.9, 93.2, "Brasilia", "BRL"),
            ("Nigeria", "Africa", 206139589, 923768, 440.8, 54.7, 62.0, "Abuja", "NGN"),
            ("Bangladesh", "Asia", 164689383, 147570, 416.3, 72.6, 74.7, "Dhaka", "BDT"),
            ("Russia", "Europe", 145934462, 17098246, 1775.8, 72.6, 99.7, "Moscow", "RUB"),
            ("Mexico", "North America", 128932753, 1964375, 1293.0, 75.1, 95.4, "Mexico City", "MXN"),
            ("Japan", "Asia", 126476461, 377975, 4231.1, 84.6, 99.0, "Tokyo", "JPY"),
            ("Ethiopia", "Africa", 114963588, 1104300, 111.3, 66.6, 51.8, "Addis Ababa", "ETB"),
            ("Philippines", "Asia", 109581078, 300000, 394.1, 71.2, 98.2, "Manila", "PHP"),
            ("Egypt", "Africa", 102334404, 1002450, 404.1, 72.0, 71.2, "Cairo", "EGP"),
            ("Vietnam", "Asia", 97338579, 331212, 408.8, 75.4, 95.0, "Hanoi", "VND"),
            ("Germany", "Europe", 83783942, 357022, 4072.2, 81.3, 99.0, "Berlin", "EUR"),
            ("Turkey", "Asia", 84339067, 783562, 819.0, 77.7, 96.2, "Ankara", "TRY"),
            ("Iran", "Asia", 83992949, 1648195, 231.5, 76.7, 85.5, "Tehran", "IRR"),
            ("Thailand", "Asia", 69799978, 513120, 495.4, 77.2, 93.8, "Bangkok", "THB"),
            ("United Kingdom", "Europe", 67886011, 243610, 3070.7, 81.3, 99.0, "London", "GBP"),
            ("France", "Europe", 65273511, 640679, 2782.9, 82.7, 99.0, "Paris", "EUR"),
            ("Italy", "Europe", 60461826, 301340, 2010.4, 83.5, 99.2, "Rome", "EUR"),
            ("Tanzania", "Africa", 59734218, 947303, 67.8, 65.5, 77.9, "Dodoma", "TZS"),
            ("South Africa", "Africa", 59308690, 1221037, 405.9, 64.1, 87.0, "Pretoria", "ZAR"),
            ("Kenya", "Africa", 53771296, 580367, 110.3, 66.7, 81.5, "Nairobi", "KES"),
            ("South Korea", "Asia", 51269185, 100210, 1665.2, 83.5, 98.0, "Seoul", "KRW"),
            ("Colombia", "South America", 50882891, 1141748, 314.5, 77.3, 95.6, "Bogota", "COP"),
            ("Spain", "Europe", 46754778, 505992, 1397.5, 83.6, 98.4, "Madrid", "EUR"),
            ("Argentina", "South America", 45195774, 2780400, 632.8, 76.7, 99.0, "Buenos Aires", "ARS"),
            ("Canada", "North America", 37742154, 9984670, 2139.8, 82.4, 99.0, "Ottawa", "CAD"),
            ("Australia", "Oceania", 25499884, 7692024, 1675.4, 83.4, 99.0, "Canberra", "AUD"),
            ("Saudi Arabia", "Asia", 34813871, 2149690, 1108.1, 75.1, 97.6, "Riyadh", "SAR"),
            ("Ghana", "Africa", 31072940, 238533, 77.6, 64.1, 79.0, "Accra", "GHS"),
            ("Nepal", "Asia", 29136808, 147181, 36.3, 70.8, 67.9, "Kathmandu", "NPR"),
            ("Venezuela", "South America", 28435940, 916445, 482.4, 72.1, 97.1, "Caracas", "VEF"),
            ("Peru", "South America", 32971854, 1285216, 223.2, 76.7, 94.4, "Lima", "PEN"),
            ("Malaysia", "Asia", 32365999, 329847, 372.7, 76.2, 95.0, "Kuala Lumpur", "MYR"),
            ("Angola", "Africa", 32866272, 1246700, 72.5, 61.2, 71.1, "Luanda", "AOA"),
            ("Mozambique", "Africa", 31255435, 801590, 14.4, 60.9, 47.0, "Maputo", "MZN"),
            ("Ivory Coast", "Africa", 26378274, 322463, 70.0, 57.8, 47.2, "Yamoussoukro", "XOF"),
            ("Sweden", "Europe", 10099265, 450295, 585.9, 82.8, 99.0, "Stockholm", "SEK"),
            ("Norway", "Europe", 5421241, 385207, 579.3, 82.8, 99.0, "Oslo", "NOK"),
            ("Switzerland", "Europe", 8654622, 41277, 807.7, 83.8, 99.0, "Bern", "CHF"),
            ("Singapore", "Asia", 5850342, 728, 397.0, 83.6, 97.3, "Singapore", "SGD"),
            ("New Zealand", "Oceania", 4822233, 270467, 249.9, 82.3, 99.0, "Wellington", "NZD"),
            ("Israel", "Asia", 8655535, 20770, 525.0, 83.0, 97.8, "Jerusalem", "ILS"),
            ("Chile", "South America", 19116201, 756102, 301.0, 80.2, 96.6, "Santiago", "CLP"),
            ("Poland", "Europe", 37846611, 312696, 688.2, 78.7, 99.8, "Warsaw", "PLN"),
            ("Ukraine", "Europe", 43733762, 603550, 200.1, 72.5, 99.8, "Kyiv", "UAH"),
            ("Netherlands", "Europe", 17134872, 41543, 1013.6, 82.3, 99.0, "Amsterdam", "EUR"),
        ]
        conn.executemany(
            "INSERT INTO world_countries (country, continent, population, area_sq_km, gdp_usd_billion, life_expectancy, literacy_rate, capital, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            countries_data,
        )

        # Dataset 2: Sales Orders
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_date TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_segment TEXT NOT NULL,
                region TEXT NOT NULL,
                city TEXT NOT NULL,
                product_category TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                discount REAL DEFAULT 0,
                total_amount REAL NOT NULL,
                profit REAL NOT NULL,
                shipping_cost REAL NOT NULL,
                order_status TEXT NOT NULL
            )
        """)
        import random
        random.seed(42)
        segments = ["Consumer", "Corporate", "Small Business", "Home Office"]
        regions = ["East", "West", "Central", "South"]
        cities_by_region = {
            "East": ["New York", "Boston", "Philadelphia", "Miami", "Atlanta"],
            "West": ["Los Angeles", "San Francisco", "Seattle", "Portland", "Denver"],
            "Central": ["Chicago", "Dallas", "Houston", "Minneapolis", "Detroit"],
            "South": ["Charlotte", "Nashville", "New Orleans", "Austin", "Tampa"],
        }
        categories = {
            "Electronics": [("Laptop Pro 15", 999.99), ("Wireless Mouse", 29.99), ("USB-C Hub", 49.99), ("Monitor 27inch", 399.99), ("Keyboard Mechanical", 89.99), ("Webcam HD", 59.99), ("External SSD 1TB", 109.99), ("Headphones Wireless", 149.99)],
            "Office Supplies": [("Paper A4 500sheets", 8.99), ("Pen Set Premium", 15.99), ("Notebook Leather", 24.99), ("Stapler Heavy-Duty", 19.99), ("Desk Organizer", 34.99), ("Whiteboard Markers", 12.99), ("File Folders 50pk", 22.99), ("Binder Clips Box", 6.99)],
            "Furniture": [("Standing Desk", 599.99), ("Office Chair Ergonomic", 449.99), ("Bookshelf 5-Tier", 189.99), ("Filing Cabinet", 279.99), ("Desk Lamp LED", 45.99), ("Monitor Stand", 79.99), ("Conference Table", 899.99), ("Storage Cabinet", 349.99)],
            "Software": [("Antivirus Annual", 49.99), ("Office Suite License", 149.99), ("Project Management Tool", 29.99), ("Cloud Storage 1TB", 9.99), ("Design Software", 199.99), ("Accounting Software", 99.99), ("CRM License", 79.99), ("VPN Annual", 39.99)],
        }
        statuses = ["Delivered", "Delivered", "Delivered", "Delivered", "Shipped", "Processing", "Cancelled"]
        customers = [
            "Acme Corp", "TechVision Inc", "DataFlow LLC", "Pinnacle Solutions", "BrightPath Co",
            "Summit Digital", "Horizon Systems", "NexGen Labs", "CloudBridge Inc", "Pulse Analytics",
            "Metro Solutions", "FreshWave Corp", "AlphaPoint LLC", "ClearView Tech", "SwiftEdge Inc",
            "BlueOcean Co", "SkyHigh Systems", "RedRock Labs", "GreenField Inc", "IronClad Corp",
            "StarLight Digital", "PrimeForce LLC", "EagleEye Tech", "RiverBend Co", "ThunderBolt Inc",
        ]
        orders_data = []
        for i in range(500):
            year = random.choice([2023, 2023, 2024, 2024, 2024, 2025])
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            order_date = f"{year}-{month:02d}-{day:02d}"
            customer = random.choice(customers)
            segment = random.choice(segments)
            region = random.choice(regions)
            city = random.choice(cities_by_region[region])
            category = random.choice(list(categories.keys()))
            product_name, unit_price = random.choice(categories[category])
            quantity = random.randint(1, 20)
            discount = random.choice([0, 0, 0, 0.05, 0.1, 0.15, 0.2])
            total_amount = round(quantity * unit_price * (1 - discount), 2)
            profit = round(total_amount * random.uniform(0.05, 0.35), 2)
            shipping_cost = round(random.uniform(5, 50), 2)
            status = random.choice(statuses)
            orders_data.append((order_date, customer, segment, region, city, category, product_name, quantity, unit_price, discount, total_amount, profit, shipping_cost, status))

        conn.executemany(
            "INSERT INTO sales_orders (order_date, customer_name, customer_segment, region, city, product_category, product_name, quantity, unit_price, discount, total_amount, profit, shipping_cost, order_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            orders_data,
        )

        # Dataset 3: Employees
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL,
                department TEXT NOT NULL,
                job_title TEXT NOT NULL,
                hire_date TEXT NOT NULL,
                salary REAL NOT NULL,
                bonus_pct REAL DEFAULT 0,
                manager_id INTEGER,
                office_location TEXT NOT NULL,
                employment_status TEXT NOT NULL DEFAULT 'Active',
                performance_rating REAL
            )
        """)
        departments = {
            "Engineering": ["Software Engineer", "Senior Software Engineer", "Staff Engineer", "Engineering Manager", "DevOps Engineer", "QA Engineer", "Data Engineer"],
            "Product": ["Product Manager", "Senior Product Manager", "Product Analyst", "UX Designer", "UI Designer"],
            "Sales": ["Sales Representative", "Sales Manager", "Account Executive", "Sales Director", "Business Development Rep"],
            "Marketing": ["Marketing Manager", "Content Strategist", "SEO Specialist", "Social Media Manager", "Brand Manager"],
            "Finance": ["Financial Analyst", "Accountant", "Finance Manager", "Controller", "Payroll Specialist"],
            "HR": ["HR Generalist", "Recruiter", "HR Manager", "Benefits Coordinator", "Training Specialist"],
            "Operations": ["Operations Manager", "Supply Chain Analyst", "Logistics Coordinator", "Facilities Manager", "Office Administrator"],
        }
        first_names = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen", "Daniel", "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark", "Margaret", "Steven", "Sandra", "Andrew", "Ashley", "Paul", "Emily", "Joshua", "Donna", "Kenneth", "Michelle", "Kevin", "Carol"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"]
        offices = ["New York", "San Francisco", "Chicago", "Austin", "Seattle", "Boston", "Denver", "Remote"]
        salary_ranges = {
            "Engineering": (85000, 200000),
            "Product": (80000, 180000),
            "Sales": (55000, 150000),
            "Marketing": (55000, 140000),
            "Finance": (60000, 160000),
            "HR": (50000, 130000),
            "Operations": (50000, 120000),
        }
        emp_data = []
        for i in range(150):
            fname = random.choice(first_names)
            lname = random.choice(last_names)
            email = f"{fname.lower()}.{lname.lower()}{random.randint(1,99)}@company.com"
            dept = random.choice(list(departments.keys()))
            title = random.choice(departments[dept])
            year = random.randint(2015, 2025)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            hire_date = f"{year}-{month:02d}-{day:02d}"
            low, high = salary_ranges[dept]
            salary = round(random.uniform(low, high), 2)
            bonus = round(random.uniform(0, 0.25), 2)
            manager_id = random.randint(1, 20) if i > 20 else None
            office = random.choice(offices)
            status = random.choice(["Active", "Active", "Active", "Active", "Active", "On Leave", "Terminated"])
            rating = round(random.uniform(1, 5), 1)
            emp_data.append((fname, lname, email, dept, title, hire_date, salary, bonus, manager_id, office, status, rating))

        conn.executemany(
            "INSERT INTO employees (first_name, last_name, email, department, job_title, hire_date, salary, bonus_pct, manager_id, office_location, employment_status, performance_rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            emp_data,
        )

        # Dataset 4: Product Inventory
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                unit_price REAL NOT NULL,
                cost_price REAL NOT NULL,
                stock_quantity INTEGER NOT NULL,
                reorder_level INTEGER NOT NULL,
                supplier TEXT NOT NULL,
                warehouse_location TEXT NOT NULL,
                last_restocked TEXT,
                rating REAL,
                reviews_count INTEGER DEFAULT 0
            )
        """)
        brands = {
            "Electronics": ["TechPro", "DigiMax", "SmartEdge", "NovaTech", "CyberLink"],
            "Office Supplies": ["PaperCraft", "WriteWell", "DeskMate", "OrganizerPro", "OfficeKing"],
            "Furniture": ["ComfortZone", "WoodCraft", "ErgoDesign", "ModernSpace", "SteelCase"],
            "Clothing": ["UrbanStyle", "ClassicFit", "SportFlex", "EcoWear", "PremiumThread"],
        }
        suppliers = ["GlobalSource Ltd", "Pacific Imports", "Continental Supply", "DirectTrade Inc", "PrimeVendor Co"]
        warehouses = ["Warehouse A - East", "Warehouse B - West", "Warehouse C - Central", "Warehouse D - South"]
        inv_data = []
        sku_counter = 1000
        products_inv = {
            "Electronics": [("Wireless Earbuds", 79.99, 35.0), ("Smart Watch", 249.99, 120.0), ("Bluetooth Speaker", 59.99, 25.0), ("Tablet 10inch", 449.99, 220.0), ("Power Bank 20000mAh", 39.99, 15.0), ("Smart Home Hub", 129.99, 55.0), ("Action Camera", 199.99, 90.0), ("E-Reader", 139.99, 65.0), ("Drone Mini", 299.99, 140.0), ("Gaming Controller", 59.99, 25.0)],
            "Office Supplies": [("Printer Paper Ream", 12.99, 5.0), ("Ink Cartridge Black", 29.99, 10.0), ("Sticky Notes 12pk", 9.99, 3.0), ("Desk Calendar", 14.99, 5.0), ("Paper Shredder", 89.99, 40.0), ("Label Maker", 49.99, 20.0), ("Desk Fan USB", 19.99, 8.0), ("Document Scanner", 179.99, 80.0), ("Ergonomic Wrist Rest", 24.99, 10.0), ("Cable Management Kit", 15.99, 6.0)],
            "Furniture": [("L-Shaped Desk", 399.99, 180.0), ("Mesh Office Chair", 299.99, 130.0), ("Standing Desk Converter", 249.99, 110.0), ("Under Desk Drawer", 69.99, 30.0), ("Monitor Arm Dual", 119.99, 50.0), ("Acoustic Panel Set", 89.99, 35.0), ("Footrest Adjustable", 44.99, 18.0), ("Whiteboard 4x3", 149.99, 60.0), ("Coat Rack", 59.99, 25.0), ("Plant Stand", 34.99, 14.0)],
            "Clothing": [("Polo Shirt", 34.99, 12.0), ("Khaki Pants", 49.99, 18.0), ("Running Shoes", 89.99, 35.0), ("Winter Jacket", 129.99, 50.0), ("Baseball Cap", 19.99, 7.0), ("Backpack Laptop", 69.99, 28.0), ("Sunglasses", 24.99, 8.0), ("Leather Belt", 29.99, 10.0), ("Casual Sneakers", 64.99, 25.0), ("Dress Shirt", 44.99, 16.0)],
        }
        for cat, products in products_inv.items():
            for pname, price, cost in products:
                sku = f"SKU-{sku_counter}"
                sku_counter += 1
                brand = random.choice(brands[cat])
                stock = random.randint(0, 500)
                reorder = random.randint(10, 50)
                supplier = random.choice(suppliers)
                warehouse = random.choice(warehouses)
                year = random.choice([2024, 2025])
                month = random.randint(1, 12)
                day = random.randint(1, 28)
                last_restocked = f"{year}-{month:02d}-{day:02d}"
                rating = round(random.uniform(3.0, 5.0), 1)
                reviews = random.randint(5, 500)
                inv_data.append((sku, pname, cat, brand, price, cost, stock, reorder, supplier, warehouse, last_restocked, rating, reviews))

        conn.executemany(
            "INSERT INTO product_inventory (sku, product_name, category, brand, unit_price, cost_price, stock_quantity, reorder_level, supplier, warehouse_location, last_restocked, rating, reviews_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            inv_data,
        )

    print("Sample datasets loaded successfully!")
