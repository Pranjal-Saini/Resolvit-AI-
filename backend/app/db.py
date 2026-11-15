"""SQLite storage shared by the backend modules."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "resolveai.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
    email TEXT NOT NULL, upi_id TEXT NOT NULL,
    wallet_balance REAL NOT NULL CHECK(wallet_balance >= 0),
    wallet_status TEXT NOT NULL CHECK(wallet_status IN ('active', 'frozen'))
);
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
    amount REAL NOT NULL CHECK(amount > 0), payee TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success','failed_debited','reversed','pending')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
    history_json TEXT NOT NULL DEFAULT '[]', pii_map_json TEXT NOT NULL DEFAULT '{}',
    current_case_id TEXT
);
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
    customer_id TEXT NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL CHECK(status IN ('open','need_info','resolved','awaiting_approval','escalated','rejected')),
    summary TEXT, resolution_type TEXT, created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id),
    tool TEXT NOT NULL, args_json TEXT NOT NULL, policy_ref TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
    reviewer TEXT, note TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS step_up_verifications (
    case_id TEXT PRIMARY KEY REFERENCES cases(id), verified_by TEXT NOT NULL, verified_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
    case_id TEXT NOT NULL REFERENCES cases(id), actor TEXT NOT NULL,
    tool TEXT NOT NULL, tier TEXT NOT NULL, args_masked_json TEXT NOT NULL,
    decision TEXT NOT NULL, reason TEXT, result_json TEXT,
    policy_ref TEXT, idempotency_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_approvals_case ON approvals(case_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_idempotency ON audit_log(idempotency_key);
"""


def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    try:
        with conn:
            conn.executescript(SCHEMA)
    finally:
        conn.close()


def fetch_one(sql, params=()):
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def fetch_all(sql, params=()):
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid
    finally:
        conn.close()
