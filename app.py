#!/usr/bin/env python3
"""
GUI launcher for the YouTube Script Agent.
Run this file or the desktop shortcut — paste a URL and click Generate.
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

# Ensure UTF-8 output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Redirect stdout/stderr to the GUI log ─────────────────────────────────────

class _LogRedirect:
    def __init__(self, widget: scrolledtext.ScrolledText):
        self._w = widget
        self.encoding = "utf-8"

    def write(self, text: str):
        self._w.configure(state="normal")
        self._w.insert(tk.END, text)
        self._w.see(tk.END)
        self._w.configure(state="disabled")

    def flush(self):
        pass


# ── Main window ────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Убиваю БПМ — Агент сценариев")
        self.resizable(True, True)
        self.minsize(540, 420)
        self._build_ui()
        self._center()
        # Keep window on top until user moves focus away
        self.attributes("-topmost", True)
        self.after(3000, lambda: self.attributes("-topmost", False))

    def _center(self):
        self.update_idletasks()
        w, h = 600, 520
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}

        # ── URL (required) ──
        tk.Label(self, text="URL источника(ов)", anchor="w").pack(fill="x", **pad)
        self.url_var = tk.StringVar()
        url_entry = tk.Entry(self, textvariable=self.url_var, font=("Consolas", 10))
        url_entry.pack(fill="x", padx=10, pady=(0, 4))
        url_entry.bind("<Control-v>", lambda e: self.after(10, self._try_paste_multi))
        url_entry.focus()

        # hint
        tk.Label(
            self,
            text="Несколько ссылок — через пробел",
            fg="grey", font=("Segoe UI", 8), anchor="w",
        ).pack(fill="x", padx=10)

        # ── Row: length + note ──
        row = tk.Frame(self)
        row.pack(fill="x", **pad)

        tk.Label(row, text="Длина (мин)").pack(side="left")
        self.length_var = tk.StringVar()
        tk.Entry(row, textvariable=self.length_var, width=5).pack(side="left", padx=(4, 20))

        tk.Label(row, text="Указания").pack(side="left")
        self.note_var = tk.StringVar()
        tk.Entry(row, textvariable=self.note_var).pack(side="left", fill="x", expand=True, padx=(4, 0))

        # ── Inserts ──
        tk.Label(self, text="Вставки с YouTube (ссылки через пробел)", anchor="w").pack(fill="x", **pad)
        self.inserts_var = tk.StringVar()
        tk.Entry(self, textvariable=self.inserts_var, font=("Consolas", 10)).pack(
            fill="x", padx=10, pady=(0, 6)
        )

        # ── Generate button ──
        self.btn = tk.Button(
            self,
            text="  Генерировать сценарий  ",
            command=self._run,
            bg="#1a73e8", fg="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2",
            padx=10, pady=6,
        )
        self.btn.pack(pady=(2, 8))

        # ── Log output ──
        tk.Label(self, text="Вывод агента", anchor="w").pack(fill="x", padx=10)
        self.log = scrolledtext.ScrolledText(
            self, state="disabled", font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
        )
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Status bar
        self.status_var = tk.StringVar(value="Готов")
        tk.Label(self, textvariable=self.status_var, anchor="w", fg="grey").pack(
            fill="x", padx=10, pady=(0, 4)
        )

    def _try_paste_multi(self):
        """If clipboard has multiple lines, join them with spaces."""
        try:
            text = self.clipboard_get().strip().replace("\n", " ").replace("\r", "")
            self.url_var.set(text)
        except Exception:
            pass

    def _log_clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def _run(self):
        urls_raw = self.url_var.get().strip()
        if not urls_raw:
            self.status_var.set("Введи хотя бы один URL")
            return

        self._log_clear()
        self.btn.configure(state="disabled", text="  Генерирую...  ")
        self.status_var.set("Агент работает...")

        # Redirect print output to the log widget
        sys.stdout = _LogRedirect(self.log)
        sys.stderr = _LogRedirect(self.log)

        urls = urls_raw.split()
        length_raw = self.length_var.get().strip()
        length_min = int(length_raw) if length_raw.isdigit() else None
        inserts_raw = self.inserts_var.get().strip()
        inserts = inserts_raw.split() if inserts_raw else None
        note = self.note_var.get().strip() or None

        def worker():
            try:
                # Import here so dotenv loads relative to script_agent dir
                import importlib.util, os
                agent_path = Path(__file__).parent / "script_agent.py"
                spec = importlib.util.spec_from_file_location("script_agent", agent_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.generate_script(urls, length_min=length_min, inserts=inserts, note=note)
                self.after(0, lambda: self.status_var.set("Готово"))
            except Exception as e:
                print(f"\n[ОШИБКА] {e}")
                self.after(0, lambda: self.status_var.set(f"Ошибка: {e}"))
            finally:
                self.after(0, lambda: self.btn.configure(
                    state="normal", text="  Генерировать сценарий  "
                ))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
