#!/usr/bin/env python3
"""
MiniSearch MCP Server (stdio transport)
AI agent launches this as a subprocess. Reads JSON-RPC from stdin, writes to stdout.
Config loaded from ~/.minisearch/config.json
"""

import json
import os
import sys

from search_engine import SearchEngine, MCP_TOOLS, PRODUCT_NAME, DEFAULT_MODEL_NAME

CONFIG_DIR = os.path.expanduser("~/.minisearch")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


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


def main():
    cfg = load_config()

    model_name = cfg.get("model_name", DEFAULT_MODEL_NAME)
    max_workers = cfg.get("max_workers", 3)
    embedding_mode = cfg.get("embedding_mode", "local")
    api_endpoint = cfg.get("api_endpoint", "")
    api_key = cfg.get("api_key", "")
    api_model = cfg.get("api_model", "")

    print(f"[{PRODUCT_NAME}] starting engine (stdio mode)...",
          file=sys.stderr, flush=True)

    engine = SearchEngine(
        model_name=model_name,
        max_workers=max_workers,
        embedding_mode=embedding_mode,
        api_endpoint=api_endpoint or None,
        api_key=api_key or None,
        api_model=api_model or None,
    )

    print(f"[{PRODUCT_NAME}] engine ready, waiting for requests on stdin",
          file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            body = json.loads(line)
            result = handle_mcp_request(body, engine)
            if result is not None:
                sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            err = build_error(None, -32700, f"Parse error: {e}")
            sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:
            print(f"[{PRODUCT_NAME}] error: {e}", file=sys.stderr, flush=True)
            err = build_error(None, -32603, str(e))
            sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    engine.close()


if __name__ == "__main__":
    main()
