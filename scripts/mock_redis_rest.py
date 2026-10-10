"""Synthetic Redis REST emulator for protected two-instance CI only.

No real data or Redis credentials. Supports only the session protocol's GET,
SET ... EX ... NX, and DEL commands. Never logs submitted session values.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

records: dict[str, tuple[str, float]] = {}
lock = threading.RLock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Never emit the authorization header, Redis keys, or session values.
        return

    def do_POST(self):
        token = os.environ.get("KAUSHALWATCH_TEST_REDIS_TOKEN", "")
        if (not token or self.headers.get("Authorization") != "Bearer " + token
                or self.path != "/"):
            return self._reply(401, {"error": "Unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_384:
                return self._reply(413, {"error": "Invalid request size"})
            command = json.loads(self.rfile.read(length))
            if not isinstance(command, list) or not command:
                raise ValueError("Invalid command")
            name = command[0]
            with lock:
                now = time.monotonic()
                if name == "SET" and len(command) == 6 and command[3:] == ["EX", 1800, "NX"]:
                    _, key, value, *_ = command
                    if not isinstance(key, str) or not isinstance(value, str):
                        raise ValueError("Invalid SET args")
                    old = records.get(key)
                    if old and old[1] > now:
                        result = None
                    else:
                        records[key] = (value, now + 1800)
                        result = "OK"
                elif name == "GET" and len(command) == 2:
                    old = records.get(command[1])
                    result = old[0] if old and old[1] > now else None
                    if old and old[1] <= now:
                        records.pop(command[1], None)
                elif name == "DEL" and len(command) == 2:
                    result = int(records.pop(command[1], None) is not None)
                else:
                    raise ValueError("Unsupported command")
            return self._reply(200, {"result": result})
        except (TypeError, ValueError, json.JSONDecodeError, KeyError):
            return self._reply(400, {"error": "Invalid synthetic command"})

    def _reply(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6399)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("Synthetic emulator must stay on loopback")
    if len(os.environ.get("KAUSHALWATCH_TEST_REDIS_TOKEN", "")) < 32:
        parser.error("Missing synthetic test Redis token")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
