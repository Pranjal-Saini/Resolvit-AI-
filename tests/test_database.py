"""Database contract tests; every write is confined to a temporary SQLite file."""

import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.app import db, seed


REQUIRED_COLUMNS = {
    "customers": "id name phone email upi_id wallet_balance wallet_status",
    "transactions": "id customer_id amount payee type status created_at",
    "sessions": "id customer_id history_json pii_map_json current_case_id",
    "cases": "id session_id customer_id status summary resolution_type created_at resolved_at",
    "approvals": "id case_id tool args_json policy_ref status reviewer note created_at",
    "audit_log": "id ts case_id actor tool tier args_masked_json decision reason result_json policy_ref idempotency_key",
}

EXPECTED_CUSTOMERS = [
    dict(id="C001", name="Rahul Sharma", phone="9876543210", email="rahul@example.com",
         upi_id="rahul@paytm", wallet_balance=1200, wallet_status="active"),
    dict(id="C002", name="Priya Verma", phone="9123456780", email="priya@example.com",
         upi_id="priya@paytm", wallet_balance=3400, wallet_status="active"),
]

EXPECTED_TRANSACTIONS = [
    dict(id="T1001", customer_id="C001", amount=499, payee="Electricity Board", status="failed_debited"),
    dict(id="T1002", customer_id="C001", amount=5000, payee="Flight Booking", status="failed_debited"),
    dict(id="T1003", customer_id="C001", amount=250, payee="Grocery", status="success"),
    dict(id="T2001", customer_id="C002", amount=1000, payee="Recharge", status="success"),
]


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database_path = Path(directory) / "test.sqlite3"
        self.enterContext(patch.object(db, "DB_PATH", self.database_path))
        db.init_db()

    def test_required_tables_and_columns(self):
        # Inspect independently of the helpers under test.
        with closing(sqlite3.connect(self.database_path)) as conn, conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertTrue(REQUIRED_COLUMNS.keys() <= tables)
            for table, columns in REQUIRED_COLUMNS.items():
                with self.subTest(table=table):
                    info = list(conn.execute(f"PRAGMA table_info({table})"))
                    self.assertTrue(set(columns.split()) <= {row[1] for row in info})
                    self.assertEqual([row[1] for row in info if row[5]], ["id"])

    def test_initialization_preserves_existing_data(self):
        seed.seed()
        with closing(sqlite3.connect(self.database_path)) as conn, conn:
            conn.execute("UPDATE customers SET wallet_balance=123, wallet_status='frozen' WHERE id='C001'")
            before = list(conn.iterdump())
        db.init_db()
        db.init_db()
        with closing(sqlite3.connect(self.database_path)) as conn, conn:
            self.assertEqual(list(conn.iterdump()), before)

    def test_fetch_and_execute_helpers(self):
        self.assertIsNone(db.fetch_one("SELECT * FROM customers WHERE id=?", ("missing",)))
        self.assertEqual(db.fetch_all("SELECT * FROM customers"), [])
        customer = ("C-test", "O'Brien", "123", "test@example.com", "test@upi", 10, "active")
        db.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?)", customer)
        row = db.fetch_one("SELECT name, wallet_balance FROM customers WHERE id=?", ("C-test",))
        self.assertEqual(row, {"name": "O'Brien", "wallet_balance": 10})
        self.assertIsInstance(row, dict)
        db.execute("UPDATE customers SET wallet_balance=? WHERE id=?", (25, "C-test"))
        with closing(sqlite3.connect(self.database_path)) as conn, conn:
            self.assertEqual(conn.execute("SELECT wallet_balance FROM customers").fetchone()[0], 25)
        self.assertEqual(db.fetch_all("SELECT id FROM customers ORDER BY id"), [{"id": "C-test"}])
        self.assertIsNone(db.fetch_one("SELECT id FROM customers WHERE id=?", ("' OR 1=1 --",)))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("UPDATE customers SET wallet_balance=-1 WHERE id=?", ("C-test",))
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers"), {"wallet_balance": 25})
        db.execute("DELETE FROM customers WHERE id=?", ("C-test",))
        self.assertEqual(db.fetch_all("SELECT * FROM customers"), [])

    def test_seed_records_match_spec(self):
        before = datetime.now(timezone.utc)
        seed.seed()
        after = datetime.now(timezone.utc)
        self.assertEqual(db.fetch_all("SELECT * FROM customers WHERE id IN ('C001','C002') ORDER BY id"), EXPECTED_CUSTOMERS)
        transactions = db.fetch_all("SELECT * FROM transactions WHERE id IN ('T1001','T1002','T1003','T2001') ORDER BY id")
        self.assertEqual(
            [{key: row[key] for key in expected} for row, expected in zip(transactions, EXPECTED_TRANSACTIONS)],
            EXPECTED_TRANSACTIONS,
        )
        self.assertEqual(len(transactions), 4)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) AS n FROM customers")["n"], 10)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) AS n FROM transactions")["n"], 20)
        self.assertEqual(db.fetch_all("PRAGMA foreign_key_check"), [])
        self.assertEqual(db.fetch_all("SELECT c.id FROM customers c LEFT JOIN transactions t ON t.customer_id=c.id GROUP BY c.id HAVING COUNT(t.id)=0"), [])
        kinds = {r["type"] for r in db.fetch_all("SELECT DISTINCT type FROM transactions")}
        self.assertTrue({"UPI_TRANSFER", "MOBILE_RECHARGE", "ELECTRICITY_BILL", "WALLET_PAYMENT", "GIFT_VOUCHER"} <= kinds)
        self.assertEqual({r["status"] for r in db.fetch_all("SELECT DISTINCT status FROM transactions")},
                         {"success", "pending", "failed_debited", "reversed"})
        for row, days_ago in zip(transactions, (1, 2, 0, 0)):
            with self.subTest(transaction=row["id"]):
                timestamp = datetime.fromisoformat(row["created_at"])
                self.assertIsNotNone(timestamp.tzinfo)
                self.assertLessEqual(before - timedelta(days=days_ago), timestamp)
                self.assertLessEqual(timestamp, after - timedelta(days=days_ago))

    def test_seed_reset_restores_records_without_duplicates(self):
        seed.seed()
        db.execute("UPDATE customers SET wallet_balance=0, wallet_status='frozen' WHERE id='C001'")
        db.execute("UPDATE transactions SET status='reversed' WHERE id='T1001'")
        db.execute("INSERT INTO sessions (id, customer_id) VALUES (?,?)", ("session-test", "C001"))
        db.execute(
            "INSERT INTO cases (id, session_id, customer_id, status, created_at) VALUES (?,?,?,?,?)",
            ("CASE-0001", "session-test", "C001", "open", "2026-01-01"),
        )
        approval_id = db.execute(
            "INSERT INTO approvals (case_id, tool, args_json, status, created_at) VALUES (?,?,?,?,?)",
            ("CASE-0001", "reverse_payment", "{}", "pending", "2026-01-01"),
        )
        self.assertEqual(db.fetch_one("SELECT id FROM approvals"), {"id": approval_id})
        db.execute(
            "INSERT INTO audit_log (ts, case_id, actor, tool, tier, args_masked_json, decision) "
            "VALUES (?,?,?,?,?,?,?)",
            ("2026-01-01", "CASE-0001", "test", "reverse_payment", "financial", "{}", "blocked"),
        )
        for reset in range(2):
            with self.subTest(reset=reset):
                seed.seed()
                self.assertEqual(db.fetch_one("SELECT COUNT(*) AS n FROM customers")["n"], 10)
                self.assertEqual(db.fetch_one("SELECT COUNT(*) AS n FROM transactions")["n"], 20)
                self.assertEqual(db.fetch_all("SELECT * FROM customers WHERE id IN ('C001','C002') ORDER BY id"), EXPECTED_CUSTOMERS)
                self.assertEqual(
                    db.fetch_all("SELECT id, customer_id, amount, payee, status FROM transactions WHERE id IN ('T1001','T1002','T1003','T2001') ORDER BY id"),
                    EXPECTED_TRANSACTIONS,
                )
                for table in ("sessions", "cases", "approvals", "audit_log"):
                    self.assertEqual(db.fetch_all(f"SELECT * FROM {table}"), [], table)


if __name__ == "__main__":
    unittest.main()
