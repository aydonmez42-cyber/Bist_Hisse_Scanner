import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            "TEST 16 is online.\n"
            "Backtest: python backtest.py\n"
            "LONG: ETHUSDT | SHORT: ETHUSDC | Fixed size: 1 ETH\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"TEST 16 web service listening on port {PORT}", flush=True)
    server.serve_forever()
