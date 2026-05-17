import hashlib
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import default_config


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "company_data.db")


def _get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_database(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            vietnamese_name TEXT,
            tax_code TEXT,
            address TEXT,
            status TEXT DEFAULT 'pending',
            vn_data_source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS search_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            search_query TEXT,
            search_type TEXT,
            result_rank INTEGER,
            url TEXT,
            title TEXT,
            snippet TEXT,
            credits_used REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS filtered_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_result_id INTEGER,
            company_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            source_type TEXT,
            should_scrape BOOLEAN DEFAULT 1,
            reason TEXT,
            relevance_score REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS scraped_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            filtered_link_id INTEGER,
            url TEXT,
            source_type TEXT,
            markdown_content TEXT,
            content_length INTEGER DEFAULT 0,
            scrape_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS extracted_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            source_type TEXT,
            source_url TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            fax TEXT,
            representative TEXT,
            raw_ai_response TEXT,
            confidence_score REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            step TEXT,
            source_name TEXT,
            status TEXT,
            credits_used REAL DEFAULT 0,
            network_latency_ms REAL,
            error_message TEXT,
            error_category TEXT,
            raw_request TEXT,
            raw_response_summary TEXT,
            metadata TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS query_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_hash TEXT UNIQUE NOT NULL,
            query_text TEXT,
            company_id INTEGER,
            result_count INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_quota (
            date TEXT PRIMARY KEY,
            gemini_grounding_used INTEGER DEFAULT 0,
            serper_used INTEGER DEFAULT 0
        );
    """)


class DatabaseManager:
    """Manages all database operations for the pipeline.

    Each method opens and closes its own connection — NOT thread-safe.
    """

    def __init__(self):
        conn = _get_connection()
        try:
            _init_database(conn)
        finally:
            conn.close()

    # ── Companies ──

    def insert_company(self, original_name: str, **kwargs) -> int:
        conn = _get_connection()
        try:
            fields = {"original_name": original_name, **kwargs}
            fields["updated_at"] = datetime.now().isoformat()
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO companies ({cols}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_company(self, company_id: int) -> Optional[Dict]:
        conn = _get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM companies WHERE id = ?", (company_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_companies(self, status: str = None) -> List[Dict]:
        conn = _get_connection()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM companies WHERE status = ?", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM companies").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_company(self, company_id: int, **kwargs) -> None:
        conn = _get_connection()
        try:
            kwargs["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = tuple(kwargs.values()) + (company_id,)
            conn.execute(
                f"UPDATE companies SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
        finally:
            conn.close()

    # ── Search Results ──

    def insert_search_result(
        self, company_id: int, url: str, **kwargs
    ) -> int:
        conn = _get_connection()
        try:
            fields = {"company_id": company_id, "url": url, **kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO search_results ({cols}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_search_results_for_company(
        self, company_id: int
    ) -> List[Dict]:
        conn = _get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM search_results WHERE company_id = ? ORDER BY result_rank",
                (company_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Filtered Links ──

    def insert_filtered_link(
        self, company_id: int, url: str, **kwargs
    ) -> int:
        conn = _get_connection()
        try:
            fields = {"company_id": company_id, "url": url, **kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO filtered_links ({cols}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_filtered_links_for_company(
        self, company_id: int, should_scrape: bool = None
    ) -> List[Dict]:
        conn = _get_connection()
        try:
            if should_scrape is not None:
                rows = conn.execute(
                    "SELECT * FROM filtered_links WHERE company_id = ? AND should_scrape = ?",
                    (company_id, int(should_scrape)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM filtered_links WHERE company_id = ?",
                    (company_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Scraped Pages ──

    def insert_scraped_page(
        self, company_id: int, url: str, **kwargs
    ) -> int:
        conn = _get_connection()
        try:
            fields = {"company_id": company_id, "url": url, **kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO scraped_pages ({cols}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_scraped_pages_for_company(
        self, company_id: int
    ) -> List[Dict]:
        conn = _get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM scraped_pages WHERE company_id = ?",
                (company_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_scraped_page(self, page_id: int, **kwargs) -> None:
        conn = _get_connection()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = tuple(kwargs.values()) + (page_id,)
            conn.execute(
                f"UPDATE scraped_pages SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
        finally:
            conn.close()

    # ── Extracted Contacts ──

    def insert_extracted_contact(
        self, company_id: int, **kwargs
    ) -> int:
        conn = _get_connection()
        try:
            fields = {"company_id": company_id, **kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO extracted_contacts ({cols}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_extracted_contacts_for_company(
        self, company_id: int
    ) -> List[Dict]:
        conn = _get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM extracted_contacts WHERE company_id = ?",
                (company_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Pipeline Logs ──

    def insert_pipeline_log(self, **kwargs) -> int:
        conn = _get_connection()
        try:
            fields = {**kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            cur = conn.execute(
                f"INSERT INTO pipeline_logs ({cols}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # ── Query Cache ──

    def is_query_cached(self, query_text: str) -> bool:
        conn = _get_connection()
        try:
            query_hash = hashlib.sha256(query_text.encode()).hexdigest()
            row = conn.execute(
                "SELECT 1 FROM query_cache WHERE query_hash = ? AND (expires_at IS NULL OR expires_at > ?)",
                (query_hash, datetime.now().isoformat()),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def insert_query_cache(
        self, query_text: str, company_id: int = None, result_count: int = 0
    ) -> int:
        conn = _get_connection()
        try:
            query_hash = hashlib.sha256(query_text.encode()).hexdigest()
            expires_at = (
                datetime.now() + timedelta(days=default_config.CACHE_TTL_DAYS)
            ).isoformat()
            cur = conn.execute(
                """INSERT OR REPLACE INTO query_cache
                   (query_hash, query_text, company_id, result_count, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (query_hash, query_text, company_id, result_count, expires_at),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # ── Daily Quota ──

    def get_daily_quota(self, date_str: str = None) -> Dict:
        conn = _get_connection()
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            row = conn.execute(
                "SELECT * FROM daily_quota WHERE date = ?", (date_str,)
            ).fetchone()
            if row:
                return dict(row)
            return {"date": date_str, "gemini_grounding_used": 0, "serper_used": 0}
        finally:
            conn.close()

    def upsert_daily_quota(
        self, date_str: str, gemini_grounding_used: int = None, serper_used: int = None
    ) -> None:
        """Upsert daily quota atomically — no race condition.

        Args:
            date_str: Date string in YYYY-MM-DD format.
            gemini_grounding_used: Gemini grounding usage count.
            serper_used: Serper usage count.
        """
        conn = _get_connection()
        try:
            # Build dynamic query based on which fields are provided
            updates = []
            values = [date_str]
            insert_fields = ["date"]
            insert_values = ["?"]

            if gemini_grounding_used is not None:
                insert_fields.append("gemini_grounding_used")
                insert_values.append("?")
                values.append(gemini_grounding_used)
                updates.append("gemini_grounding_used = excluded.gemini_grounding_used")

            if serper_used is not None:
                insert_fields.append("serper_used")
                insert_values.append("?")
                values.append(serper_used)
                updates.append("serper_used = excluded.serper_used")

            # If no fields provided, just ensure row exists
            if not updates:
                insert_fields.append("gemini_grounding_used")
                insert_values.append("0")
                insert_fields.append("serper_used")
                insert_values.append("0")

            fields_str = ", ".join(insert_fields)
            values_str = ", ".join(insert_values)
            updates_str = ", ".join(updates) if updates else "gemini_grounding_used = gemini_grounding_used"

            conn.execute(
                f"""INSERT INTO daily_quota ({fields_str})
                    VALUES ({values_str})
                    ON CONFLICT(date) DO UPDATE SET {updates_str}""",
                values,
            )
            conn.commit()
        finally:
            conn.close()

    def _update_daily_quota(
        self, conn: sqlite3.Connection, date_str: str, updates: dict
    ) -> None:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = tuple(updates.values()) + (date_str,)
        conn.execute(
            f"UPDATE daily_quota SET {set_clause} WHERE date = ?", values
        )
        conn.commit()
