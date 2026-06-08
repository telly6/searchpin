#!/usr/bin/env python3
"""
MiniSearch Desktop App
Configuration panel + model manager + one-click search test.
No server — AI agents launch search_server.py directly via stdio MCP.
Settings persist to ~/.minisearch/config.json
"""

import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from search_engine import SearchEngine, PRODUCT_NAME, DEFAULT_MODEL_NAME
from model_manager import list_all_models, download_model, delete_model, get_cached_size_mb

CONFIG_DIR = os.path.expanduser("~/.minisearch")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def detect_ram_gb():
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(int(out.strip()) / (1024 ** 3))
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(int(line.split()[1]) / (1024 * 1024))
    except Exception:
        return 0


def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


class MiniSearchApp:
    def __init__(self):
        saved = load_config()
        self.config = {
            "model_name": saved.get("model_name", DEFAULT_MODEL_NAME),
            "max_workers": saved.get("max_workers", 3),
            "max_results": saved.get("max_results", 10),
            "embedding_mode": saved.get("embedding_mode", "local"),
            "api_endpoint": saved.get("api_endpoint", "https://api.openai.com/v1/embeddings"),
            "api_key": saved.get("api_key", ""),
            "api_model": saved.get("api_model", "text-embedding-3-small"),
        }

        self.ram_gb = detect_ram_gb()
        self.models = list_all_models()
        self._model_rows = {}

        self.root = tk.Tk()
        self.root.title(f"{PRODUCT_NAME} · 配置")
        self.root.geometry("540x540")
        self.root.resizable(True, True)
        self.root.minsize(480, 460)

        self._build_ui()
        self._load_config_to_ui()
        self.root.mainloop()

    # ═══════════════════════════════════════════════════════════
    # UI Construction
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Embedding source toggle ──
        toggle_frame = ttk.Frame(outer)
        toggle_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(toggle_frame, text="Embedding 来源",
                  font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value=self.config["embedding_mode"])
        self.local_btn = ttk.Radiobutton(
            toggle_frame, text="本地模型", variable=self.mode_var,
            value="local", command=self._on_mode_switch)
        self.local_btn.pack(side=tk.RIGHT)
        self.api_btn = ttk.Radiobutton(
            toggle_frame, text="API 模式", variable=self.mode_var,
            value="api", command=self._on_mode_switch)
        self.api_btn.pack(side=tk.RIGHT, padx=(0, 8))

        # ── Model list (local) / API form ──
        self.models_frame = ttk.Frame(outer)
        self.models_frame.pack(fill=tk.BOTH, expand=True)
        self._build_model_list()

        self.api_frame = ttk.Frame(outer)
        self._build_api_form()

        # ── Progress bar ──
        self.progress_frame = ttk.Frame(outer)
        self.progress_frame.pack(fill=tk.X, pady=(4, 8))

        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 6))

        self.progress_label = ttk.Label(
            self.progress_frame, text="", font=("Helvetica", 9), width=18)
        self.progress_label.pack(side=tk.RIGHT)

        # ── Settings ──
        settings = ttk.Frame(outer)
        settings.pack(fill=tk.X, pady=(0, 8))

        # Workers
        ttk.Label(settings, text="并行爬取线程",
                  font=("Helvetica", 10)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.workers_var = tk.StringVar(value=str(self.config["max_workers"]))
        self.workers_entry = ttk.Entry(settings, textvariable=self.workers_var, width=8)
        self.workers_entry.grid(row=0, column=1, sticky=tk.W, pady=2)
        self.workers_var.trace_add("write", lambda *_: self._on_config_change())

        # Max results
        ttk.Label(settings, text="最大结果数",
                  font=("Helvetica", 10)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.results_var = tk.StringVar(value=str(self.config["max_results"]))
        self.results_entry = ttk.Entry(settings, textvariable=self.results_var, width=8)
        self.results_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        self.results_var.trace_add("write", lambda *_: self._on_config_change())

        # ── Buttons ──
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X, pady=(4, 2))

        self.test_btn = ttk.Button(btn_frame, text="测试搜索", command=self._test_search)
        self.test_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(btn_frame, text="复制 MCP 配置",
                   command=self._copy_config).pack(side=tk.LEFT)

        # ── Bottom ──
        ttk.Label(outer, text=f"{PRODUCT_NAME} v1.0 · 自部署免费搜索 · stdio 模式",
                  foreground="#bbbbbb", font=("Helvetica", 9)) \
            .pack(side=tk.BOTTOM, pady=(8, 2))

        self._on_mode_switch()

    def _build_model_list(self):
        """Scrollable model list for local mode."""
        header = ttk.Frame(self.models_frame)
        header.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(header, text="模型", font=("Helvetica", 10, "bold")) \
            .pack(side=tk.LEFT, padx=(2, 0))
        ttk.Label(header, text="状态", font=("Helvetica", 10, "bold")) \
            .pack(side=tk.RIGHT, padx=(0, 50))

        canvas_frame = ttk.Frame(self.models_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.model_canvas = tk.Canvas(canvas_frame, highlightthickness=0, height=240)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                   command=self.model_canvas.yview)
        self.model_list_inner = ttk.Frame(self.model_canvas)

        self.model_list_inner.bind("<Configure>",
            lambda e: self.model_canvas.configure(
                scrollregion=self.model_canvas.bbox("all")))
        self.model_canvas.create_window((0, 0), window=self.model_list_inner,
                                         anchor=tk.NW, tags="inner")

        self.model_canvas.configure(yscrollcommand=scrollbar.set)
        self.model_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_scroll(event):
            if event.delta:
                # macOS trackpad sends small deltas (±1); Windows/mice send ±120
                delta = event.delta if abs(event.delta) < 10 else event.delta / 120
                self.model_canvas.yview_scroll(int(-delta), "units")
            elif event.num == 4:
                self.model_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.model_canvas.yview_scroll(1, "units")

        def _bind():
            self.model_canvas.bind_all("<MouseWheel>", _on_scroll)
            self.model_canvas.bind_all("<Button-4>", _on_scroll)
            self.model_canvas.bind_all("<Button-5>", _on_scroll)

        def _unbind():
            self.model_canvas.unbind_all("<MouseWheel>")
            self.model_canvas.unbind_all("<Button-4>")
            self.model_canvas.unbind_all("<Button-5>")

        self.model_canvas.bind("<Enter>", lambda _: _bind())
        self.model_canvas.bind("<Leave>", lambda _: _unbind())

        self._build_model_rows()

    def _build_model_rows(self):
        for widget in self.model_list_inner.winfo_children():
            widget.destroy()
        self._model_rows.clear()
        self._model_radios = {}

        self.models.sort(key=lambda m: (not m["cached"], -m["size_gb"], m["model"]))

        for m in self.models:
            row = ttk.Frame(self.model_list_inner)
            row.pack(fill=tk.X, pady=1)

            rb = ttk.Radiobutton(
                row, text="", variable=self._model_selection_var(),
                value=m["model"],
                state=tk.NORMAL if m["cached"] else tk.DISABLED)
            rb.pack(side=tk.LEFT)
            self._model_radios[m["model"]] = rb

            info = ttk.Frame(row)
            info.pack(side=tk.LEFT, fill=tk.X, expand=True)

            ttk.Label(info, text=m["model"].split("/")[-1],
                      font=("Helvetica", 10)).pack(anchor=tk.W)

            tags_str = " · ".join(m["tags"]) + f" · {m['dim']}维 · {m['size_mb']}MB"
            ttk.Label(info, text=tags_str,
                      foreground="#888888", font=("Helvetica", 9)) \
                .pack(anchor=tk.W)

            action_frame = ttk.Frame(row)
            action_frame.pack(side=tk.RIGHT, padx=(4, 4))

            if m["cached"]:
                cached_size = get_cached_size_mb(m)
                size_str = f"{cached_size:.0f}MB" if cached_size > 0 else ""
                ttk.Label(action_frame, text=f"✓ 已下载 {size_str}",
                          foreground="#34c759", font=("Helvetica", 9)) \
                    .pack(side=tk.RIGHT, padx=(4, 0))
                btn = ttk.Button(action_frame, text="卸载", width=5,
                                 command=lambda m=m: self._uninstall_model(m))
                btn.pack(side=tk.RIGHT)
            else:
                ttk.Label(action_frame, text="✗ 未下载",
                          foreground="#999999", font=("Helvetica", 9)) \
                    .pack(side=tk.RIGHT, padx=(4, 0))
                btn = ttk.Button(action_frame, text="下载", width=5,
                                 command=lambda m=m: self._download_model(m))
                btn.pack(side=tk.RIGHT)

            self._model_rows[m["model"]] = {
                "action_btn": btn,
                "action_frame": action_frame,
            }

    def _model_selection_var(self):
        if not hasattr(self, '_model_sel_var'):
            self._model_sel_var = tk.StringVar(value=self.config["model_name"])
            self._model_sel_var.trace_add("write", lambda *_: self._on_config_change())
        return self._model_sel_var

    def _build_api_form(self):
        ttk.Label(self.api_frame, text="API 端点",
                  font=("Helvetica", 10)).pack(anchor=tk.W, pady=(0, 1))
        self.api_endpoint_var = tk.StringVar(value=self.config["api_endpoint"])
        self.api_endpoint_entry = ttk.Entry(self.api_frame, textvariable=self.api_endpoint_var, width=50)
        self.api_endpoint_entry.pack(fill=tk.X, pady=(0, 6))
        self.api_endpoint_var.trace_add("write", lambda *_: self._on_config_change())

        ttk.Label(self.api_frame, text="API Key",
                  font=("Helvetica", 10)).pack(anchor=tk.W, pady=(0, 1))
        self.api_key_var = tk.StringVar(value=self.config["api_key"])
        self.api_key_entry = ttk.Entry(self.api_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.pack(fill=tk.X, pady=(0, 6))
        self.api_key_var.trace_add("write", lambda *_: self._on_config_change())

        ttk.Label(self.api_frame, text="模型 ID",
                  font=("Helvetica", 10)).pack(anchor=tk.W, pady=(0, 1))
        self.api_model_var = tk.StringVar(value=self.config["api_model"])
        self.api_model_entry = ttk.Entry(self.api_frame, textvariable=self.api_model_var, width=50)
        self.api_model_entry.pack(fill=tk.X, pady=(0, 6))
        self.api_model_var.trace_add("write", lambda *_: self._on_config_change())

        ttk.Label(self.api_frame,
                  text="兼容 OpenAI Embeddings API 格式",
                  foreground="#888888", font=("Helvetica", 9)) \
            .pack(anchor=tk.W)

    # ═══════════════════════════════════════════════════════════
    # Mode switching
    # ═══════════════════════════════════════════════════════════

    def _on_mode_switch(self):
        mode = self.mode_var.get()
        if mode == "local":
            self.api_frame.pack_forget()
            self.models_frame.pack(fill=tk.BOTH, expand=True,
                                   before=self.progress_frame)
        else:
            self.models_frame.pack_forget()
            self.api_frame.pack(fill=tk.BOTH, expand=True,
                               before=self.progress_frame)
        self._on_config_change()

    # ═══════════════════════════════════════════════════════════
    # Model actions
    # ═══════════════════════════════════════════════════════════

    def _download_model(self, model_info):
        self._set_all_buttons_state(tk.DISABLED)
        self._set_progress(0, "准备下载...")

        def _run():
            try:
                download_model(model_info, progress_callback=self._on_download_progress)
                self.root.after(0, self._on_download_done, model_info)
            except Exception as e:
                self.root.after(0, self._on_download_error, model_info, str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_download_progress(self, pct, msg):
        self.root.after(0, self._set_progress, pct, msg)

    def _on_download_done(self, model_info):
        self._set_progress(0, "")
        self._set_all_buttons_state(tk.NORMAL)
        model_info["cached"] = True
        self._build_model_rows()

    def _on_download_error(self, model_info, error_msg):
        self._set_progress(0, f"下载失败: {error_msg}")
        self._set_all_buttons_state(tk.NORMAL)

    def _uninstall_model(self, model_info):
        ok = messagebox.askokcancel(
            "卸载模型",
            f"确定要删除 {model_info['model'].split('/')[-1]} 吗？\n"
            f"释放约 {get_cached_size_mb(model_info):.0f}MB 磁盘空间。")
        if not ok:
            return
        delete_model(model_info)
        model_info["cached"] = False
        self._build_model_rows()

    def _set_progress(self, pct, msg):
        self.progress_var.set(pct)
        self.progress_label.config(text=msg)

    def _set_all_buttons_state(self, state):
        for row_data in self._model_rows.values():
            try:
                row_data["action_btn"].config(state=state)
            except Exception:
                pass
        self.test_btn.config(state=state)

    # ═══════════════════════════════════════════════════════════
    # Config persistence
    # ═══════════════════════════════════════════════════════════

    def _on_config_change(self, *_):
        self._save_current_config()

    def _read_config_from_ui(self):
        mode = self.mode_var.get()
        model_name = DEFAULT_MODEL_NAME
        if mode == "local" and hasattr(self, '_model_sel_var'):
            model_name = self._model_sel_var.get() or DEFAULT_MODEL_NAME
        try:
            max_workers = int(self.workers_var.get())
        except ValueError:
            max_workers = 3
        try:
            max_results = int(self.results_var.get())
        except ValueError:
            max_results = 10

        return {
            "model_name": model_name,
            "max_workers": max_workers,
            "max_results": max_results,
            "embedding_mode": mode,
            "api_endpoint": self.api_endpoint_var.get(),
            "api_key": self.api_key_var.get(),
            "api_model": self.api_model_var.get(),
        }

    def _save_current_config(self):
        self.config = self._read_config_from_ui()
        save_config(self.config)

    def _load_config_to_ui(self):
        cfg = self.config
        self.mode_var.set(cfg["embedding_mode"])
        if hasattr(self, '_model_sel_var'):
            self._model_sel_var.set(cfg["model_name"])
        self.workers_var.set(str(cfg["max_workers"]))
        self.results_var.set(str(cfg["max_results"]))
        self.api_endpoint_var.set(cfg["api_endpoint"])
        self.api_key_var.set(cfg["api_key"])
        self.api_model_var.set(cfg["api_model"])

    # ═══════════════════════════════════════════════════════════
    # Test search
    # ═══════════════════════════════════════════════════════════

    def _test_search(self):
        self._save_current_config()
        cfg = self.config

        self.test_btn.config(state=tk.DISABLED, text="测试中...")
        self.root.update()

        def _run():
            try:
                t0 = time.time()
                engine = SearchEngine(
                    model_name=cfg["model_name"],
                    max_workers=cfg["max_workers"],
                    embedding_mode=cfg["embedding_mode"],
                    api_endpoint=cfg["api_endpoint"] or None,
                    api_key=cfg["api_key"] or None,
                    api_model=cfg["api_model"] or None,
                )

                result = engine.search("你好", max_results=cfg["max_results"])
                elapsed = time.time() - t0

                engine.close()
                self.root.after(0, self._show_test_result, result, elapsed)
            except Exception as e:
                self.root.after(0, self._show_test_result, None, 0, str(e))
            finally:
                self.root.after(0, self._restore_test_button)

        threading.Thread(target=_run, daemon=True).start()

    def _show_test_result(self, result, elapsed, error=None):
        if error:
            messagebox.showerror(
                "搜索测试失败",
                f"搜索引擎启动或执行失败：\n\n{error}"
            )
            return

        results = result.get("results", [])
        had_error = result.get("error")

        if had_error:
            messagebox.showwarning(
                "搜索测试",
                f"搜索完成，但返回了错误：\n\n{had_error}\n\n"
                f"耗时：{elapsed:.1f}s\n"
                f"模式：{self.config['embedding_mode']}"
            )
            return

        lines = [
            f"搜索测试通过 ✓",
            f"",
            f"Query：\"你好\"",
            f"返回结果：{len(results)} 条",
            f"耗时：{elapsed:.1f}s",
            f"模式：{self.config['embedding_mode']}",
            f"",
            f"前 {min(len(results), 3)} 条结果：",
        ]
        for i, r in enumerate(results[:3]):
            lines.append(f"  {i+1}. {r.get('title', 'N/A')[:50]}")
            lines.append(f"     {r.get('url', '')[:70]}")

        messagebox.showinfo("搜索测试", "\n".join(lines))

    def _restore_test_button(self):
        self.test_btn.config(state=tk.NORMAL, text="测试搜索")

    # ═══════════════════════════════════════════════════════════
    # Copy MCP config
    # ═══════════════════════════════════════════════════════════

    def _copy_config(self):
        server_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "search_server.py"))
        config = {
            "mcpServers": {
                PRODUCT_NAME: {
                    "command": sys.executable,
                    "args": [server_path],
                }
            }
        }
        text = json.dumps(config, ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo(
            "已复制",
            "MCP 配置已复制到剪贴板，粘贴到你的 AI agent 配置中即可。\n\n"
            f"使用方式：agent 会自动启动 {server_path} 作为 stdio 子进程。"
        )


def main():
    os.environ.setdefault("MINISEARCH_NAME", "MiniSearch")
    MiniSearchApp()


if __name__ == "__main__":
    main()
