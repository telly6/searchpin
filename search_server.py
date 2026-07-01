#!/usr/bin/env python3
"""
Searchpin MCP Server (stdio transport)
AI agent launches this as a subprocess. Reads JSON-RPC from stdin, writes to stdout.
"""

import json
import sys

from searchpin.config import DEFAULT_MODEL_NAME, PRODUCT_NAME
from searchpin.engine import MCP_TOOLS, SearchEngine


def build_response(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def build_error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle_mcp_request(body, engine):
    rid = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "initialize":
        return build_response(
            rid,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": PRODUCT_NAME, "version": "1.0.0"},
            },
        )
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
            print(
                f"[search_server] args keys={list(args.keys())!r} "
                f"topic={args.get('topic')!r} "
                f"exclude_domains={args.get('exclude_domains')!r}",
                file=sys.stderr,
                flush=True,
            )
            result = engine.search(
                args.get("query", ""),
                args.get("max_results", 10),
                args.get("freshness"),
                topic=args.get("topic"),
                exclude_domains=args.get("exclude_domains"),
                include_domains=args.get("include_domains"),
            )
        elif tool_name == "web_fetch":
            result = engine.fetch(args.get("url", ""))
        else:
            return build_error(rid, -32601, f"Unknown tool: {tool_name}")
        return build_response(
            rid,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            },
        )
    else:
        return build_error(rid, -32601, f"Method not found: {method}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Searchpin MCP Server")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Embedding model name (default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)",
    )
    args = parser.parse_args()

    print(f"[{PRODUCT_NAME}] starting engine (stdio mode)...", file=sys.stderr, flush=True)

    engine = SearchEngine(
        model_name=args.model or DEFAULT_MODEL_NAME,
        max_workers=3,
    )

    print(f"[{PRODUCT_NAME}] engine ready, waiting for requests on stdin", file=sys.stderr, flush=True)

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
