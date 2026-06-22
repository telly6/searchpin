#!/usr/bin/env python3
"""
dev/auto_proxy.py — Auto-detect VPN SOCKS5 proxy and set env vars.
NOT included in the published minisearch package.

Detects VPN status via macOS system SOCKS proxy settings + port probe.
When VPN is connected: sets DSOCKS_PROXY and DSOCKS_BYPASS.
When VPN is disconnected: does nothing (Python uses direct connection).

This allows seamless switching:
  - VPN ON  → all traffic goes through proxy (foreign IP)
  - VPN OFF → direct domestic connection

Usage:
  from dev.auto_proxy import auto_detect_and_set
  auto_detect_and_set()  # sets env vars if VPN detected
"""

import os
import sys
import socket
import subprocess
import re

# ── Known Chinese engine hosts to bypass when on VPN ─────────
# When on VPN (foreign IP), these Chinese engines may trigger anti-spider
# or return poor results, so we connect to them directly (no proxy).
DEFAULT_BYPASS_HOSTS = [
    "www.baidu.com",
    "www.sogou.com",
    "cn.bing.com",
]


def _get_system_socks_proxy(timeout=3):
    """Read macOS system SOCKS proxy settings via networksetup.
    Returns (host, port) or (None, None)."""
    try:
        # Get all network services
        result = subprocess.run(
            ["networksetup", "-listallnetworkservices"],
            capture_output=True, text=True, timeout=timeout
        )
        lines = result.stdout.strip().split('\n')
        # First line is "An asterisk (*) denotes that a network service is disabled."
        services = [s.strip() for s in lines[1:] if s.strip() and not s.startswith('*')]

        for service in services:
            try:
                result = subprocess.run(
                    ["networksetup", "-getsocksfirewallproxy", service],
                    capture_output=True, text=True, timeout=timeout
                )
                output = result.stdout
                enabled = re.search(r'Enabled:\s*(Yes)', output)
                if enabled:
                    server = re.search(r'Server:\s*(\S+)', output)
                    port = re.search(r'Port:\s*(\d+)', output)
                    if server and port:
                        host = server.group(1)
                        port_num = int(port.group(1))
                        return host, port_num
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def _test_socks5_proxy(host, port, timeout=1.5):
    """Test if a SOCKS5 proxy is actually responsive at host:port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        # SOCKS5 greeting (no auth)
        sock.sendall(b'\x05\x01\x00')
        resp = sock.recv(2)
        sock.close()
        return resp == b'\x05\x00'
    except Exception:
        return False


def auto_detect():
    """Auto-detect VPN SOCKS5 proxy.
    Returns (host, port) if found and responsive, else (None, None)."""
    # 1. Check macOS system SOCKS proxy setting
    host, port = _get_system_socks_proxy()
    if host and port and _test_socks5_proxy(host, port):
        return host, port

    # 2. Fallback: probe common proxy ports
    common_ports = [51453, 58127, 1080, 1086, 7890, 7891, 10808]
    for p in common_ports:
        if _test_socks5_proxy('127.0.0.1', p):
            return '127.0.0.1', p

    return None, None


def auto_detect_and_set():
    """Detect VPN proxy and set DSOCKS_PROXY / DSOCKS_BYPASS env vars.
    Returns True if proxy was detected and set, False otherwise.
    Safe to call multiple times — does nothing if already set."""
    # Already configured? Skip.
    if os.environ.get("DSOCKS_PROXY"):
        return True

    host, port = auto_detect()
    if host and port:
        proxy_addr = f"{host}:{port}"
        os.environ["DSOCKS_PROXY"] = proxy_addr
        bypass_str = ",".join(DEFAULT_BYPASS_HOSTS)
        os.environ["DSOCKS_BYPASS"] = bypass_str
        print(f"[auto_proxy] VPN proxy detected → {proxy_addr} "
              f"(bypass: {DEFAULT_BYPASS_HOSTS})",
              file=sys.stderr, flush=True)
        return True
    else:
        print("[auto_proxy] No VPN proxy detected — using direct connection",
              file=sys.stderr, flush=True)
        return False
