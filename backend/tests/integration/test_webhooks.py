
# tests/integration/test_webhooks.py
from __future__ import annotations
import httpx
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


def test_webhook_delivery(monkeypatch):
    from workers.webhook_worker import trigger_webhook, webhook_app
    webhook_app.conf.task_always_eager = True

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        res = trigger_webhook.apply_async(kwargs={"url": f"http://127.0.0.1:{port}", "event": "test", "payload": {}}).get()
        assert res["status"] == 200
    finally:
        server.shutdown()
