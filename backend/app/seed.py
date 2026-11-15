"""Reset local demo data. Run explicitly with python -m backend.app.seed."""

from datetime import datetime, timedelta, timezone

from backend.app import db


def seed():
    db.init_db()
    now = datetime.now(timezone.utc)
    customers = [
        ('C001', 'Rahul Sharma', '9876543210', 'rahul@example.com', 'rahul@paytm', 1200, 'active'),
        ('C002', 'Priya Verma', '9123456780', 'priya@example.com', 'priya@paytm', 3400, 'active'),
        ('C003', 'Amit Patel', '9000000003', 'amit@example.com', 'amit@paytm', 850, 'active'),
        ('C004', 'Neha Singh', '9000000004', 'neha@example.com', 'neha@paytm', 2100, 'active'),
        ('C005', 'Arjun Rao', '9000000005', 'arjun@example.com', 'arjun@paytm', 600, 'active'),
        ('C006', 'Sneha Das', '9000000006', 'sneha@example.com', 'sneha@paytm', 1750, 'active'),
        ('C007', 'Vikram Shah', '9000000007', 'vikram@example.com', 'vikram@paytm', 400, 'active'),
        ('C008', 'Ananya Iyer', '9000000008', 'ananya@example.com', 'ananya@paytm', 950, 'active'),
        ('C009', 'Rohan Mehta', '9000000009', 'rohan@example.com', 'rohan@paytm', 1250, 'frozen'),
        ('C010', 'Kavya Nair', '9000000010', 'kavya@example.com', 'kavya@paytm', 500, 'active'),
    ]
    # Fictional Paytm support scenarios; identifiers and balances are demo-only.
    transactions = [
        ('T1001', 'C001', 499, 'Electricity Board', 'UPI', 'failed_debited', (now-timedelta(days=1)).isoformat()),
        ('T1002', 'C001', 5000, 'Flight Booking', 'UPI', 'failed_debited', (now-timedelta(days=2)).isoformat()),
        ('T1003', 'C001', 250, 'Grocery', 'UPI', 'success', now.isoformat()),
        ('T2001', 'C002', 1000, 'Recharge', 'UPI', 'success', now.isoformat()),
    ]
    for txn_id, customer_id, amount, payee, kind, status, days_ago in [
        ('T3001', 'C003', 1500, 'UPI transfer to friend', 'UPI_TRANSFER', 'pending', 1),
        ('T3002', 'C003', 799, 'Merchant QR payment', 'UPI_MERCHANT', 'failed_debited', 2),
        ('T4001', 'C004', 299, 'Mobile prepaid recharge', 'MOBILE_RECHARGE', 'failed_debited', 1),
        ('T4002', 'C004', 349, 'DTH recharge', 'DTH_RECHARGE', 'pending', 0),
        ('T5001', 'C005', 1250, 'Electricity bill payment', 'ELECTRICITY_BILL', 'pending', 2),
        ('T5002', 'C005', 650, 'Water bill payment', 'WATER_BILL', 'failed_debited', 1),
        ('T6001', 'C006', 899, 'Broadband bill payment', 'BROADBAND_BILL', 'failed_debited', 1),
        ('T6002', 'C006', 750, 'Postpaid mobile bill', 'POSTPAID_BILL', 'success', 2),
        ('T7001', 'C007', 500, 'Paytm wallet merchant payment', 'WALLET_PAYMENT', 'failed_debited', 1),
        ('T7002', 'C007', 200, 'Paytm wallet merchant refund', 'WALLET_PAYMENT', 'reversed', 3),
        ('T8001', 'C008', 1000, 'Paytm gift voucher purchase', 'GIFT_VOUCHER', 'failed_debited', 1),
        ('T8002', 'C008', 500, 'Paytm gift voucher purchase', 'GIFT_VOUCHER', 'success', 2),
        ('T9001', 'C009', 300, 'Unrecognized Paytm wallet payment', 'WALLET_PAYMENT', 'success', 0),
        ('T9002', 'C009', 450, 'UPI transfer to merchant', 'UPI_TRANSFER', 'success', 1),
        ('T10001', 'C010', 2500, 'UPI transfer to family', 'UPI_TRANSFER', 'failed_debited', 2),
        ('T10002', 'C010', 199, 'Mobile prepaid recharge refund', 'MOBILE_RECHARGE', 'reversed', 3),
    ]:
        transactions.append((txn_id, customer_id, amount, payee, kind, status,
                             (now - timedelta(days=days_ago)).isoformat()))
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
    print('Reset demo database: 10 customers, 20 transactions.')
