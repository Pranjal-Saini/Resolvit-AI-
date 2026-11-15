"""Reset local demo data. Run explicitly with python -m backend.app.seed."""

from datetime import datetime, timedelta, timezone

from backend.app import db


def seed():
    db.init_db()
    now = datetime.now(timezone.utc)
    customers = [
        ('C001', 'Rahul Sharma', '9876543210', 'rahul@example.com', 'rahul@paytm', 1200, 'active'),
        ('C002', 'Priya Verma', '9123456780', 'priya@example.com', 'priya@paytm', 3400, 'active'),
    ]
    transactions = [
        ('T1001', 'C001', 499, 'Electricity Board', 'UPI', 'failed_debited', (now-timedelta(days=1)).isoformat()),
        ('T1002', 'C001', 5000, 'Flight Booking', 'UPI', 'failed_debited', (now-timedelta(days=2)).isoformat()),
        ('T1003', 'C001', 250, 'Grocery', 'UPI', 'success', now.isoformat()),
        ('T2001', 'C002', 1000, 'Recharge', 'UPI', 'success', now.isoformat()),
    ]
    conn = db.get_conn()
    try:
        with conn:
            for table in ('audit_log', 'approvals', 'cases', 'sessions', 'transactions', 'customers'):
                conn.execute('DELETE FROM ' + table)
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('approvals','audit_log')")
            conn.executemany('INSERT INTO customers VALUES (?,?,?,?,?,?,?)', customers)
            conn.executemany('INSERT INTO transactions VALUES (?,?,?,?,?,?,?)', transactions)
    finally:
        conn.close()


if __name__ == '__main__':
    seed()
    print('Reset demo database: 2 customers, 4 transactions.')
