#!/usr/bin/env python3
"""
GUI launcher — two tabs:
  1. Сценарий  — generate YouTube script from news URL
  2. База знаний — save interesting material without generating a script
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── Stdout redirect to a log widget ───────────────────────────────────────────

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


# ── Reusable helpers ───────────────────────────────────────────────────────────

def _make_log(parent) -> scrolledtext.ScrolledText:
    log = scrolledtext.ScrolledText(
        parent, state="disabled", font=("Consolas", 9),
        bg="#1e1e1e", fg="#d4d4d4",
    )
    return log


def _clear_log(log: scrolledtext.ScrolledText):
    log.configure(state="normal")
    log.delete("1.0", tk.END)
    log.configure(state="disabled")


def _url_entry(parent, var: tk.StringVar) -> tk.Entry:
    e = tk.Entry(parent, textvariable=var, font=("Consolas", 10))
    e.bind("<Control-v>", lambda ev: e.after(10, lambda: var.set(
        e.clipboard_get().strip().replace("\n", " ").replace("\r", "")
    )))
    return e


# ── Tab 1: Сценарий ────────────────────────────────────────────────────────────

def build_script_tab(nb: ttk.Notebook):
    frame = ttk.Frame(nb)
    nb.add(frame, text="  Сценарий  ")

    pad = {"padx": 10, "pady": 4}

    tk.Label(frame, text="URL источника(ов)", anchor="w").pack(fill="x", **pad)
    url_var = tk.StringVar()
    entry = _url_entry(frame, url_var)
    entry.pack(fill="x", padx=10, pady=(0, 2))
    entry.focus()
    tk.Label(frame, text="Несколько ссылок — через пробел", fg="grey",
             font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=10)

    row = tk.Frame(frame)
    row.pack(fill="x", **pad)
    tk.Label(row, text="Длина (мин)").pack(side="left")
    length_var = tk.StringVar()
    tk.Entry(row, textvariable=length_var, width=5).pack(side="left", padx=(4, 20))
    tk.Label(row, text="Указания").pack(side="left")
    note_var = tk.StringVar()
    tk.Entry(row, textvariable=note_var).pack(side="left", fill="x", expand=True, padx=(4, 0))

    tk.Label(frame, text="Вставки с YouTube (через пробел)", anchor="w").pack(fill="x", **pad)
    inserts_var = tk.StringVar()
    _url_entry(frame, inserts_var).pack(fill="x", padx=10, pady=(0, 6))

    log = _make_log(frame)
    status_var = tk.StringVar(value="Готов")

    def run():
        urls_raw = url_var.get().strip()
        if not urls_raw:
            status_var.set("Введи хотя бы один URL")
            return
        _clear_log(log)
        btn.configure(state="disabled", text="  Генерирую...  ")
        status_var.set("Агент работает...")
        sys.stdout = _LogRedirect(log)
        sys.stderr = _LogRedirect(log)

        urls = urls_raw.split()
        length_raw = length_var.get().strip()
        length_min = int(length_raw) if length_raw.isdigit() else None
        inserts_raw = inserts_var.get().strip()
        inserts = inserts_raw.split() if inserts_raw else None
        note = note_var.get().strip() or None

        def worker():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "script_agent", Path(__file__).parent / "script_agent.py"
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.generate_script(urls, length_min=length_min, inserts=inserts, note=note)
                frame.after(0, lambda: status_var.set("Готово"))
            except Exception as e:
                print(f"\n[ОШИБКА] {e}")
                frame.after(0, lambda: status_var.set(f"Ошибка: {e}"))
            finally:
                frame.after(0, lambda: btn.configure(
                    state="normal", text="  Генерировать сценарий  "
                ))

        threading.Thread(target=worker, daemon=True).start()

    btn = tk.Button(
        frame, text="  Генерировать сценарий  ", command=run,
        bg="#1a73e8", fg="white", font=("Segoe UI", 11, "bold"),
        relief="flat", cursor="hand2", padx=10, pady=6,
    )
    btn.pack(pady=(2, 6))

    tk.Label(frame, text="Вывод агента", anchor="w").pack(fill="x", padx=10)
    log.pack(fill="both", expand=True, padx=10, pady=(0, 6))
    tk.Label(frame, textvariable=status_var, anchor="w", fg="grey").pack(
        fill="x", padx=10, pady=(0, 4)
    )

    return frame


# ── Tab 2: База знаний ─────────────────────────────────────────────────────────

def build_ingest_tab(nb: ttk.Notebook):
    frame = ttk.Frame(nb)
    nb.add(frame, text="  База знаний  ")

    pad = {"padx": 10, "pady": 4}

    tk.Label(
        frame,
        text="Вставь ссылки на материалы, которые хочешь сохранить.\nАгент прочитает их и создаст структурированные заметки в Obsidian.",
        justify="left", fg="#555",
    ).pack(fill="x", padx=10, pady=(10, 4))

    tk.Label(frame, text="URL(s) — через пробел", anchor="w").pack(fill="x", **pad)
    url_var = tk.StringVar()
    entry = _url_entry(frame, url_var)
    entry.pack(fill="x", padx=10, pady=(0, 6))

    row = tk.Frame(frame)
    row.pack(fill="x", **pad)
    tk.Label(row, text="Комментарий (опционально)").pack(side="left")
    note_var = tk.StringVar()
    tk.Entry(row, textvariable=note_var).pack(
        side="left", fill="x", expand=True, padx=(8, 0)
    )

    log = _make_log(frame)
    status_var = tk.StringVar(value="Готов")

    def run():
        urls_raw = url_var.get().strip()
        if not urls_raw:
            status_var.set("Введи хотя бы один URL")
            return
        _clear_log(log)
        btn.configure(state="disabled", text="  Сохраняю...  ")
        status_var.set("Агент обрабатывает материалы...")
        sys.stdout = _LogRedirect(log)
        sys.stderr = _LogRedirect(log)

        urls = urls_raw.split()
        note = note_var.get().strip() or None

        def worker():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "ingest", Path(__file__).parent / "ingest.py"
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.ingest(urls, note=note)
                frame.after(0, lambda: status_var.set("Сохранено в базу знаний"))
            except Exception as e:
                print(f"\n[ОШИБКА] {e}")
                frame.after(0, lambda: status_var.set(f"Ошибка: {e}"))
            finally:
                frame.after(0, lambda: btn.configure(
                    state="normal", text="  Сохранить в базу знаний  "
                ))

        threading.Thread(target=worker, daemon=True).start()

    btn = tk.Button(
        frame, text="  Сохранить в базу знаний  ", command=run,
        bg="#2e7d32", fg="white", font=("Segoe UI", 11, "bold"),
        relief="flat", cursor="hand2", padx=10, pady=6,
    )
    btn.pack(pady=(6, 6))

    tk.Label(frame, text="Вывод", anchor="w").pack(fill="x", padx=10)
    log.pack(fill="both", expand=True, padx=10, pady=(0, 6))
    tk.Label(frame, textvariable=status_var, anchor="w", fg="grey").pack(
        fill="x", padx=10, pady=(0, 4)
    )

    return frame


# ── Main window ────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Убиваю БПМ — Агент")
        self.minsize(560, 480)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        build_script_tab(nb)
        build_ingest_tab(nb)

        w, h = 620, 560
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.attributes("-topmost", True)
        self.after(3000, lambda: self.attributes("-topmost", False))


if __name__ == "__main__":
    App().mainloop()
