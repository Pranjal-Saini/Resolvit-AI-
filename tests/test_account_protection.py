"""Account protection and ownership checks against an isolated SQLite file."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from backend.app import db, gateway, mock_paytm, seed
from shared.contracts import CallContext, ToolCall


class AccountProtectionTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database_path = Path(directory) / "protection.sqlite3"
        self.enterContext(patch.object(db, "DB_PATH", self.database_path))
        seed.seed()
        self.contexts = {}
        for customer_id in ("C001", "C002"):
            session_id = "session-" + customer_id
            case_id = "case-" + customer_id
            db.execute("INSERT INTO sessions (id, customer_id) VALUES (?,?)", (session_id, customer_id))
            db.execute(
                "INSERT INTO cases (id, session_id, customer_id, status, created_at) VALUES (?,?,?,?,?)",
                (case_id, session_id, customer_id, "open", "2026-01-01T00:00:00+00:00"),
            )
            self.contexts[customer_id] = CallContext(
                case_id=case_id, session_id=session_id, customer_id=customer_id, verified=True,
            )

    def rows(self, sql, params=()):
        # A fresh independent connection verifies that writes were committed.
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params)]

    def test_freeze_persists_without_changing_balances_or_transactions(self):
        customers_before = self.rows("SELECT * FROM customers ORDER BY id")
        transactions_before = self.rows("SELECT * FROM transactions ORDER BY id")
        result = gateway.execute(
            ToolCall(name="freeze_wallet_upi", args={"reason": "Account compromised"}),
            self.contexts["C002"],
        )
        self.assertEqual(result.status, "ok", result.reason)
        expected = [dict(row) for row in customers_before]
        expected[1]["wallet_status"] = "frozen"
        self.assertEqual(self.rows("SELECT * FROM customers ORDER BY id"), expected)
        self.assertEqual(self.rows("SELECT * FROM transactions ORDER BY id"), transactions_before)
        self.assertEqual(result.data["wallet_status"], "frozen")

    def test_escalation_persists_case_status_and_reason(self):
        other_case = self.rows("SELECT * FROM cases WHERE customer_id='C001'")
        result = gateway.execute(
            ToolCall(name="escalate_to_human", args={"reason": "Account compromised"}),
            self.contexts["C002"],
        )
        self.assertEqual(result.status, "ok", result.reason)
        self.assertEqual(
            self.rows("SELECT status, summary FROM cases WHERE id=?", (self.contexts["C002"].case_id,)),
            [{"status": "escalated", "summary": "Account compromised"}],
        )
        self.assertEqual(self.rows("SELECT * FROM cases WHERE customer_id='C001'"), other_case)

    def test_cross_customer_transaction_attempts_are_blocked_and_audited(self):
        customers_before = self.rows("SELECT * FROM customers ORDER BY id")
        transactions_before = self.rows("SELECT * FROM transactions ORDER BY id")
        cases_before = self.rows("SELECT * FROM cases ORDER BY id")
        calls = (
            ToolCall(name="get_txn_status", args={"txn_id": "T2001"}),
            ToolCall(name="trigger_reversal", args={"txn_id": "T2001", "amount": 1000},
                     policy_ref="Test policy permitting failed-payment reversal"),
            ToolCall(name="schedule_followup", args={"txn_id": "T2001", "minutes": 30}),
        )
        for call in calls:
            with self.subTest(tool=call.name):
                dispatch = Mock(wraps=mock_paytm.DISPATCH[call.name])
                with patch.dict(mock_paytm.DISPATCH, {call.name: dispatch}):
                    result = gateway.execute(call, self.contexts["C001"])
                self.assertEqual(result.status, "blocked", result.reason)
                self.assertEqual(result.reason, "transaction not found for customer")
                self.assertEqual(result.data, {})
                self.assertIsNone(result.approval_id)
                dispatch.assert_not_called()
                audit = self.rows("SELECT * FROM audit_log WHERE id=?", (result.audit_id,))
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0]["case_id"], self.contexts["C001"].case_id)
                self.assertEqual(audit[0]["tool"], call.name)
                self.assertEqual(audit[0]["decision"], "blocked")
                self.assertEqual(audit[0]["reason"], result.reason)
                self.assertEqual(json.loads(audit[0]["args_masked_json"]), call.args)
                self.assertEqual(json.loads(audit[0]["result_json"])["status"], "blocked")
        self.assertEqual(len(self.rows("SELECT * FROM audit_log")), len(calls))
        self.assertEqual(self.rows("SELECT * FROM approvals"), [])
        self.assertEqual(self.rows("SELECT * FROM customers ORDER BY id"), customers_before)
        self.assertEqual(self.rows("SELECT * FROM transactions ORDER BY id"), transactions_before)
        self.assertEqual(self.rows("SELECT * FROM cases ORDER BY id"), cases_before)


if __name__ == "__main__":
    unittest.main()
