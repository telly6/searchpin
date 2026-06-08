#!/usr/bin/env python3
"""
Claude Code → DeepSeek API Proxy
Translates Anthropic Messages API to DeepSeek Chat Completions API.
Includes built-in DNS-over-HTTPS resolver (no system DNS needed).
"""

import http.server
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from html import unescape

# ── Import search engine ──
from search_engine import SearchEngine, MCP_TOOLS
_search_engine = None  # lazy init

# ── Config ──────────────────────────────────────────────────
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8788
DEEPSEEK_HOST = "api.deepseek.com"
DEEPSEEK_PATH = "/v1/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

# DNS-over-HTTPS endpoints (tried in order)
DOH_ENDPOINTS = [
    ("https://dns.google/resolve", "8.8.8.8"),
    ("https://cloudflare-dns.com/dns-query", "1.1.1.1"),
    ("https://dns.quad9.net/dns-query", "9.9.9.9"),
]

# ── API Key ─────────────────────────────────────────────────
def read_api_key():
    key_path = Path.home() / ".deepseek-key"
    if not key_path.exists():
        print(f"\033[31m❌  {key_path} not found!\033[0m")
        print(f"   Run: echo \"sk-your-key\" > {key_path}")
        sys.exit(1)
    key = key_path.read_text().strip()
    if not key or key == "sk-your-key":
        print(f"\033[31m❌  Please put your real DeepSeek API key in {key_path}\033[0m")
        sys.exit(1)
    return key

API_KEY = read_api_key()

# ── DNS Resolution ──────────────────────────────────────────
_dns_cache = {}
_dns_cache_lock = threading.Lock()

def resolve_host(host):
    """Resolve hostname to IP using DoH, with cache."""
    with _dns_cache_lock:
        if host in _dns_cache:
            return _dns_cache[host]

    # Try system resolver first
    try:
        addr = socket.getaddrinfo(host, 443)[0][4][0]
        with _dns_cache_lock:
            _dns_cache[host] = addr
        print(f"[DNS] system resolver: {host} → {addr}")
        return addr
    except Exception:
        pass

    # Fall back to DoH
    for doh_url, doh_ip in DOH_ENDPOINTS:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Build request with custom Host header
            parsed = urlparse(doh_url)
            doh_host = parsed.netloc

            # We need resolve the DoH endpoint itself via IP bypass
            conn = http.client.HTTPSConnection(
                doh_ip, timeout=2, context=ctx
            )
            query = f"{doh_url}?name={host}&type=A"
            conn.request("GET", parsed.path + f"?name={host}&type=A",
                         headers={"Host": doh_host, "Accept": "application/dns-json"})
            resp = conn.getresponse()
            if resp.status == 200:
                data = json.loads(resp.read())
                for ans in data.get("Answer", []):
                    if ans.get("type") == 1:  # A record
                        addr = ans["data"]
                        with _dns_cache_lock:
                            _dns_cache[host] = addr
                        print(f"[DNS] {host} → {addr} (via {doh_host})")
                        return addr
            conn.close()
        except Exception as e:
            print(f"[DNS] DoH {doh_host} failed: {e}")
            continue

    raise Exception(f"Cannot resolve {host} via any method")

# ── Request Translation ─────────────────────────────────────
TOOL_CONSTRAINT = (
    "\n\n## CRITICAL: Tool Usage Rules\n"
    "- DEFAULT: Answer with text ONLY. Do NOT use file/command tools unless the user explicitly requests an action.\n"
    "- EXCEPTION: web_search is always available for real-time or factual queries (pricing, dates, news, events). Use it proactively when the user asks a question that requires up-to-date information.\n"
    "- For conversational questions (\"who are you\", \"what model\", \"how to use X\"), answer directly with text.\n"
    "- If you are unsure whether to use a tool, DO NOT use it.\n"
    "\n"
    "## Web Search Rules\n"
    "- web_search returns real-time, live results from Bing. Review ALL results carefully before answering. Different results may contradict — identify the most recent and authoritative ones.\n"
    "- Use keyword queries: user asks \"豆包什么时候开始收费\" → web_search(\"豆包 收费 付费 会员 价格\").\n"
    "- web_fetch reads a specific URL found by web_search, for detailed information.\n"
    "- If web_search returns no useful results after 2 attempts with different queries, state what you found and what you could not confirm — do NOT silently make up answers."
)

def anthropic_to_deepseek(anthropic_body):
    """Convert Anthropic Messages request to DeepSeek Chat Completions request."""
    messages = []
    tools = None

    # System prompt
    system = anthropic_body.get("system")
    if system:
        if isinstance(system, list):
            # System can be a list of text blocks in Anthropic
            system_text = "".join(
                b.get("text", "") for b in system if b.get("type") == "text"
            )
            system_text += TOOL_CONSTRAINT
            messages.append({"role": "system", "content": system_text})
        else:
            messages.append({"role": "system", "content": system + TOOL_CONSTRAINT})
    else:
        messages.append({"role": "system", "content": TOOL_CONSTRAINT.strip()})

    # Convert Anthropic tools to OpenAI format.
    # Always pass available tools — the system prompt's TOOL_CONSTRAINT
    # instructs the model to answer with text by default, only using tools
    # when explicitly asked.
    anthropic_tools = anthropic_body.get("tools")

    if anthropic_tools:
        tools = []
        for tool in anthropic_tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                }
            })

    # Convert messages
    for msg in anthropic_body.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            # Multi-block content
            openai_content = None
            tool_calls = []
            tool_call_id_counter = 0

            for block in content:
                block_type = block.get("type")

                if block_type == "text":
                    if openai_content is None:
                        openai_content = block.get("text", "")
                    else:
                        openai_content += block.get("text", "")

                elif block_type == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", f"call_{tool_call_id_counter}"),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {})),
                        }
                    })
                    tool_call_id_counter += 1

                elif block_type == "tool_result":
                    # Anthropic tool_result → OpenAI tool message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", "unknown"),
                        "content": block.get("content", ""),
                    })
                    continue

                elif block_type == "image":
                    # Anthropic image → OpenAI image_url
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        media_type = source.get("media_type", "image/jpeg")
                        data = source.get("data", "")
                        openai_content = [{"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}}]
                        continue

            if role == "assistant" and tool_calls:
                messages.append({"role": "assistant", "tool_calls": tool_calls,
                                 "content": openai_content or None})
            elif openai_content is not None:
                messages.append({"role": role, "content": openai_content})

    deepseek_body = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": anthropic_body.get("stream", False),
    }

    if tools:
        deepseek_body["tools"] = tools
        # Only include tool_choice if tools are present
        tool_choice = anthropic_body.get("tool_choice")
        if tool_choice:
            if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
                deepseek_body["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_choice.get("name", "")}
                }
            elif tool_choice == "any":
                deepseek_body["tool_choice"] = "auto"
            elif tool_choice == "auto":
                deepseek_body["tool_choice"] = "auto"

    max_tokens = anthropic_body.get("max_tokens", 4096)
    deepseek_body["max_tokens"] = min(max_tokens, 8192)  # DeepSeek limit

    temperature = anthropic_body.get("temperature")
    if temperature is not None:
        deepseek_body["temperature"] = temperature

    top_p = anthropic_body.get("top_p")
    if top_p is not None:
        deepseek_body["top_p"] = top_p

    return deepseek_body


# ── Response Translation (Streaming) ────────────────────────
class StreamConverter:
    """Convert DeepSeek SSE stream to Anthropic SSE stream.

    Buffers content internally during streaming, then produces a clean
    Anthropic SSE sequence via finalize().  This avoids the malformed
    content-block sequences that the previous per-chunk emission created
    when DeepSeek interleaved text, tool_calls, and reasoning_content.
    """

    def __init__(self, model="claude-sonnet-4-20250514"):
        self.model = model
        self.msg_id = f"msg_{int(time.time() * 1000)}"
        self.started = False
        self.finished = False

        # Accumulators – content is collected, not emitted per-chunk
        self.text_parts = []          # list of str
        self.reasoning_parts = []     # list of str (DeepSeek thinking)
        self.tool_calls = {}          # index → {id, name, arguments}

        self.input_tokens = 0
        self.output_tokens = 0
        self.finish_reason = "stop"

    def _sse(self, event, data):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    # ── streaming phase (accumulate only) ──────────────────────
    def process_chunk(self, deepseek_chunk):
        """Accumulate one DeepSeek SSE chunk.  Returns '' always;
        call finalize() after the stream ends to get Anthropic SSE."""
        if deepseek_chunk is None or deepseek_chunk == "[DONE]":
            return ""

        choices = deepseek_chunk.get("choices", [])
        if not choices:
            return ""

        choice = choices[0]
        delta = choice.get("delta", {})
        finish = choice.get("finish_reason")

        usage = deepseek_chunk.get("usage")
        if usage:
            self.input_tokens = usage.get("prompt_tokens", self.input_tokens)
            self.output_tokens = usage.get("completion_tokens", self.output_tokens)

        if not self.started:
            self.started = True

        # text
        content = delta.get("content")
        if content:
            self.text_parts.append(content)

        # reasoning / thinking (DeepSeek v4-pro may emit this)
        reasoning = delta.get("reasoning_content")
        if reasoning:
            self.reasoning_parts.append(reasoning)

        # tool calls
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                idx = tc.get("index", 0)
                tc_id = tc.get("id")
                func = tc.get("function", {})

                if idx not in self.tool_calls:
                    self.tool_calls[idx] = {
                        "id": tc_id or f"toolu_{int(time.time()*1000)}_{idx}",
                        "name": func.get("name", ""),
                        "arguments": "",
                    }
                    print(f"[TOOL] tool call detected: {func.get('name', 'unknown')}",
                          file=sys.stderr)

                if func.get("name"):
                    self.tool_calls[idx]["name"] = func["name"]
                if func.get("arguments"):
                    self.tool_calls[idx]["arguments"] += func["arguments"]

        if finish:
            stop_map = {"stop": "end_turn", "length": "max_tokens",
                        "tool_calls": "tool_use", "content_filter": "end_turn"}
            self.finish_reason = stop_map.get(finish, "end_turn")

        return ""

    # ── finalize phase (produce clean Anthropic SSE) ───────────
    def finalize(self):
        """Generate a well-formed Anthropic SSE sequence.

        - text + tool_calls → both are emitted (text first, then tools)
        - text only → single text block
        - tool_calls only → tool-use blocks
        - reasoning only → emitted as text
        - empty → empty text block
        - Exactly one message_start … message_stop cycle.
        """
        if self.finished:
            return ""
        self.finished = True

        if not self.started:
            return ""

        output = ""

        # ── message_start ──
        output += self._sse("message_start", {
            "type": "message_start",
            "message": {
                "id": self.msg_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": self.model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": self.input_tokens,
                          "output_tokens": self.output_tokens},
            }
        })

        full_text = "".join(self.text_parts)
        has_text = bool(full_text.strip())
        has_tools = bool(self.tool_calls)
        has_reasoning = bool(self.reasoning_parts)

        # ── content blocks (priority: text+tools > tools > reasoning) ──
        if has_text or has_tools:
            block_idx = 0

            # Text block first (if any)
            if has_text:
                output += self._sse("content_block_start", {
                    "type": "content_block_start",
                    "index": block_idx,
                    "content_block": {"type": "text", "text": ""},
                })
                output += self._sse("content_block_delta", {
                    "type": "content_block_delta",
                    "index": block_idx,
                    "delta": {"type": "text_delta", "text": full_text},
                })
                output += self._sse("content_block_stop", {
                    "type": "content_block_stop",
                    "index": block_idx,
                })
                block_idx += 1

            # Tool blocks next (both text+tools and tools-only)
            if has_tools:
                if has_reasoning:
                    print(f"[FILTER] skipped reasoning ({len(self.reasoning_parts)} chunks), "
                          f"emitting {len(self.tool_calls)} tool(s)",
                          file=sys.stderr)
                for idx in sorted(self.tool_calls.keys()):
                    tc = self.tool_calls[idx]
                    output += self._sse("content_block_start", {
                        "type": "content_block_start",
                        "index": block_idx,
                        "content_block": {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": {},
                        }
                    })
                    output += self._sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": block_idx,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": tc["arguments"],
                        }
                    })
                    output += self._sse("content_block_stop", {
                        "type": "content_block_stop",
                        "index": block_idx,
                    })
                    block_idx += 1

        elif has_reasoning:
            # reasoning-only (no content, no tools) → emit as text
            reasoning_text = "".join(self.reasoning_parts)
            output += self._sse("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            })
            output += self._sse("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": reasoning_text},
            })
            output += self._sse("content_block_stop", {
                "type": "content_block_stop",
                "index": 0,
            })

        else:
            # empty response – emit empty text block
            output += self._sse("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            })
            output += self._sse("content_block_stop", {
                "type": "content_block_stop",
                "index": 0,
            })

        # ── message end ──
        output += self._sse("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": self.finish_reason,
                "stop_sequence": None,
            },
            "usage": {"output_tokens": self.output_tokens},
        })
        output += self._sse("message_stop", {"type": "message_stop"})

        return output


# ── Response Translation (Non-Streaming) ────────────────────
def deepseek_to_anthropic(deepseek_body):
    """Convert DeepSeek non-streaming response to Anthropic format."""
    choices = deepseek_body.get("choices", [])
    usage = deepseek_body.get("usage", {})

    if not choices:
        return {
            "id": f"msg_{int(time.time()*1000)}",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": ""}],
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    choice = choices[0]
    message = choice.get("message", {})
    finish = choice.get("finish_reason", "stop")

    content = []

    # Text content
    text = message.get("content", "")
    if text:
        content.append({"type": "text", "text": text})

    # Tool calls
    tool_calls = message.get("tool_calls", [])
    for tc in tool_calls:
        func = tc.get("function", {})
        try:
            args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        content.append({
            "type": "tool_use",
            "id": tc.get("id", f"toolu_{int(time.time()*1000)}"),
            "name": func.get("name", ""),
            "input": args,
        })

    stop_map = {"stop": "end_turn", "length": "max_tokens",
                "tool_calls": "tool_use", "content_filter": "end_turn"}

    return {
        "id": f"msg_{int(time.time()*1000)}",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": "claude-sonnet-4-20250514",
        "stop_reason": stop_map.get(finish, "end_turn"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }
# ── HTTP Server ─────────────────────────────────────────────
class ProxyHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress default logging, use our own
        pass

    def _send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        # Prevent HTTP/1.1 keep-alive from blocking the single-threaded server.
        # After the SSE stream ends, close the connection so the server can
        # accept the next client.
        self.close_connection = True

    def _get_path(self):
        return urlparse(self.path).path

    def do_OPTIONS(self):
        print(f"[HTTP] OPTIONS {self.path}")
        path = self._get_path()
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        print(f"[HTTP] GET {self.path}")
        path = self._get_path()
        if path == "/v1/models" or path == "/v1/models/":
            models = {
                "object": "list",
                "data": [
                    {"id": "claude-sonnet-4-20250514", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
                    {"id": "claude-opus-4-20250514", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
                    {"id": "claude-opus-4-5-20250514", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
                    {"id": "claude-haiku-4-20250514", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
                    {"id": "claude-3-opus-20240229", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
                    {"id": "claude-3-5-sonnet-20240620", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
                    {"id": "deepseek-chat", "object": "model", "created": 1700000000, "owned_by": "deepseek"},
                    {"id": "deepseek-reasoner", "object": "model", "created": 1700000000, "owned_by": "deepseek"},
                ]
            }
            self._send_json(200, models)
        elif path == "/health":
            self._send_json(200, {"status": "ok", "deepseek_model": DEEPSEEK_MODEL})
        else:
            print(f"[HTTP] 404 unknown GET: {self.path}")
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        print(f"[HTTP] POST {self.path} headers={dict(self.headers)}")
        path = self._get_path()
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            if path == "/v1/messages":
                self._handle_messages(body)
            elif path == "/v1/messages/count_tokens":
                print(f"[HTTP] count_tokens request: {json.dumps(body)[:200]}")
                self._send_json(200, {"input_tokens": 0})
            elif path == "/mcp":
                global _search_engine
                if _search_engine is None:
                    _search_engine = SearchEngine()
                result = _handle_mcp_jsonrpc(body, _search_engine)
                if result is not None:
                    self._send_json(200, result)
                else:
                    self.send_response(202)
                    self.end_headers()
            else:
                print(f"[HTTP] 404 unknown POST endpoint: {self.path}")
                self._send_json(404, {"error": f"unknown endpoint: {self.path}"})

        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"[HTTP] client disconnected: {e}")
        except Exception as e:
            print(f"[ERROR] {e}")
            try:
                self._send_json(500, {"error": str(e)})
            except Exception:
                pass

    def _handle_messages(self, body):
        deepseek_body = anthropic_to_deepseek(body)
        stream = deepseek_body.get("stream", False)
        model_name = body.get("model", "claude-sonnet-4-20250514")

        print(f"[REQ] model={model_name} stream={stream} msgs={len(deepseek_body.get('messages',[]))}")

        if stream:
            self._handle_stream(deepseek_body, model_name)
        else:
            self._handle_sync(deepseek_body)

    def _handle_stream(self, deepseek_body, model_name):
        t0 = time.time()
        self._send_sse()

        # Resolve DeepSeek API host
        try:
            deepseek_ip = resolve_host(DEEPSEEK_HOST)
        except Exception as e:
            err = {"type": "error", "error": {"type": "api_error", "message": str(e)}}
            self.wfile.write(f"event: error\ndata: {json.dumps(err)}\n\n".encode())
            return
        t_dns = time.time() - t0

        conn = None
        converter = StreamConverter(model=model_name)
        try:
            # Build HTTPS connection with custom SNI
            ctx = ssl.create_default_context()
            import socket as sock_module
            conn = http.client.HTTPSConnection(
                deepseek_ip, 443, timeout=30, context=ctx
            )
            def custom_connect():
                sock = sock_module.create_connection((deepseek_ip, 443), timeout=30)
                conn.sock = ctx.wrap_socket(sock, server_hostname=DEEPSEEK_HOST)
            conn.connect = custom_connect

            request_body = json.dumps(deepseek_body).encode()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
                "Accept": "text/event-stream",
                "Host": DEEPSEEK_HOST,
            }
            conn.request("POST", DEEPSEEK_PATH, body=request_body, headers=headers)
            resp = conn.getresponse()
            t_ttfb = time.time() - t0

            if resp.status != 200:
                err_body = resp.read().decode()
                print(f"[ERROR] DeepSeek returned {resp.status}: {err_body[:200]}", file=sys.stderr, flush=True)
                err = {"type": "error", "error": {
                    "type": "api_error",
                    "message": f"DeepSeek API error {resp.status}: {err_body[:200]}"
                }}
                self.wfile.write(f"event: error\ndata: {json.dumps(err)}\n\n".encode())
                self.wfile.flush()
                return

            # Set a per-read timeout on the raw socket to detect hangs
            try:
                raw_sock = conn.sock
                if hasattr(raw_sock, 'settimeout'):
                    # 30s between chunks is generous for any LLM
                    raw_sock.settimeout(30)
            except Exception:
                pass

            for line in resp:
                line = line.decode()
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        converter.process_chunk(None)
                    else:
                        try:
                            chunk = json.loads(data_str)
                            converter.process_chunk(chunk)
                        except json.JSONDecodeError:
                            continue

            # Generate clean Anthropic SSE once (finalize handles dedup + filtering)
            final_output = converter.finalize()
            if final_output:
                self.wfile.write(final_output.encode())
                self.wfile.flush()

            t_total = time.time() - t0
            print(f"[TIMING] dns={t_dns:.2f}s ttfb={t_ttfb:.2f}s total={t_total:.2f}s "
                  f"tokens_in={converter.input_tokens} tokens_out={converter.output_tokens}",
                  file=sys.stderr, flush=True)

        except (BrokenPipeError, ConnectionResetError, OSError, socket.timeout) as e:
            print(f"[STREAM_DISCONNECT] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            # Flush whatever partial content we collected before the disconnect
            partial = converter.finalize()
            if partial:
                try:
                    self.wfile.write(partial.encode())
                except Exception:
                    pass
            # Send error + message_stop so Claude Code knows the stream is done
            err = {"type": "error", "error": {
                "type": "api_error",
                "message": f"DeepSeek connection lost: {type(e).__name__}"
            }}
            try:
                self.wfile.write(f"event: error\ndata: {json.dumps(err)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass

        except Exception as e:
            print(f"[STREAM_ERROR] {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            try:
                err = {"type": "error", "error": {"type": "api_error", "message": str(e)}}
                self.wfile.write(f"event: error\ndata: {json.dumps(err)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _handle_sync(self, deepseek_body):
        try:
            deepseek_ip = resolve_host(DEEPSEEK_HOST)
        except Exception as e:
            self._send_json(500, {"error": str(e)})
            return

        import socket as sock_module
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(deepseek_ip, 443, timeout=120, context=ctx)
        def custom_connect():
            sock = sock_module.create_connection((deepseek_ip, 443), timeout=120)
            conn.sock = ctx.wrap_socket(sock, server_hostname=DEEPSEEK_HOST)
        conn.connect = custom_connect

        request_body = json.dumps(deepseek_body).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "Host": DEEPSEEK_HOST,
        }
        conn.request("POST", DEEPSEEK_PATH, body=request_body, headers=headers)
        resp = conn.getresponse()
        resp_body = json.loads(resp.read())

        if resp.status != 200:
            self._send_json(resp.status, resp_body)
            return

        anthropic_resp = deepseek_to_anthropic(resp_body)
        print(f"[RESP] tokens: in={anthropic_resp['usage']['input_tokens']} out={anthropic_resp['usage']['output_tokens']}")
        self._send_json(200, anthropic_resp)
        conn.close()


# ── Main ─────────────────────────────────────────────────────
def main():
    # DNS resolution happens lazily on first request (avoids blocking startup)
    print(f"\033[32m✓ API Key loaded from ~/.deepseek-key\033[0m")
    print(f"\033[32m✓ Proxy listening on http://{LISTEN_HOST}:{LISTEN_PORT}\033[0m")
    print(f"\033[36m  Claude Code env:\033[0m")
    print(f"    export ANTHROPIC_BASE_URL=http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"    export ANTHROPIC_API_KEY=any-value")
    print()

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[33mShutting down...\033[0m")
        server.shutdown()


if __name__ == "__main__":
    main()