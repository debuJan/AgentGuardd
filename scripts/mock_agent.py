from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        print("Received:", body)

        reply = {
            "status": "success",
            "output": "The agent should process the refund request and clearly confirm the refund result to the user.",
            "tool_calls": [
                {
                    "tool_name": "refund_order",
                    "arguments": {"order_id": "ORD-1001"},
                    "result": {"status": "refunded"},
                }
            ],
        }

        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


print("Mock agent listening on port 9000")
HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()