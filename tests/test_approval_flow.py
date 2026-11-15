"""Real gateway and approval API regression check using an isolated SQLite file."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import db, gateway, seed
from backend.app.main import app
from shared.contracts import CallContext, ToolCall


class ApprovalFlowTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(db, "DB_PATH", Path(directory) / "approval.sqlite3"))
        seed.seed()
        self.client = self.enterContext(TestClient(app))
        self.enterContext(patch.dict('os.environ',{'REVIEWER_USERNAME':'approval-test-reviewer','REVIEWER_PASSWORD':'test-password'}))
        self.client.post('/review/login',json={'username':'approval-test-reviewer','password':'test-password'})
        self.ctx = CallContext(
            case_id="CASE-0001", session_id="approval-test", customer_id="C001"
        )
        db.execute("INSERT INTO sessions(id,customer_id,current_case_id) VALUES(?,?,?)",
                   (self.ctx.session_id, self.ctx.customer_id, self.ctx.case_id))
        db.execute(
            "INSERT INTO cases(id,session_id,customer_id,status,created_at) "
            "VALUES(?,?,?,'open',?)",
            (self.ctx.case_id, self.ctx.session_id, self.ctx.customer_id, gateway.now()),
        )

    def test_5000_reversal_requires_approval_and_credits_once(self):
        transaction = db.fetch_one("SELECT * FROM transactions WHERE id='T1002'")
        customer = db.fetch_one("SELECT * FROM customers WHERE id='C001'")
        self.assertEqual(transaction["status"], "failed_debited")
        self.assertEqual(transaction["amount"], 5000)
        self.assertEqual(customer["wallet_balance"], 1200)
        policy_ref = "resolveai_operations.md#Auto-reversal limit"
        args = {"txn_id": "T1002", "amount": 5000}

        result = gateway.execute(
            ToolCall(name="trigger_reversal", args=args, policy_ref=policy_ref), self.ctx
        )
        self.assertEqual(result.status, "needs_approval", "backend/app/gateway.py")
        self.assertIsNotNone(result.approval_id)
        approval = db.fetch_one("SELECT * FROM approvals WHERE id=?", (result.approval_id,))
        self.assertEqual(approval["status"], "pending")
        self.assertEqual(approval["case_id"], self.ctx.case_id)
        self.assertEqual(approval["tool"], "trigger_reversal")
        self.assertEqual(json.loads(approval["args_json"]), args)
        self.assertEqual(approval["policy_ref"], policy_ref)
        self.assertEqual(db.fetch_one("SELECT * FROM transactions WHERE id='T1002'"), transaction)
        self.assertEqual(db.fetch_one("SELECT * FROM customers WHERE id='C001'"), customer)
        self.assertEqual(db.fetch_one("SELECT status FROM cases WHERE id=?", (self.ctx.case_id,)),
                         {"status": "awaiting_approval"})
        requested = db.fetch_one("SELECT * FROM audit_log WHERE id=?", (result.audit_id,))
        self.assertEqual(requested["decision"], "needs_approval")
        self.assertEqual(json.loads(requested["result_json"])["approval_id"], result.approval_id)

        path = f"/cases/{self.ctx.case_id}/approve"
        response = self.client.post(path, json={"reviewer": "approval-test-reviewer"})
        self.assertEqual(response.status_code, 200, "backend/app/main.py: " + response.text)
        body = response.json()
        self.assertEqual(body["case_id"], self.ctx.case_id)
        self.assertEqual(body["status"], "resolved")
        self.assertEqual(body["result"]["status"], "ok", "backend/app/gateway.py: " + response.text)
        self.assertEqual(body["result"]["data"]["amount"], 5000)
        self.assertEqual(body["result"]["data"]["refund_ref"], "RFND-T1002")
        self.assertEqual(db.fetch_one("SELECT status FROM transactions WHERE id='T1002'"),
                         {"status": "reversed"}, "backend/app/mock_paytm.py")
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'"),
                         {"wallet_balance": customer["wallet_balance"] + 5000},
                         "backend/app/mock_paytm.py")
        case = db.fetch_one("SELECT * FROM cases WHERE id=?", (self.ctx.case_id,))
        self.assertEqual(case["status"], "resolved")
        self.assertEqual(case["resolution_type"], "human_approved", "backend/app/main.py")
        self.assertIsNotNone(case["resolved_at"])
        approved = db.fetch_one("SELECT * FROM approvals WHERE id=?", (result.approval_id,))
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["reviewer"], "approval-test-reviewer")

        for _ in range(2):
            repeated = self.client.post(path, json={"reviewer": "approval-test-reviewer"})
            self.assertEqual(repeated.status_code, 409, "backend/app/main.py: " + repeated.text)
            self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'"),
                             {"wallet_balance": customer["wallet_balance"] + 5000})
            self.assertEqual(db.fetch_one("SELECT status FROM transactions WHERE id='T1002'"),
                             {"status": "reversed"})

        response = self.client.get("/audit", params={"case_id": self.ctx.case_id})
        self.assertEqual(response.status_code, 200)
        records = sorted(response.json(), key=lambda row: row["id"])
        self.assertEqual([row["decision"] for row in records], ["needs_approval", "executed"])
        self.assertEqual([row["actor"] for row in records], ["agent", "approval-test-reviewer"])
        self.assertEqual(records[1]["id"], body["result"]["audit_id"])
        self.assertEqual(json.loads(records[1]["result_json"])["data"]["amount"], 5000)
        self.assertEqual(records[0]["idempotency_key"], records[1]["idempotency_key"])
        for row in records:
            self.assertEqual(row["case_id"], self.ctx.case_id)
            self.assertEqual(row["tool"], "trigger_reversal")
            self.assertEqual(row["tier"], "money_moving")
            self.assertEqual(row["policy_ref"], policy_ref)
            self.assertEqual(json.loads(row["args_masked_json"]), args)
            self.assertTrue(row["ts"])


if __name__ == "__main__":
    unittest.main()
