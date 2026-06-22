#!/usr/bin/env python3
"""
dev/proxy_patch.py — VPN proxy injection for local development.
NOT included in the published minisearch package.

Activates when DSOCKS_PROXY environment variable is set.

SOCKS5 socket monkeypatch — routes ALL Python TCP through the VPN proxy.
This lets MiniSearch bypass the GFW to reach Google, Yandex, etc.

Without DSOCKS_PROXY, calling activate() is a no-op.
"""

import socket as _socket
import struct as _struct
import os as _os
import sys as _sys

# ── State ─────────────────────────────────────────────────────
_activated = False


def activate():
    """Activate SOCKS5 proxy patch.
    Safe to call multiple times — second call is a no-op.
    Returns True if patches were applied, False if skipped."""
    global _activated
    if _activated:
        return True

    _SOCKS_PROXY = _os.environ.get("DSOCKS_PROXY")
    if not _SOCKS_PROXY:
        print("[dev/proxy_patch] DSOCKS_PROXY not set — skipping all patches",
              file=_sys.stderr, flush=True)
        return False

    _HOST, _PORT = _SOCKS_PROXY.rsplit(":", 1)
    _PORT = int(_PORT)

    # ── Bypass list: hosts that connect directly (no proxy) ──
    # Comma-separated in DSOCKS_BYPASS env var.  Useful for Chinese
    # engines that work fine from within China but trigger anti-spider
    # when accessed from a foreign VPN IP.
    _BYPASS_RAW = _os.environ.get("DSOCKS_BYPASS", "")
    _BYPASS_HOSTS = set(
        h.strip().lower() for h in _BYPASS_RAW.split(",") if h.strip()
    ) if _BYPASS_RAW else set()
    if _BYPASS_HOSTS:
        print(f"[dev/proxy_patch] bypass hosts: {_BYPASS_HOSTS}",
              file=_sys.stderr, flush=True)

    # ── 1. SOCKS5 socket monkeypatch ──────────────────────────
    _original_connect = _socket.socket.connect

    def _patched_connect(self, address):
        host, port = address
        # Don't proxy connections to the proxy itself, localhost, or bypass hosts
        if host == _HOST or host in ('127.0.0.1', '::1', 'localhost'):
            return _original_connect(self, address)
        if host.lower() in _BYPASS_HOSTS:
            return _original_connect(self, address)
        # Connect to SOCKS5 proxy
        _original_connect(self, (_HOST, _PORT))
        # SOCKS5 handshake: greeting (no auth)
        self.sendall(b'\x05\x01\x00')
        if self.recv(2) != b'\x05\x00':
            raise OSError("SOCKS5 auth failed")
        # SOCKS5 CONNECT request
        addr_bytes = host.encode() if isinstance(host, str) else \
            (_socket.inet_pton(_socket.AF_INET, host)
             if '.' in str(host)
             else _socket.inet_pton(_socket.AF_INET6, host))
        if isinstance(host, str) and not host.replace('.', '').replace(':', '').isdigit():
            # Domain name (ATYP=0x03)
            req = (b'\x05\x01\x00\x03'
                   + _struct.pack('B', len(addr_bytes))
                   + addr_bytes
                   + _struct.pack('>H', port))
        else:
            # IPv4 (ATYP=0x01)
            req = (b'\x05\x01\x00\x01'
                   + _socket.inet_aton(host)
                   + _struct.pack('>H', port))
        self.sendall(req)
        resp = self.recv(10)
        if resp[1] != 0:
            raise OSError(f"SOCKS5 connect failed: code {resp[1]}")
        return None

    _socket.socket.connect = _patched_connect
    print(f"[dev/proxy_patch] SOCKS5 proxy active → {_SOCKS_PROXY}",
          file=_sys.stderr, flush=True)

    _activated = True
    return True
