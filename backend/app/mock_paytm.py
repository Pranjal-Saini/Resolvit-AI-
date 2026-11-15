"""Local payment operations; the gateway owns authorization."""
from uuid import uuid4
from backend.app import db


def get_customer_profile(customer_id):
    row = db.fetch_one('SELECT * FROM customers WHERE id=?', (customer_id,))
    if row is None:
        raise ValueError('customer not found')
    return row


def transaction_details(row):
    if row['status'] == 'reversed':
        row.update(credited_to='wallet', refund_status='completed',
                   refund_ref='RFND-' + row['txn_id'])
    return row


def list_recent_transactions(customer_id, limit=5):
    if not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    rows = db.fetch_all('SELECT *, id AS txn_id FROM transactions WHERE customer_id=? ORDER BY created_at DESC LIMIT ?', (customer_id, limit))
    return {'transactions': [transaction_details(row) for row in rows]}


def get_txn_status(customer_id, txn_id):
    row = db.fetch_one('SELECT *, id AS txn_id FROM transactions WHERE id=? AND customer_id=?', (txn_id, customer_id))
    if row is None:
        raise ValueError('transaction not found for customer')
    return transaction_details(row)


def get_wallet_balance(customer_id):
    row = get_customer_profile(customer_id)
    return {key: row[key] for key in ('wallet_balance', 'wallet_status')}


def trigger_reversal(customer_id, txn_id, amount):
    conn = db.get_conn()
    try:
        with conn:
            cursor = conn.execute("UPDATE transactions SET status='reversed' WHERE id=? AND customer_id=? AND status='failed_debited' AND amount=? AND ?>0", (txn_id, customer_id, amount, amount))
            if cursor.rowcount != 1:
                raise ValueError('transaction not eligible for reversal')
            conn.execute('UPDATE customers SET wallet_balance=wallet_balance+? WHERE id=?', (amount, customer_id))
    finally:
        conn.close()
    return {'txn_id': txn_id, 'status': 'reversed', 'amount': amount, 'refund_ref': 'RFND-' + txn_id, 'credited_to': 'wallet', 'refund_status': 'completed'}


def freeze_wallet_upi(customer_id, reason):
    get_customer_profile(customer_id)
    db.execute("UPDATE customers SET wallet_status='frozen' WHERE id=?", (customer_id,))
    return {'wallet_status': 'frozen', 'reason': reason}


def update_contact(customer_id, new_phone):
    import re
    if not re.fullmatch(r'[6-9]\d{9}', new_phone):
        raise ValueError('invalid Indian phone number')
    get_customer_profile(customer_id)
    db.execute('UPDATE customers SET phone=? WHERE id=?', (new_phone, customer_id))
    return {'phone': new_phone}


def schedule_followup(customer_id, txn_id, minutes):
    get_txn_status(customer_id, txn_id)
    if minutes <= 0:
        raise ValueError('minutes must be positive')
    # shortcut: acknowledgement only, add durable scheduling when a timer is required.
    return {'followup_id': 'FOLLOWUP-' + uuid4().hex}


def escalate_to_human(case_id, reason):
    db.execute("UPDATE cases SET status='escalated', summary=? WHERE id=?", (reason, case_id))
    return {'case_id': case_id, 'status': 'escalated'}


DISPATCH = {fn.__name__: fn for fn in (get_customer_profile, list_recent_transactions, get_txn_status, get_wallet_balance, trigger_reversal, freeze_wallet_upi, update_contact, schedule_followup, escalate_to_human)}
