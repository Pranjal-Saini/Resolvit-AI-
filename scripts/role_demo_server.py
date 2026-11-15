"""Run a dedicated, persistent local role demo without resetting the working database.

RESOLVEAI_DEMO_DB can select a different dedicated file. A new file gets two
illustrative gateway-backed cases; an existing file is preserved on restart.
"""
import os
import tempfile
from pathlib import Path

import uvicorn
from backend.app import db, gateway, seed
from backend.app.main import app, append_message
from shared.contracts import CallContext, ToolCall


def prepare_examples():
    for case_id, session_id, customer_id in [
        ('CASE-DEMO-SUPPORT', 'role-demo-support', 'C002'),
        ('CASE-DEMO-REVIEW', 'role-demo-review', 'C001'),
    ]:
        db.execute('INSERT INTO sessions(id,customer_id,current_case_id) VALUES(?,?,?)', (session_id,customer_id,case_id))
        db.execute("INSERT INTO cases(id,session_id,customer_id,status,created_at) VALUES(?,?,?,'open',?)", (case_id,session_id,customer_id,gateway.now()))
    support = CallContext(case_id='CASE-DEMO-SUPPORT', session_id='role-demo-support', customer_id='C002')
    append_message(support.session_id, 'user', 'Someone accessed my account. Please protect my wallet and help me investigate.', support.case_id)
    gateway.execute(ToolCall(name='freeze_wallet_upi', args={'reason':'Demo account compromise'}), support)
    gateway.execute(ToolCall(name='escalate_to_human', args={'reason':'Investigate the reported account compromise; mock wallet frozen.'}), support)
    append_message(support.session_id, 'assistant', 'Your mock wallet has been frozen. A support specialist will help investigate.', support.case_id)
    db.execute('UPDATE cases SET summary=? WHERE id=?', ('Account compromise reported. Mock wallet frozen; human investigation required.',support.case_id))
    review = CallContext(case_id='CASE-DEMO-REVIEW', session_id='role-demo-review', customer_id='C001')
    append_message(review.session_id, 'user', 'My ₹5,000 flight payment failed after debit. Can you reverse it?', review.case_id)
    gateway.execute(ToolCall(name='trigger_reversal',args={'txn_id':'T1002','amount':5000},policy_ref='resolveai_operations.md#Auto-reversal limit'),review)
    append_message(review.session_id, 'assistant', 'Your request needs specialist approval. No refund has been processed yet.', review.case_id)
    db.execute('UPDATE cases SET summary=? WHERE id=?', ('Failed ₹5,000 flight payment. Above the ₹2,000 demo automatic-reversal cap.',review.case_id))


def main():
    db.DB_PATH = Path(os.getenv('RESOLVEAI_DEMO_DB', str(Path(tempfile.gettempdir())/'resolveai-role-demo.db')))
    fresh = not db.DB_PATH.exists()
    db.init_db()
    if fresh:
        seed.seed()
        prepare_examples()
    print('Role demo: http://127.0.0.1:8010 · existing demo activity is preserved on restart.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8010,log_level='warning')


if __name__ == '__main__':
    main()
