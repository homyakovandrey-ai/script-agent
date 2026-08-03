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

if sys.stdout is not None and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG_FILE = Path(__file__).parent / "output" / "last_run_log.txt"


# ── Stdout redirect to a log widget ───────────────────────────────────────────

class _LogRedirect:
    def __init__(self, widget: scrolledtext.ScrolledText, log_file=None):
        self._w = widget
        self._log_file = log_file
        self.encoding = "utf-8"

    def write(self, text: str):
        self._w.configure(state="normal")
        self._w.insert(tk.END, text)
        self._w.see(tk.END)
        self._w.configure(state="disabled")
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass

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


def _bind_paste(widget: tk.Text):
    def _do_paste():
        try:
            text = widget.clipboard_get()
        except tk.TclError:
            return
        if widget.tag_ranges("sel"):
            widget.delete("sel.first", "sel.last")
        widget.insert(tk.INSERT, text)

    def _paste(event):
        widget.after(10, _do_paste)
        return "break"

    widget.bind("<Control-v>", _paste)
    widget.bind("<Control-V>", _paste)
    widget.bind("<<Paste>>", _paste)


def _paste_button(parent, widget: tk.Text) -> tk.Button:
    def _click():
        try:
            text = widget.clipboard_get()
        except tk.TclError:
            return
        widget.insert(tk.END, text.strip() + "\n")

    return tk.Button(parent, text="Вставить", command=_click,
                     font=("Segoe UI", 9), relief="flat",
                     bg="#e8eaf6", cursor="hand2", padx=6, pady=2)


# ── Tab 1: Сценарий ────────────────────────────────────────────────────────────

def build_script_tab(nb: ttk.Notebook):
    frame = ttk.Frame(nb)
    nb.add(frame, text="  Сценарий  ")

    pad = {"padx": 10, "pady": 4}

    hdr = tk.Frame(frame)
    hdr.pack(fill="x", padx=10, pady=(4, 0))
    tk.Label(hdr, text="Ссылки на источники (по одной на строку)", anchor="w").pack(side="left")
    url_frame = tk.Frame(frame)
    url_frame.pack(fill="both", padx=10, pady=(2, 0))
    url_scroll = tk.Scrollbar(url_frame)
    url_scroll.pack(side="right", fill="y")
    url_text = tk.Text(url_frame, height=12, font=("Consolas", 10), wrap="none",
                       yscrollcommand=url_scroll.set)
    url_text.pack(side="left", fill="both", expand=True)
    url_scroll.config(command=url_text.yview)
    _bind_paste(url_text)
    _paste_button(hdr, url_text).pack(side="right")
    url_text.focus()

    check_row = tk.Frame(frame)
    check_row.pack(fill="x", padx=10, pady=(2, 4))
    check_btn = tk.Button(
        check_row, text="Проверить ссылки", command=lambda: check_links(),
        font=("Segoe UI", 9, "bold"), bg="#e8e8e8", relief="flat",
        padx=8, cursor="hand2",
    )
    check_btn.pack(side="left")
    check_status_var = tk.StringVar()
    tk.Label(check_row, textvariable=check_status_var, fg="grey", font=("Segoe UI", 8)).pack(
        side="left", padx=(8, 0)
    )

    row = tk.Frame(frame)
    row.pack(fill="x", **pad)
    tk.Label(row, text="Длина (мин)").pack(side="left")
    length_var = tk.StringVar()
    tk.Entry(row, textvariable=length_var, width=5).pack(side="left", padx=(4, 0))

    note_hdr = tk.Frame(frame)
    note_hdr.pack(fill="x", padx=10, pady=(6, 0))
    tk.Label(note_hdr, text="ТЗ / Указания агенту (всё написанное будет строго исполнено)",
             anchor="w", font=("Segoe UI", 9, "bold")).pack(side="left")
    note_frame = tk.Frame(frame)
    note_frame.pack(fill="both", padx=10, pady=(2, 4))
    note_scroll = tk.Scrollbar(note_frame)
    note_scroll.pack(side="right", fill="y")
    note_text = tk.Text(note_frame, height=6, font=("Consolas", 10), wrap="word",
                        yscrollcommand=note_scroll.set)
    note_text.pack(side="left", fill="both", expand=True)
    note_scroll.config(command=note_text.yview)
    _bind_paste(note_text)
    _paste_button(note_hdr, note_text).pack(side="right")

    tk.Label(frame, text="Вставки с YouTube (через пробел)", anchor="w").pack(fill="x", **pad)
    inserts_var = tk.StringVar()
    _url_entry(frame, inserts_var).pack(fill="x", padx=10, pady=(0, 6))

    manual_header = tk.Frame(frame)
    manual_header.pack(fill="x", padx=10, pady=(4, 2))
    tk.Label(manual_header, text="Материалы вручную (если ссылка не открывается)", anchor="w").pack(side="left")
    manual_frame = tk.Frame(frame)
    manual_frame.pack(fill="both", padx=10, pady=(0, 2))
    manual_scroll = tk.Scrollbar(manual_frame)
    manual_scroll.pack(side="right", fill="y")
    manual_text = tk.Text(manual_frame, height=6, font=("Consolas", 10), wrap="word",
                          yscrollcommand=manual_scroll.set)
    manual_text.pack(side="left", fill="both", expand=True)
    manual_scroll.config(command=manual_text.yview)
    _bind_paste(manual_text)
    _paste_button(manual_header, manual_text).pack(side="right")
    tk.Label(
        frame,
        text="Перед текстом статьи укажи строку «URL: ссылка», для нескольких ссылок повтори блок:\n"
             "URL: https://ссылка\nтекст статьи",
        justify="left", fg="grey", font=("Segoe UI", 8), anchor="w",
    ).pack(fill="x", padx=10, pady=(0, 6))

    log = _make_log(frame)
    status_var = tk.StringVar(value="Готов")
    _stop_event = threading.Event()

    def check_links():
        urls_raw = url_text.get("1.0", tk.END).strip()
        if not urls_raw:
            status_var.set("Введи хотя бы один URL")
            return
        _clear_log(log)
        check_btn.configure(state="disabled", text="  Проверяю...  ")
        check_status_var.set("")
        status_var.set("Проверяю ссылки...")
        redirector = _LogRedirect(log)
        sys.stdout = redirector
        sys.stderr = redirector

        urls = urls_raw.split()

        def worker():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "script_agent", Path(__file__).parent / "script_agent.py"
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                ok_count = 0
                blocked = []
                for u in urls:
                    print(f"[*] {u}")
                    ok, preview = mod.check_source(u)
                    if ok:
                        ok_count += 1
                        print(f"    OK -> {preview}\n")
                    else:
                        blocked.append(u)
                        print(f"    НЕ ЧИТАЕТСЯ -> {preview}\n")

                print(f"[ИТОГ] Доступно: {ok_count}/{len(urls)}")
                if blocked:
                    print("Заполни «Материалы вручную» для:")
                    for u in blocked:
                        print(f"  {u}")

                    existing = manual_text.get("1.0", tk.END)
                    additions = "".join(
                        f"URL: {u}\n\n" for u in blocked if f"URL: {u}" not in existing
                    )
                    if additions:
                        prefix = "\n" if existing.strip() else ""
                        frame.after(0, lambda a=additions, p=prefix: manual_text.insert(tk.END, p + a))

                frame.after(0, lambda: check_status_var.set(f"Доступно: {ok_count}/{len(urls)}"))
                frame.after(0, lambda: status_var.set("Проверка завершена"))
            except Exception as e:
                msg = str(e)
                print(f"\n[ОШИБКА] {msg}")
                frame.after(0, lambda m=msg: status_var.set(f"Ошибка: {m}"))
            finally:
                frame.after(0, lambda: check_btn.configure(
                    state="normal", text="  Проверить ссылки  "
                ))

        threading.Thread(target=worker, daemon=True).start()

    def run():
        urls_raw = url_text.get("1.0", tk.END).strip()
        if not urls_raw:
            status_var.set("Введи хотя бы один URL")
            return
        _clear_log(log)
        _stop_event.clear()
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text("", encoding="utf-8")
        btn.configure(state="disabled", text="  Генерирую...  ")
        stop_btn.configure(state="normal")
        status_var.set("Агент работает...")
        redirector = _LogRedirect(log, LOG_FILE)
        sys.stdout = redirector
        sys.stderr = redirector

        urls = urls_raw.split()
        length_raw = length_var.get().strip()
        length_min = int(length_raw) if length_raw.isdigit() else None
        inserts_raw = inserts_var.get().strip()
        inserts = inserts_raw.split() if inserts_raw else None
        note = note_text.get("1.0", tk.END).strip() or None
        manual_materials_raw = manual_text.get("1.0", tk.END)

        def worker():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "script_agent", Path(__file__).parent / "script_agent.py"
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.generate_script(
                    urls, length_min=length_min, inserts=inserts,
                    note=note, manual_materials_raw=manual_materials_raw,
                    stop_event=_stop_event,
                )
                if _stop_event.is_set():
                    frame.after(0, lambda: status_var.set(
                        f"Остановлено. Лог: {LOG_FILE}"
                    ))
                else:
                    frame.after(0, lambda: status_var.set("Готово"))
            except Exception as e:
                print(f"\n[ОШИБКА] {e}")
                frame.after(0, lambda: status_var.set(f"Ошибка: {e}"))
            finally:
                frame.after(0, lambda: (
                    btn.configure(state="normal", text="  Генерировать сценарий  "),
                    stop_btn.configure(state="disabled"),
                ))

        threading.Thread(target=worker, daemon=True).start()

    def stop():
        _stop_event.set()
        stop_btn.configure(state="disabled")
        print(f"\n[!] Остановлено пользователем.\n[!] Лог сохранён: {LOG_FILE}")

    btn_row = tk.Frame(frame)
    btn_row.pack(pady=(2, 6))

    btn = tk.Button(
        btn_row, text="  Генерировать сценарий  ", command=run,
        bg="#1a73e8", fg="white", font=("Segoe UI", 11, "bold"),
        relief="flat", cursor="hand2", padx=10, pady=6,
    )
    btn.pack(side="left", padx=(0, 6))

    stop_btn = tk.Button(
        btn_row, text="  Стоп  ", command=stop,
        bg="#d32f2f", fg="white", font=("Segoe UI", 11, "bold"),
        relief="flat", cursor="hand2", padx=10, pady=6,
        state="disabled",
    )
    stop_btn.pack(side="left")

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

    hdr2 = tk.Frame(frame)
    hdr2.pack(fill="x", padx=10, pady=(4, 0))
    tk.Label(hdr2, text="Ссылки (по одной на строку)", anchor="w").pack(side="left")
    url_frame = tk.Frame(frame)
    url_frame.pack(fill="both", padx=10, pady=(2, 6))
    url_scroll = tk.Scrollbar(url_frame)
    url_scroll.pack(side="right", fill="y")
    url_text = tk.Text(url_frame, height=12, font=("Consolas", 10), wrap="none",
                       yscrollcommand=url_scroll.set)
    url_text.pack(side="left", fill="both", expand=True)
    url_scroll.config(command=url_text.yview)
    _bind_paste(url_text)
    _paste_button(hdr2, url_text).pack(side="right")

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
        urls_raw = url_text.get("1.0", tk.END).strip()
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
        self.minsize(560, 780)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        build_script_tab(nb)
        build_ingest_tab(nb)

        w, h = 620, 880
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.attributes("-topmost", True)
        self.after(3000, lambda: self.attributes("-topmost", False))


if __name__ == "__main__":
    App().mainloop()
