#!/usr/bin/env python3
"""
dev/run_search_server.py — development entry point.
Activates VPN proxy patches, then runs search_server.py.

Usage:
  DSOCKS_PROXY=127.0.0.1:58127 python3 dev/run_search_server.py [search_server_args...]

NOT included in the published minisearch package.
Foreign users run search_server.py directly — no proxy needed.
"""

import os
import sys
import runpy

_ProjectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ProjectRoot not in sys.path:
    sys.path.insert(0, _ProjectRoot)

# ── 1. Auto-detect VPN proxy (sets DSOCKS_PROXY if VPN is on) ──
from dev.auto_proxy import auto_detect_and_set
auto_detect_and_set()

# ── 2. Activate proxy patches (no-op if no proxy detected) ──
from dev.proxy_patch import activate
activate()

# ── Forward to search_server.py ──────────────────────────────
_ServerPath = os.path.join(_ProjectRoot, 'search_server.py')
sys.argv = [_ServerPath] + sys.argv[1:]
runpy.run_path(_ServerPath, run_name='__main__')
