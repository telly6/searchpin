#!/bin/bash
# ── Claude Code + DeepSeek Launcher ─────────────────────────
# Starts the API proxy, then launches Claude Code CLI.
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROXY_PID=""

cleanup() {
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        echo ""
        echo "Stopping proxy (pid $PROXY_PID)..."
        kill "$PROXY_PID" 2>/dev/null
        wait "$PROXY_PID" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

# ── Kill any stale proxy processes ───────────────────────────
pkill -f "proxy.py" 2>/dev/null || true
sleep 0.5

# Also kill anything on our ports
for port in 8787 8788; do
    EXISTING=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$EXISTING" ]; then
        kill $EXISTING 2>/dev/null || true
    fi
done

# ── Check prerequisites ─────────────────────────────────────
if [ ! -f "$HOME/.deepseek-key" ]; then
    echo "~/.deepseek-key not found!"
    echo ""
    echo "   Run:  echo \"sk-your-key\" > ~/.deepseek-key"
    exit 1
fi

KEY=$(cat "$HOME/.deepseek-key")
if [ "$KEY" = "sk-your-key" ]; then
    echo "Replace the placeholder key in ~/.deepseek-key with your real one."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "python3 not found"
    exit 1
fi

# ── Start proxy ─────────────────────────────────────────────
echo "Starting DeepSeek API proxy (port 8788)..."
PROXY_LOG="/tmp/claude-proxy.log"
python3 -u "$SCRIPT_DIR/proxy.py" >> "$PROXY_LOG" 2>&1 &
PROXY_PID=$!

# Wait for proxy to be ready
for i in $(seq 1 20); do
    if curl -s http://127.0.0.1:8788/health >/dev/null 2>&1; then
        echo "Proxy ready (pid $PROXY_PID)"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "Proxy failed to start after 10 seconds"
        cleanup
        exit 1
    fi
    sleep 0.5
done

# ── Launch Claude Code ──────────────────────────────────────
echo ""
echo "Launching Claude Code with DeepSeek backend..."
echo ""

export ANTHROPIC_BASE_URL="http://127.0.0.1:8788"
export ANTHROPIC_API_KEY="deepseek-proxy"
export CLAUDE_CODE_SIMPLE=1

claude --bare "$@"

# cleanup runs via trap