"""
Advanced Schema Retriever — 6-level hybrid retrieval system.

Elevates schema retrieval from simple keyword matching to Databricks Genie-level
intelligent schema resolution using multiple retrieval signals:

Level 1: Value Dictionaries — match actual column values in the question
Level 2: Column Statistics — data profiling (distinct counts, min/max, cardinality)
Level 3: Embedding Search — semantic similarity via TF-IDF word vectors
Level 4: LLM-Assisted Selection — cheap LLM call for schema resolution
Level 5: Query History Patterns — co-occurrence learning from past queries
Level 6: Hybrid Ranker — weighted fusion of all retrieval signals
"""

import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from openai import OpenAI

from app.database import get_db


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievalScore:
    """Score from a single retrieval signal."""
    table: str
    column: str | None = None
    score: float = 0.0
    method: str = ""
    detail: str = ""


@dataclass
class RetrievalResult:
    """Combined result from hybrid retrieval."""
    tables: list[str] = field(default_factory=list)
    table_scores: dict[str, float] = field(default_factory=dict)
    relevant_columns: list[dict] = field(default_factory=list)
    value_matches: list[dict] = field(default_factory=list)
    column_stats: list[dict] = field(default_factory=list)
    retrieval_signals: dict[str, list[RetrievalScore]] = field(default_factory=dict)
    method_summary: str = ""
    filter_hints: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Level 1: Value Dictionary
# ---------------------------------------------------------------------------

def init_value_dictionary():
    """Create the value dictionary table and auto-scan column values."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_value_dictionary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                sample_value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                UNIQUE(table_name, column_name, normalized_value)
            )
        """)
    _scan_column_values()


def _scan_column_values():
    """Auto-scan categorical columns and populate value dictionary."""
    with get_db() as conn:
        # Check if already populated
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM semantic_value_dictionary"
        ).fetchone()["cnt"]
        if count > 0:
            return

        # Get all data tables (exclude system tables)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'semantic_%' "
            "AND name NOT IN ('query_history', 'settings', 'conversation_sessions', "
            "'conversation_messages', 'schema_usage_patterns')"
        ).fetchall()

        for table_row in tables:
            table_name = table_row["name"]
            columns = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()

            for col in columns:
                col_name = col["name"]
                col_type = (col["type"] or "").upper()

                # Skip ID columns and large text fields
                if col_name == "id":
                    continue

                # Check cardinality — only index categorical columns (distinct < 100)
                try:
                    distinct_count = conn.execute(
                        f"SELECT COUNT(DISTINCT \"{col_name}\") as cnt FROM \"{table_name}\" "
                        f"WHERE \"{col_name}\" IS NOT NULL"
                    ).fetchone()["cnt"]
                except Exception:
                    continue

                if distinct_count > 100 or distinct_count == 0:
                    continue

                # Get top values with frequencies
                try:
                    values = conn.execute(
                        f"SELECT \"{col_name}\" as val, COUNT(*) as freq "
                        f"FROM \"{table_name}\" WHERE \"{col_name}\" IS NOT NULL "
                        f"GROUP BY \"{col_name}\" ORDER BY freq DESC LIMIT 50"
                    ).fetchall()
                except Exception:
                    continue

                for v in values:
                    val = str(v["val"])
                    if not val or val.lower() == "none":
                        continue
                    normalized = val.lower().strip()
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO semantic_value_dictionary "
                            "(table_name, column_name, sample_value, normalized_value, frequency) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (table_name, col_name, val, normalized, v["freq"]),
                        )
                    except Exception:
                        continue


def match_values(question: str) -> list[RetrievalScore]:
    """Find column value matches in the user's question."""
    q_lower = question.lower()
    scores: list[RetrievalScore] = []

    with get_db() as conn:
        values = conn.execute(
            "SELECT table_name, column_name, sample_value, normalized_value, frequency "
            "FROM semantic_value_dictionary ORDER BY LENGTH(normalized_value) DESC"
        ).fetchall()

    for v in values:
        normalized = v["normalized_value"]
        # Only match values with 2+ characters to avoid false positives
        if len(normalized) < 2:
            continue
        # Check if the value appears in the question
        # Use word boundary matching for short values
        if len(normalized) <= 4:
            pattern = r'\b' + re.escape(normalized) + r'\b'
            if re.search(pattern, q_lower):
                scores.append(RetrievalScore(
                    table=v["table_name"],
                    column=v["column_name"],
                    score=0.8 + (0.2 * min(v["frequency"] / 100, 1.0)),
                    method="value_dictionary",
                    detail=f"Matched value '{v['sample_value']}' in {v['table_name']}.{v['column_name']}",
                ))
        elif normalized in q_lower:
            scores.append(RetrievalScore(
                table=v["table_name"],
                column=v["column_name"],
                score=0.9 + (0.1 * min(v["frequency"] / 100, 1.0)),
                method="value_dictionary",
                detail=f"Matched value '{v['sample_value']}' in {v['table_name']}.{v['column_name']}",
            ))

    return scores


def get_value_dictionary(table_name: str | None = None) -> list[dict]:
    """Get value dictionary entries, optionally filtered by table."""
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_value_dictionary WHERE table_name = ? "
                "ORDER BY column_name, frequency DESC",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM semantic_value_dictionary "
                "ORDER BY table_name, column_name, frequency DESC"
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Level 2: Column Statistics
# ---------------------------------------------------------------------------

def init_column_stats():
    """Create column stats table and auto-profile all columns."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_column_stats (
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                data_type TEXT,
                distinct_count INTEGER,
                null_count INTEGER,
                total_count INTEGER,
                min_value TEXT,
                max_value TEXT,
                avg_value REAL,
                is_categorical INTEGER DEFAULT 0,
                sample_values TEXT,
                PRIMARY KEY (table_name, column_name)
            )
        """)
    _profile_columns()


def _profile_columns():
    """Auto-profile all data columns."""
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM semantic_column_stats"
        ).fetchone()["cnt"]
        if count > 0:
            return

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'semantic_%' "
            "AND name NOT IN ('query_history', 'settings', 'conversation_sessions', "
            "'conversation_messages', 'schema_usage_patterns')"
        ).fetchall()

        for table_row in tables:
            table_name = table_row["name"]
            columns = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            total_count = conn.execute(
                f"SELECT COUNT(*) as cnt FROM \"{table_name}\""
            ).fetchone()["cnt"]

            for col in columns:
                col_name = col["name"]
                col_type = col["type"] or "TEXT"

                try:
                    stats = conn.execute(
                        f"SELECT COUNT(DISTINCT \"{col_name}\") as distinct_count, "
                        f"SUM(CASE WHEN \"{col_name}\" IS NULL THEN 1 ELSE 0 END) as null_count, "
                        f"MIN(\"{col_name}\") as min_val, "
                        f"MAX(\"{col_name}\") as max_val "
                        f"FROM \"{table_name}\""
                    ).fetchone()

                    distinct_count = stats["distinct_count"]
                    null_count = stats["null_count"]
                    min_val = str(stats["min_val"]) if stats["min_val"] is not None else None
                    max_val = str(stats["max_val"]) if stats["max_val"] is not None else None

                    # Try to get average for numeric columns
                    avg_val = None
                    if col_type.upper() in ("INTEGER", "REAL", "BIGINT", "FLOAT", "NUMERIC"):
                        try:
                            avg_row = conn.execute(
                                f"SELECT AVG(\"{col_name}\") as avg_val FROM \"{table_name}\""
                            ).fetchone()
                            avg_val = avg_row["avg_val"]
                        except Exception:
                            pass

                    is_categorical = 1 if distinct_count < 50 else 0

                    # Get sample values for categorical columns
                    sample_values = None
                    if is_categorical and distinct_count > 0:
                        try:
                            samples = conn.execute(
                                f"SELECT DISTINCT \"{col_name}\" FROM \"{table_name}\" "
                                f"WHERE \"{col_name}\" IS NOT NULL LIMIT 10"
                            ).fetchall()
                            sample_values = json.dumps([str(s[0]) for s in samples])
                        except Exception:
                            pass

                    conn.execute(
                        "INSERT OR REPLACE INTO semantic_column_stats "
                        "(table_name, column_name, data_type, distinct_count, null_count, "
                        "total_count, min_value, max_value, avg_value, is_categorical, sample_values) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (table_name, col_name, col_type, distinct_count, null_count,
                         total_count, min_val, max_val, avg_val, is_categorical, sample_values),
                    )
                except Exception:
                    continue


def get_column_stats(table_name: str | None = None) -> list[dict]:
    """Retrieve column statistics."""
    with get_db() as conn:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM semantic_column_stats WHERE table_name = ? "
                "ORDER BY column_name",
                (table_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM semantic_column_stats ORDER BY table_name, column_name"
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Level 3: Embedding Search (TF-IDF based word vectors)
# ---------------------------------------------------------------------------

# In-memory cache for the embedding index
_embedding_index: dict[str, dict] | None = None


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove short tokens."""
    return [t for t in re.split(r'[^a-z0-9]+', text.lower()) if len(t) > 1]


def _build_embedding_index() -> dict[str, dict]:
    """Build TF-IDF-like word vectors for all metadata."""
    global _embedding_index

    if _embedding_index is not None:
        return _embedding_index

    documents: dict[str, str] = {}  # key -> text

    with get_db() as conn:
        # Column descriptions
        cols = conn.execute(
            "SELECT table_name, column_name, description, business_name "
            "FROM semantic_column_descriptions"
        ).fetchall()
        for col in cols:
            key = f"{col['table_name']}.{col['column_name']}"
            text_parts = [
                col["table_name"], col["column_name"],
                col["description"] or "",
                col["business_name"] or "",
            ]
            documents[key] = " ".join(text_parts)

        # Table-level documents (aggregate all column descriptions)
        table_docs: dict[str, list[str]] = defaultdict(list)
        for col in cols:
            table_docs[col["table_name"]].append(
                f"{col['column_name']} {col['description'] or ''} {col['business_name'] or ''}"
            )

        # Glossary
        glossary = conn.execute(
            "SELECT term, definition, mapped_table, synonyms FROM semantic_glossary"
        ).fetchall()
        for g in glossary:
            table = g["mapped_table"] or "general"
            text = f"{g['term']} {g['definition']} {g['synonyms'] or ''}"
            if table in table_docs:
                table_docs[table].append(text)
            documents[f"glossary.{g['term']}"] = text

        # Metrics
        metrics = conn.execute(
            "SELECT name, description, table_name FROM semantic_metrics"
        ).fetchall()
        for m in metrics:
            text = f"{m['name']} {m['description']}"
            if m["table_name"] in table_docs:
                table_docs[m["table_name"]].append(text)

        # Add table-level documents
        for table, parts in table_docs.items():
            documents[f"__table__{table}"] = " ".join(parts)

    # Build vocabulary (IDF)
    doc_count = len(documents)
    word_doc_freq: Counter = Counter()
    doc_tokens: dict[str, list[str]] = {}

    for key, text in documents.items():
        tokens = _tokenize(text)
        doc_tokens[key] = tokens
        unique_tokens = set(tokens)
        for token in unique_tokens:
            word_doc_freq[token] += 1

    # Build TF-IDF vectors
    _embedding_index = {}
    for key, tokens in doc_tokens.items():
        if not tokens:
            continue
        tf = Counter(tokens)
        vector: dict[str, float] = {}
        for word, count in tf.items():
            tf_val = count / len(tokens)
            idf_val = math.log((doc_count + 1) / (word_doc_freq[word] + 1)) + 1
            vector[word] = tf_val * idf_val
        _embedding_index[key] = vector

    return _embedding_index


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Compute cosine similarity between two sparse word vectors."""
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0

    dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def embedding_search(question: str, top_k: int = 20) -> list[RetrievalScore]:
    """Find semantically similar tables/columns using TF-IDF word vectors."""
    index = _build_embedding_index()
    if not index:
        return []

    # Build query vector using same IDF weights
    query_tokens = _tokenize(question)
    if not query_tokens:
        return []

    # Use document frequencies from the index to compute query TF-IDF
    doc_count = len(index)
    word_doc_freq: Counter = Counter()
    for vec in index.values():
        for word in vec:
            word_doc_freq[word] += 1

    query_tf = Counter(query_tokens)
    query_vec: dict[str, float] = {}
    for word, count in query_tf.items():
        tf_val = count / len(query_tokens)
        idf_val = math.log((doc_count + 1) / (word_doc_freq.get(word, 0) + 1)) + 1
        query_vec[word] = tf_val * idf_val

    # Score all documents
    results: list[tuple[str, float]] = []
    for key, doc_vec in index.items():
        sim = _cosine_similarity(query_vec, doc_vec)
        if sim > 0.05:  # Minimum threshold
            results.append((key, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    results = results[:top_k]

    scores: list[RetrievalScore] = []
    for key, sim in results:
        if key.startswith("__table__"):
            table = key.replace("__table__", "")
            scores.append(RetrievalScore(
                table=table, column=None, score=sim,
                method="embedding_search",
                detail=f"Table '{table}' semantic similarity: {sim:.3f}",
            ))
        elif key.startswith("glossary."):
            term = key.replace("glossary.", "")
            # Look up which table this glossary term maps to
            with get_db() as conn:
                row = conn.execute(
                    "SELECT mapped_table FROM semantic_glossary WHERE term = ?",
                    (term,),
                ).fetchone()
            if row and row["mapped_table"]:
                scores.append(RetrievalScore(
                    table=row["mapped_table"], column=None, score=sim * 0.8,
                    method="embedding_search",
                    detail=f"Glossary term '{term}' similarity: {sim:.3f}",
                ))
        elif "." in key:
            parts = key.split(".", 1)
            scores.append(RetrievalScore(
                table=parts[0], column=parts[1], score=sim,
                method="embedding_search",
                detail=f"Column '{key}' semantic similarity: {sim:.3f}",
            ))

    return scores


def reset_embedding_index():
    """Reset the cached embedding index (call after metadata changes)."""
    global _embedding_index
    _embedding_index = None


# ---------------------------------------------------------------------------
# Level 4: LLM-Assisted Schema Selection
# ---------------------------------------------------------------------------

def llm_schema_select(question: str, client: OpenAI | None, entities: list[str] | None = None) -> list[RetrievalScore]:
    """Use a cheap LLM call to select relevant tables and columns."""
    if not client:
        return []

    # Build compact table summaries
    with get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'semantic_%' "
            "AND name NOT IN ('query_history', 'settings', 'conversation_sessions', "
            "'conversation_messages', 'schema_usage_patterns')"
        ).fetchall()

        summaries = []
        for t in tables:
            table_name = t["name"]
            cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            col_list = ", ".join(c["name"] for c in cols)

            # Get column descriptions
            descs = conn.execute(
                "SELECT column_name, description, business_name FROM semantic_column_descriptions "
                "WHERE table_name = ?", (table_name,)
            ).fetchall()
            desc_parts = []
            for d in descs:
                biz = f" ({d['business_name']})" if d["business_name"] else ""
                desc_parts.append(f"  - {d['column_name']}{biz}: {d['description']}")

            row_count = conn.execute(
                f"SELECT COUNT(*) as cnt FROM \"{table_name}\""
            ).fetchone()["cnt"]

            summary = f"Table: {table_name} ({row_count} rows)\n  Columns: {col_list}"
            if desc_parts:
                summary += "\n" + "\n".join(desc_parts[:8])  # Limit to 8 descriptions
            summaries.append(summary)

    table_info = "\n\n".join(summaries)

    entity_hint = ""
    if entities:
        entity_hint = f"\nExtracted entities from intent classifier: {', '.join(entities)}"

    try:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        # Try to get model from settings
        try:
            from app.database import get_setting
            model = get_setting("openai_model") or model
        except Exception:
            pass

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "You are a schema resolution component in a compound AI pipeline. "
                    "Given the user's question and available database tables, select the "
                    "most relevant tables and columns for answering the question.\n\n"
                    "Respond with JSON only:\n"
                    '{"tables": ["table1"], '
                    '"columns": ["table1.col1", "table1.col2"], '
                    '"filters": [{"column": "table1.col1", "op": "=", "value": "X"}], '
                    '"reasoning": "brief explanation"}\n\n'
                    "Rules:\n"
                    "- Select only tables needed to answer the question\n"
                    "- Select specific columns, not all columns\n"
                    "- If the question mentions a specific value, include a filter hint\n"
                    "- Be concise in reasoning"
                )},
                {"role": "user", "content": f"Question: {question}{entity_hint}\n\nAvailable tables:\n{table_info}"},
            ],
            temperature=0,
            max_tokens=500,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        result = json.loads(content)
        scores: list[RetrievalScore] = []

        for table in result.get("tables", []):
            scores.append(RetrievalScore(
                table=table, column=None, score=1.0,
                method="llm_selection",
                detail=f"LLM selected table '{table}': {result.get('reasoning', '')}",
            ))

        for col_path in result.get("columns", []):
            if "." in col_path:
                table, col = col_path.split(".", 1)
                scores.append(RetrievalScore(
                    table=table, column=col, score=0.9,
                    method="llm_selection",
                    detail=f"LLM selected column '{col_path}'",
                ))

        # Store filter hints for context assembler
        for f in result.get("filters", []):
            col = f.get("column", "")
            if "." in col:
                table = col.split(".")[0]
                scores.append(RetrievalScore(
                    table=table, column=col.split(".")[1] if "." in col else None,
                    score=0.95,
                    method="llm_filter_hint",
                    detail=f"LLM filter: {col} {f.get('op', '=')} '{f.get('value', '')}'",
                ))

        return scores
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Level 5: Query History Patterns
# ---------------------------------------------------------------------------

def init_usage_patterns():
    """Create query usage pattern tracking table."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_usage_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                co_table TEXT NOT NULL,
                co_column TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(table_name, column_name, co_table, co_column)
            )
        """)


def record_usage(sql: str, tables: list[str]):
    """Record which tables/columns were used together in a successful query."""
    if not sql or not tables:
        return

    # Extract column references from SQL
    sql_lower = sql.lower()
    used_columns: list[tuple[str, str]] = []

    with get_db() as conn:
        for table in tables:
            try:
                cols = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
                for col in cols:
                    col_name = col["name"]
                    # Check if column appears in SQL
                    if col_name.lower() in sql_lower:
                        used_columns.append((table, col_name))
            except Exception:
                continue

        # Record co-occurrences
        for i, (t1, c1) in enumerate(used_columns):
            for t2, c2 in used_columns[i + 1:]:
                try:
                    conn.execute(
                        "INSERT INTO schema_usage_patterns (table_name, column_name, co_table, co_column, frequency) "
                        "VALUES (?, ?, ?, ?, 1) "
                        "ON CONFLICT(table_name, column_name, co_table, co_column) "
                        "DO UPDATE SET frequency = frequency + 1, last_used = CURRENT_TIMESTAMP",
                        (t1, c1, t2, c2),
                    )
                    # Store reverse direction too
                    conn.execute(
                        "INSERT INTO schema_usage_patterns (table_name, column_name, co_table, co_column, frequency) "
                        "VALUES (?, ?, ?, ?, 1) "
                        "ON CONFLICT(table_name, column_name, co_table, co_column) "
                        "DO UPDATE SET frequency = frequency + 1, last_used = CURRENT_TIMESTAMP",
                        (t2, c2, t1, c1),
                    )
                except Exception:
                    continue


def get_usage_boost(tables: list[str], columns: list[str]) -> list[RetrievalScore]:
    """Boost scores for columns that frequently co-occur with already-matched ones."""
    if not tables and not columns:
        return []

    scores: list[RetrievalScore] = []

    with get_db() as conn:
        for table in tables:
            for col in columns:
                try:
                    rows = conn.execute(
                        "SELECT co_table, co_column, frequency FROM schema_usage_patterns "
                        "WHERE table_name = ? AND column_name = ? "
                        "ORDER BY frequency DESC LIMIT 10",
                        (table, col),
                    ).fetchall()
                    for r in rows:
                        # Normalize frequency to 0-1 range (log scale)
                        freq_score = min(math.log(r["frequency"] + 1) / 5.0, 1.0)
                        scores.append(RetrievalScore(
                            table=r["co_table"], column=r["co_column"],
                            score=freq_score,
                            method="usage_pattern",
                            detail=f"Co-occurs with {table}.{col} ({r['frequency']} times)",
                        ))
                except Exception:
                    continue

    return scores


# ---------------------------------------------------------------------------
# Level 6: Hybrid Ranker
# ---------------------------------------------------------------------------

# Keyword retriever (upgraded from original)
TABLE_KEYWORDS = {
    "world_countries": ["country", "countries", "population", "gdp", "continent",
                        "capital", "currency", "area", "life expectancy", "literacy",
                        "nation", "global", "world", "economic"],
    "sales_orders": ["sales", "order", "orders", "revenue", "profit", "customer",
                     "discount", "shipping", "product_category", "segment", "region",
                     "city", "total_amount", "quantity", "price", "income"],
    "employees": ["employee", "employees", "salary", "department", "hire", "job",
                  "performance", "rating", "bonus", "office", "staff", "headcount",
                  "workforce", "compensation", "hr", "worker"],
    "product_inventory": ["product", "inventory", "stock", "sku", "warehouse",
                          "brand", "supplier", "reorder", "rating", "review",
                          "cost_price", "unit_price", "category", "catalog"],
}

# Weights for each retrieval signal
SIGNAL_WEIGHTS = {
    "keyword": 0.15,
    "entity": 0.15,
    "value_dictionary": 0.25,
    "embedding_search": 0.20,
    "llm_selection": 0.15,
    "llm_filter_hint": 0.05,
    "usage_pattern": 0.05,
}


def _keyword_scores(question: str) -> list[RetrievalScore]:
    """Score tables by keyword matching (Level 0 baseline)."""
    q_lower = question.lower()
    scores: list[RetrievalScore] = []

    for table, keywords in TABLE_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in q_lower]
        if matched:
            score = len(matched) / len(keywords)
            scores.append(RetrievalScore(
                table=table, column=None, score=min(score, 1.0),
                method="keyword",
                detail=f"Matched keywords: {', '.join(matched)}",
            ))

    return scores


def _entity_scores(entities: list[str]) -> list[RetrievalScore]:
    """Score tables by entity extraction from intent classifier."""
    scores: list[RetrievalScore] = []
    for entity in entities:
        entity_lower = entity.lower()
        for table in TABLE_KEYWORDS:
            if entity_lower == table or entity_lower in TABLE_KEYWORDS.get(table, []):
                scores.append(RetrievalScore(
                    table=table, column=None, score=1.0,
                    method="entity",
                    detail=f"Entity '{entity}' matched table '{table}'",
                ))
    return scores


def hybrid_retrieve_schema(
    question: str,
    intent: dict,
    client: OpenAI | None = None,
    use_llm: bool = True,
) -> RetrievalResult:
    """
    Combine all 6 retrieval signals to find the most relevant tables and columns.

    Signal weights:
    - keyword:          0.15  (fast baseline)
    - entity:           0.15  (from intent classifier)
    - value_dictionary:  0.25  (exact data value matches)
    - embedding_search:  0.20  (semantic similarity)
    - llm_selection:     0.15  (LLM-based schema resolution)
    - usage_pattern:     0.05  (learned from past queries)
    """
    result = RetrievalResult()
    all_signals: dict[str, list[RetrievalScore]] = {}

    entities = intent.get("entities", [])

    # --- Level 0: Keyword matching (fast, ~1ms) ---
    keyword_scores = _keyword_scores(question)
    all_signals["keyword"] = keyword_scores

    # --- Level 0b: Entity scores from intent classifier ---
    entity_sc = _entity_scores(entities)
    all_signals["entity"] = entity_sc

    # --- Level 1: Value dictionary matching (~2ms) ---
    value_scores = match_values(question)
    all_signals["value_dictionary"] = value_scores

    # --- Level 3: Embedding search (~5ms) ---
    embed_scores = embedding_search(question)
    all_signals["embedding_search"] = embed_scores

    # --- Level 4: LLM-assisted selection (~200-400ms) ---
    llm_scores: list[RetrievalScore] = []
    if use_llm and client:
        llm_scores = llm_schema_select(question, client, entities)
        all_signals["llm_selection"] = [s for s in llm_scores if s.method == "llm_selection"]
        all_signals["llm_filter_hint"] = [s for s in llm_scores if s.method == "llm_filter_hint"]
    else:
        all_signals["llm_selection"] = []
        all_signals["llm_filter_hint"] = []

    # --- Collect initial matched tables for usage pattern lookup ---
    initial_tables: set[str] = set()
    initial_columns: set[str] = set()
    for signal_scores in all_signals.values():
        for s in signal_scores:
            initial_tables.add(s.table)
            if s.column:
                initial_columns.add(s.column)

    # --- Level 5: Usage pattern boost (~1ms) ---
    usage_scores = get_usage_boost(list(initial_tables), list(initial_columns))
    all_signals["usage_pattern"] = usage_scores

    result.retrieval_signals = all_signals

    # --- Level 6: Hybrid ranking with weighted score fusion ---
    table_scores: dict[str, float] = defaultdict(float)
    table_signal_details: dict[str, list[str]] = defaultdict(list)

    for signal_name, signal_scores in all_signals.items():
        weight = SIGNAL_WEIGHTS.get(signal_name, 0.1)
        for s in signal_scores:
            table_scores[s.table] += s.score * weight
            table_signal_details[s.table].append(
                f"{signal_name}({s.score:.2f}×{weight}={s.score * weight:.3f})"
            )

    # Sort by combined score
    sorted_tables = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)

    # If no tables matched at all, include all (broad query)
    if not sorted_tables:
        from app.semantic_layer import get_column_descriptions
        result.tables = list(TABLE_KEYWORDS.keys())
        result.table_scores = {t: 0.0 for t in result.tables}
        all_cols = get_column_descriptions()
        result.relevant_columns = all_cols
        result.method_summary = "No signals matched — using all tables (broad query)"
        return result

    # Take tables with significant scores (at least 20% of top score, or all if close)
    top_score = sorted_tables[0][1]
    threshold = top_score * 0.20
    result.tables = [t for t, s in sorted_tables if s >= threshold]
    result.table_scores = {t: round(s, 4) for t, s in sorted_tables if s >= threshold}

    # Build method summary
    methods_used = [name for name, scores in all_signals.items() if scores]
    result.method_summary = f"Hybrid retrieval using {len(methods_used)} signals: {', '.join(methods_used)}"

    # Collect value matches for context
    result.value_matches = [
        {"table": s.table, "column": s.column, "detail": s.detail}
        for s in value_scores
    ]

    # Collect filter hints from LLM
    result.filter_hints = [
        s.detail for s in llm_scores if s.method == "llm_filter_hint"
    ]

    # Get relevant column descriptions
    from app.semantic_layer import get_column_descriptions
    all_columns = get_column_descriptions()
    result.relevant_columns = [
        col for col in all_columns
        if col["table_name"] in result.tables
    ]

    # Get column stats for relevant tables
    result.column_stats = [
        s for s in get_column_stats()
        if s["table_name"] in result.tables
    ]

    return result
