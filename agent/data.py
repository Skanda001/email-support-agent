"""Standalone mock CRM store for external customer support agent."""
from __future__ import annotations

import sqlite3
import threading
from typing import Any, Optional


class StandaloneCRM:
    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    display_id INTEGER UNIQUE,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    address TEXT,
                    aadhaar TEXT,
                    pan TEXT,
                    account_status TEXT DEFAULT 'Active'
                );

                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    display_id INTEGER UNIQUE,
                    customer_id INTEGER,
                    status TEXT,
                    total_amount REAL,
                    items TEXT
                );
            """)
            # Try to populate from real PostgreSQL database if available
            pg_loaded = False
            try:
                import os, psycopg
                db_url = os.getenv("DATABASE_URL", "postgresql://agentshield:agentshield@localhost:5433/agentshield")
                pg_url = db_url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
                with psycopg.connect(pg_url, connect_timeout=3) as pg_conn:
                    with pg_conn.cursor() as pg_cur:
                        pg_cur.execute("SELECT display_id, display_id, name, email, phone, address, aadhaar, pan, account_status FROM customers")
                        c_rows = pg_cur.fetchall()
                        if c_rows:
                            cur.executemany("INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", c_rows)
                            pg_cur.execute("""
                                SELECT o.display_id, o.display_id, c.display_id, o.status, CAST(o.amount AS REAL), o.product
                                FROM orders o
                                JOIN customers c ON o.customer_id = c.id
                            """)
                            o_rows = pg_cur.fetchall()
                            if o_rows:
                                cur.executemany("INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?)", o_rows)
                            self._conn.commit()
                            pg_loaded = True
            except Exception:
                pass

            if not pg_loaded:
                # Fallback to default mock seed
                cur.executemany(
                    "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (1001, 1001, "Alice Sharma", "alice@example.com", "9876543210", "12 Park Street, Bangalore", "5521 8839 1234", "ABCDE1234F", "Active"),
                        (1008, 1008, "Priya Verma", "priya.verma@example.com", "9823456789", "45 Marine Drive, Mumbai", "6489 3127 5541", "BKLPY4321A", "Active"),
                        (1042, 1042, "Rajesh Kumar", "rajesh.kumar@example.com", "9845123456", "77 Connaught Place, New Delhi", "9123 4567 8901", "BNZPK9988H", "Active"),
                    ],
                )
                cur.executemany(
                    "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (8211, 8211, 1008, "delivered", 45.00, '[{"item": "Wireless Earbuds", "qty": 1}]'),
                        (4821, 4821, 1001, "shipped", 129.99, '[{"item": "Mechanical Keyboard", "qty": 1}]'),
                        (4822, 4822, 1001, "delivered", 24.50, '[{"item": "Laptop Sleeve", "qty": 1}]'),
                    ],
                )
                self._conn.commit()

    def search_by_email(self, email: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM customers WHERE LOWER(email) = LOWER(?)", (email.strip(),))
            r = cur.fetchone()
            if not r:
                return None
            return {"found": True, "display_id": r["display_id"], "name": r["name"], "email": r["email"], "account_status": r["account_status"]}

    def get_customer(self, customer_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM customers WHERE display_id = ?", (int(customer_id),))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "found": True,
                "display_id": r["display_id"],
                "name": r["name"],
                "email": r["email"],
                "phone": r["phone"],
                "address": r["address"],
                "aadhaar": r["aadhaar"],
                "pan": r["pan"],
                "account_status": r["account_status"],
            }

    def get_orders(self, customer_id: int) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC", (int(customer_id),))
            return [{"display_id": r["display_id"], "status": r["status"], "total_amount": r["total_amount"]} for r in cur.fetchall()]

    def refund_order(self, order_id: int, amount: float) -> dict[str, Any]:
        return {"success": True, "order_id": order_id, "amount_refunded": amount, "status": "refunded"}

    def delete_customer(self, customer_id: int) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM customers WHERE display_id = ?", (int(customer_id),))
            self._conn.commit()
            return {"deleted": True, "customer_id": customer_id}


crm = StandaloneCRM()
