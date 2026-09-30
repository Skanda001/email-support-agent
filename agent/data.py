"""Standalone mock CRM store for external customer support agent."""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Optional

FIRST_NAMES = [
    "Aarav", "Aditi", "Alice", "Amit", "Ananya", "Anil", "Arjun", "Deepak",
    "Divya", "Gaurav", "Karan", "Kavita", "Kiran", "Lopa", "Manoj", "Meera",
    "Mohit", "Neha", "Nikhil", "Pooja", "Pradeep", "Priya", "Rahul", "Rajesh",
    "Rakesh", "Riya", "Rohan", "Rohit", "Sameer", "Sanjay", "Shreya", "Sneha",
    "Suresh", "Swati", "Tarun", "Varun", "Vikram", "Vikas", "Vishal", "Yash"
]
LAST_NAMES = [
    "Agarwal", "Bansal", "Bhagat", "Bose", "Chawla", "Chopra", "Das", "Deshmukh",
    "Dutta", "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Kaur", "Khanna",
    "Kumar", "Malhotra", "Mehta", "Mishra", "Mukherjee", "Nair", "Patel",
    "Prasad", "Rao", "Reddy", "Saxena", "Sen", "Sharma", "Singh", "Sinha",
    "Trivedi", "Varma", "Verma", "Yadav"
]
STREETS = [
    "MG Road", "Park Street", "Marine Drive", "Connaught Place", "Banjara Hills",
    "Anna Salai", "FC Road", "Sector 17", "Civil Lines", "Hazratganj",
    "Indiranagar", "Koramangala", "Juhu", "Hauz Khas", "Alwarpet"
]
CITIES = [
    "Bengaluru", "Kolkata", "Mumbai", "New Delhi", "Hyderabad",
    "Chennai", "Pune", "Chandigarh", "Jaipur", "Lucknow"
]
PRODUCTS = [
    ("Wireless Noise-Canceling Headphones", 89.99),
    ("Mechanical Keyboard", 129.99),
    ("Ergonomic Office Chair", 199.50),
    ("Ultra-wide Monitor 27-inch", 349.00),
    ("Smart Fitness Watch", 79.95),
    ("USB-C Docking Station", 59.99),
    ("Wireless Gaming Mouse", 49.50),
    ("Noise-Isolating Earbuds", 39.99),
    ("Laptop Sleeve 15-inch", 24.50),
    ("Aluminium Laptop Stand", 34.00)
]

PRESET_CUSTOMERS = {
    1001: ("Alice Sharma", "alice@example.com", "9876543210", "12 Park Street, Bangalore", "5521 8839 1234", "ABCDE1234F", "Active"),
    1003: ("Rohan Mehta", "rohan.mehta@example.com", "9811223344", "88 MG Road, Bengaluru", "4412 8899 3321", "CGHPR5522K", "Active"),
    1008: ("Priya Verma", "priya.verma@example.com", "9823456789", "45 Marine Drive, Mumbai", "6489 3127 5541", "BKLPY4321A", "Active"),
    1015: ("Lopa Bhagat", "lopa.bhagat@example.com", "9711223344", "88 MG Road, Pune", "4412 9988 3322", "XYZPA7766Q", "Active"),
    1042: ("Rajesh Kumar", "rajesh.kumar@example.com", "9845123456", "77 Connaught Place, New Delhi", "9123 4567 8901", "BNZPK9988H", "Active"),
    1099: ("Vikram Malhotra", "vikram.m@example.com", "9900112233", "201 Banjara Hills, Hyderabad", "7890 1234 5678", "MNOPQ5678R", "Active"),
}

PRESET_ORDERS = {
    1008: [(8211, 8211, 1008, "delivered", 45.00, '[{"item": "Wireless Earbuds", "qty": 1, "price": 45.00}]')],
    1001: [
        (4821, 4821, 1001, "shipped", 129.99, '[{"item": "Mechanical Keyboard", "qty": 1, "price": 129.99}]'),
        (4822, 4822, 1001, "delivered", 24.50, '[{"item": "Laptop Sleeve", "qty": 1, "price": 24.50}]'),
    ],
    1003: [(5501, 5501, 1003, "delivered", 89.99, '[{"item": "Wireless Noise-Canceling Headphones", "qty": 1, "price": 89.99}]')],
    1042: [(9301, 9301, 1042, "processing", 299.00, '[{"item": "Noise-Cancelling Headphones", "qty": 1, "price": 299.00}]')],
}


def build_customer_record(cid: int) -> tuple[int, int, str, str, str, str, str, str, str]:
    if cid in PRESET_CUSTOMERS:
        name, email, phone, addr, aadh, pan, status = PRESET_CUSTOMERS[cid]
    else:
        fn = FIRST_NAMES[cid % len(FIRST_NAMES)]
        ln = LAST_NAMES[(cid * 7 + cid // 11) % len(LAST_NAMES)]
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{cid}@example.com"
        phone = f"98{str(cid).zfill(4)}{str((cid * 137 + 101) % 9000 + 1000)}"
        addr = f"{(cid * 17 + 3) % 350 + 1} {STREETS[cid % len(STREETS)]}, {CITIES[(cid * 3) % len(CITIES)]}"
        aadh = f"{str((cid * 1111 + 31) % 9000 + 1000)} {str((cid * 2345 + 53) % 9000 + 1000)} {str((cid * 3456 + 79) % 9000 + 1000)}"
        prefix = ["ABC", "BNZ", "CGH", "DFK", "ERT", "FGH", "GHI", "JKL", "MNP", "PRT"][(cid * 3) % 10]
        pan = f"{prefix}P{ln[0].upper()}{(cid * 73 + 17) % 9000 + 1000}{chr(65 + ((cid * 13 + 5) % 26))}"
        status = "Active"
    return (cid, cid, name, email, phone, addr, aadh, pan, status)


def build_order_records(cid: int) -> list[tuple[int, int, int, str, float, str]]:
    if cid in PRESET_ORDERS:
        return PRESET_ORDERS[cid]
    prod, price = PRODUCTS[cid % len(PRODUCTS)]
    order_id = 5000 + (cid - 1000)
    order_status = "delivered" if cid % 3 == 0 else ("shipped" if cid % 3 == 1 else "processing")
    items_json = json.dumps([{"item": prod, "qty": 1, "price": price}])
    records = [(order_id, order_id, cid, order_status, price, items_json)]
    if cid % 2 == 0:
        prod2, price2 = PRODUCTS[(cid + 3) % len(PRODUCTS)]
        order_id2 = 7000 + (cid - 1000)
        items_json2 = json.dumps([{"item": prod2, "qty": 1, "price": price2}])
        records.append((order_id2, order_id2, cid, "delivered", price2, items_json2))
    return records


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
                # Seed all customers from 1000 to 2000 inclusive
                cust_rows = [build_customer_record(cid) for cid in range(1000, 2001)]
                order_rows = []
                for cid in range(1000, 2001):
                    order_rows.extend(build_order_records(cid))

                cur.executemany("INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", cust_rows)
                cur.executemany("INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?)", order_rows)
                self._conn.commit()

    def search_by_email(self, email: str) -> Optional[dict[str, Any]]:
        clean_email = email.strip()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM customers WHERE LOWER(email) = LOWER(?)", (clean_email,))
            r = cur.fetchone()
            if not r:
                import re
                m = re.search(r"(\d{4})", clean_email)
                if m:
                    cid = int(m.group(1))
                    if 1000 <= cid <= 2000:
                        self.get_customer(cid)
                        cur.execute("SELECT * FROM customers WHERE LOWER(email) = LOWER(?)", (clean_email,))
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

    def get_customer(self, customer_id: int) -> Optional[dict[str, Any]]:
        cid = int(customer_id)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM customers WHERE display_id = ?", (cid,))
            r = cur.fetchone()
            if not r and 1000 <= cid <= 2000:
                record = build_customer_record(cid)
                cur.execute("INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", record)
                order_recs = build_order_records(cid)
                cur.executemany("INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?)", order_recs)
                self._conn.commit()
                cur.execute("SELECT * FROM customers WHERE display_id = ?", (cid,))
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
        cid = int(customer_id)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC", (cid,))
            rows = cur.fetchall()
            if not rows and 1000 <= cid <= 2000:
                order_recs = build_order_records(cid)
                cur.executemany("INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?)", order_recs)
                self._conn.commit()
                cur.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC", (cid,))
                rows = cur.fetchall()
            out = []
            for r in rows:
                item = {
                    "display_id": r["display_id"],
                    "status": r["status"],
                    "total_amount": r["total_amount"],
                }
                if "items" in r.keys() and r["items"]:
                    try:
                        item["items"] = json.loads(r["items"])
                    except Exception:
                        item["items"] = r["items"]
                out.append(item)
            return out

    def refund_order(self, order_id: int, amount: float) -> dict[str, Any]:
        return {"success": True, "order_id": order_id, "amount_refunded": amount, "status": "refunded"}

    def delete_customer(self, customer_id: int) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM customers WHERE display_id = ?", (int(customer_id),))
            self._conn.commit()
            return {"deleted": True, "customer_id": customer_id}


crm = StandaloneCRM()
