"""Check the first backend milestone without resetting the demo database."""

import socket
import tempfile
import threading
import time
from pathlib import Path

import requests
import uvicorn

from backend.app import db, seed
from backend.app.main import app
from shared.contracts import ChatRequest, ToolCall


def main():
    original_path = db.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as directory:
            db.DB_PATH = Path(directory) / 'check.db'
            seed.seed()
            assert len(db.fetch_all('SELECT * FROM transactions')) == 20
            db.execute("UPDATE customers SET wallet_balance=1300 WHERE id='C001'")
            db.init_db()
            assert db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'] == 1300
            seed.seed()
            assert db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'] == 1200
            assert ToolCall(name='get_customer_profile').args == {}
            ChatRequest(session_id='s1', customer_id='C001', token='demo-C001', message='Hello')

            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                base = f'http://127.0.0.1:{sock.getsockname()[1]}'
                server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
                thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() > deadline:
                            raise RuntimeError('Test server did not start')
                        time.sleep(0.05)
                    response = requests.get(base + '/health', timeout=5)
                    assert response.status_code == 200
                    assert response.json() == {'ok': True}
                    response = requests.get(base + '/customers', timeout=5)
                    assert response.status_code == 200
                    assert response.json() == db.fetch_all('SELECT id, name FROM customers ORDER BY id')
                    assert len(response.json()) == 10
                    assert requests.get(base + '/docs', timeout=5).status_code == 200
                    print('PASS: database reset, startup preservation, contracts, /health, /customers, /docs')
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    if thread.is_alive():
                        raise RuntimeError('Test server did not stop')
    finally:
        db.DB_PATH = original_path


if __name__ == '__main__':
    main()
