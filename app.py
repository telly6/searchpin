#!/usr/bin/env python3
"""
MiniSearch Desktop App
tkinter control panel — start/stop the MCP search server, copy config, monitor status.
"""

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from search_server import MCPHandler
from search_engine import SearchEngine, PRODUCT_NAME, DEFAULT_PORT


class MiniSearchApp:
    def __init__(self):
        self.engine = None
        self.server_thread = None
        self.server = None
        self.server_running = False

        self.root = tk.Tk()
        self.root.title(f"{PRODUCT_NAME}")
        self.root.geometry("360x220")
        self.root.resizable(False, False)

        # Prevent Cmd+Q from quitting while server runs
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._update_status()

        self.root.mainloop()

    def _build_ui(self):
        # ── Status indicator ──
        status_frame = ttk.Frame(self.root, padding=(10, 10, 10, 5))
        status_frame.pack(fill=tk.X)

        self.status_canvas = tk.Canvas(status_frame, width=16, height=16,
                                       highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.status_light = self.status_canvas.create_oval(
            2, 2, 14, 14, fill="#999999", outline="")

        self.status_label = ttk.Label(status_frame, text=f"{PRODUCT_NAME} — 服务未启动",
                                      font=("Helvetica", 12, "bold"))
        self.status_label.pack(side=tk.LEFT)

        # ── Port config ──
        config_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        config_frame.pack(fill=tk.X)

        ttk.Label(config_frame, text="端口:").pack(side=tk.LEFT)

        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        port_entry = ttk.Entry(config_frame, textvariable=self.port_var, width=6)
        port_entry.pack(side=tk.LEFT, padx=(4, 0))

        # ── Buttons ──
        btn_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        btn_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(btn_frame, text="启动", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self._stop,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(btn_frame, text="复制 MCP 配置",
                   command=self._copy_config).pack(side=tk.LEFT)

        # ── Info ──
        info_frame = ttk.Frame(self.root, padding=(10, 8, 10, 5))
        info_frame.pack(fill=tk.X)

        self.addr_label = ttk.Label(
            info_frame,
            text=f"地址: http://127.0.0.1:{DEFAULT_PORT}/mcp",
            font=("Monaco", 10),
            foreground="#555555",
        )
        self.addr_label.pack(anchor=tk.W)

        hint = ttk.Label(
            info_frame,
            text="接入你本地的 AI agent 中即可使用联网搜索",
            font=("Helvetica", 10),
            foreground="#888888",
        )
        hint.pack(anchor=tk.W, pady=(4, 0))

        # ── Bottom bar ──
        bottom = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Label(bottom, text=f"{PRODUCT_NAME} v1.0 · 自部署免费搜索",
                  foreground="#aaaaaa", font=("Helvetica", 9)).pack(side=tk.LEFT)

    def _start(self):
        port = int(self.port_var.get())
        try:
            self.engine = SearchEngine(port=port)
            MCPHandler.engine = self.engine

            self.server = self._make_server(port)
            self.server_thread = threading.Thread(
                target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.server_running = True
            self._update_status()
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None
            self.server_thread = None
            self.server_running = False
            if self.engine:
                self.engine.close()
                self.engine = None
            MCPHandler.engine = None
            self._update_status()

    def _on_close(self):
        if self.server_running:
            ok = messagebox.askokcancel(
                f"退出 {PRODUCT_NAME}",
                f"{PRODUCT_NAME} 正在运行中，退出将停止搜索服务。\n确定退出吗？")
            if not ok:
                return
            self._stop()
        self.root.destroy()

    def _update_status(self):
        if self.server_running:
            color = "#34c759"  # green
            self.status_label.config(text=f"{PRODUCT_NAME} — 运行中")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        else:
            color = "#999999"  # gray
            self.status_label.config(text=f"{PRODUCT_NAME} — 服务未启动")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

        self.status_canvas.itemconfig(self.status_light, fill=color)
        port = self.port_var.get()
        self.addr_label.config(text=f"地址: http://127.0.0.1:{port}/mcp")

    def _copy_config(self):
        port = self.port_var.get()
        config = {
            "mcpServers": {
                PRODUCT_NAME: {
                    "command": f"http://127.0.0.1:{port}/mcp"
                }
            }
        }
        text = json.dumps(config, ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("已复制", "MCP 配置已复制到剪贴板，粘贴到你的 AI agent 配置中即可。")

    @staticmethod
    def _make_server(port):
        import http.server
        http.server.HTTPServer.allow_reuse_address = True
        return http.server.HTTPServer(("127.0.0.1", port), MCPHandler)


def main():
    os.environ.setdefault("MINISEARCH_NAME", "MiniSearch")
    os.environ.setdefault("MINISEARCH_PORT", "8789")
    MiniSearchApp()


if __name__ == "__main__":
    main()
