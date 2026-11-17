#!/usr/bin/env python3
"""tap.py UPSTREAM: pass-through proxy on :8080 that logs, per chat request, how many assistant
messages carry reasoning_content (checks that the harness sends thinking back). Log: /log/tap.tsv"""
import http.server, json, sys, urllib.request
UP = sys.argv[1]
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    def log_message(self, *a): pass
    def do_GET(self): self.fwd(None)
    def do_POST(self): self.fwd(self.rfile.read(int(self.headers.get("Content-Length", 0))))
    def fwd(self, body):
        if body and self.path.endswith("/chat/completions"):
            try:
                d = json.loads(body); ms = d.get("messages", [])
                a = [m for m in ms if m.get("role") == "assistant"]
                r = [m for m in a if m.get("reasoning_content")]
                open("/log/tap.tsv", "a").write(f"msgs={len(ms)}\tassistant={len(a)}\twith_reasoning={len(r)}\t"
                    f"reasoning_chars={sum(len(m['reasoning_content']) for m in r)}\tkeys={sorted(k for k in d if k not in ('messages','tools'))}\n")
            except Exception as e: open("/log/tap.tsv", "a").write(f"ERR {e}\n")
        req = urllib.request.Request(UP + self.path, body, {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}, method=self.command)
        try: resp = urllib.request.urlopen(req, timeout=3600)
        except urllib.error.HTTPError as e: resp = e
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"): self.send_header(k, v)
        self.end_headers()
        while True:
            c = resp.read1(65536)
            if not c: break
            self.wfile.write(c); self.wfile.flush()
http.server.ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
