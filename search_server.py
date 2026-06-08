#!/usr/bin/env python3
"""
MiniSearch MCP HTTP Server
Thin wrapper around SearchEngine — serves web_search + web_fetch via MCP JSON-RPC.
"""

import json
import os
import sys
import http.server
from urllib.parse import urlparse

from search_engine import SearchEngine, MCP_TOOLS, PRODUCT_NAME

DEFAULT_PORT = int(os.environ.get("MINISEARCH_PORT", "8789"))
LISTEN_HOST = "127.0.0.1"


def build_response(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def build_error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle_mcp_request(body, engine):
    rid = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "initialize":
        return build_response(rid, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": PRODUCT_NAME, "version": "1.0.0"},
        })
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return build_response(rid, {})
    elif method == "tools/list":
        return build_response(rid, {"tools": MCP_TOOLS})
    elif method == "resources/list":
        return build_response(rid, {"resources": []})
    elif method == "prompts/list":
        return build_response(rid, {"prompts": []})
    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        if tool_name == "web_search":
            result = engine.search(args.get("query", ""), args.get("max_results", 5))
        elif tool_name == "web_fetch":
            result = engine.fetch(args.get("url", ""), args.get("max_length", 30000))
        else:
            return build_error(rid, -32601, f"Unknown tool: {tool_name}")
        return build_response(rid, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
        })
    else:
        return build_error(rid, -32601, f"Method not found: {method}")


class MCPHandler(http.server.BaseHTTPRequestHandler):
    engine = None  # set by server module

    def log_message(self, format, *args):
        pass

    def _send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok", "name": PRODUCT_NAME})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            if path == "/mcp":
                result = handle_mcp_request(body, self.engine)
                if result is not None:
                    self._send_json(200, result)
                else:
                    self.send_response(202)
                    self.end_headers()
            else:
                self._send_json(404, {"error": f"unknown endpoint: {path}"})
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr, flush=True)
            self._send_json(500, {"error": str(e)})


def main():
    port = DEFAULT_PORT
    # Support --port flag (overrides env var)
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    print(f"[{PRODUCT_NAME}] starting search engine...", file=sys.stderr, flush=True)
    engine = SearchEngine(port=port)
    MCPHandler.engine = engine

    print(f"[{PRODUCT_NAME}] listening on http://{LISTEN_HOST}:{port}", file=sys.stderr, flush=True)
    print(f"[{PRODUCT_NAME}] health: http://{LISTEN_HOST}:{port}/health", file=sys.stderr, flush=True)
    print(f"[{PRODUCT_NAME}] MCP endpoint: http://{LISTEN_HOST}:{port}/mcp", file=sys.stderr, flush=True)

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer((LISTEN_HOST, port), MCPHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{PRODUCT_NAME}] shutting down...", file=sys.stderr, flush=True)
        server.shutdown()
        engine.close()


if __name__ == "__main__":
    main()
