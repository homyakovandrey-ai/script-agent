#!/usr/bin/env python3
"""
ingest.py — fetch URLs and save as structured knowledge-base notes in Obsidian.
Usage: python ingest.py URL [URL2 ...] [--note "context"]
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import anthropic
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_PATH = Path(os.getenv("KNOWLEDGE_PATH", "./knowledge"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-opus-4-7"

# ── Fetch ──────────────────────────────────────────────────────────────────────

YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*?v=|shorts/)|youtu\.be/)[\w-]+",
    re.IGNORECASE,
)


def _parse_vtt(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if re.match(r"^[\d:\.]+\s*-->\s*[\d:\.]+", line):
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)
    result, prev = [], None
    for ln in lines:
        if ln != prev:
            result.append(ln)
            prev = ln
    return "\n".join(result)


def fetch_youtube_transcript(url: str) -> str:
    try:
        import yt_dlp
    except ImportError:
        return "yt-dlp не установлен. Запусти: pip install yt-dlp"
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return f"Ошибка yt-dlp {url}: {e}"
    title = info.get("title", "")
    duration = info.get("duration") or 0
    header = f"[YouTube] {title} ({duration // 60}:{duration % 60:02d})\n"
    subtitles = info.get("subtitles") or {}
    auto_caps = info.get("automatic_captions") or {}
    sub_url = lang_used = None
    for lang in ("ru", "en"):
        for source in (subtitles, auto_caps):
            if lang not in source:
                continue
            entries = source[lang]
            for entry in entries:
                if entry.get("ext") == "vtt":
                    sub_url, lang_used = entry["url"], lang
                    break
            if not sub_url and entries:
                sub_url, lang_used = entries[0]["url"], lang
            if sub_url:
                break
        if sub_url:
            break
    if not sub_url:
        desc = (info.get("description") or "")[:800]
        return header + f"(субтитры недоступны)\n\nОписание:\n{desc}"
    try:
        resp = httpx.get(sub_url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        transcript = _parse_vtt(resp.text)
    except Exception as e:
        return header + f"(ошибка субтитров: {e})"
    result = header + f"Транскрипт ({lang_used}):\n\n{transcript}"
    if len(result) > 12_000:
        result = result[:12_000] + "\n\n[... обрезано ...]"
    return result


def fetch_url(url: str) -> str:
    if YOUTUBE_RE.search(url):
        return fetch_youtube_transcript(url)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.body
        raw_text = (main or soup).get_text(separator="\n", strip=True)
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        text = "\n".join(lines)
        if len(text) > 10_000:
            text = text[:10_000] + "\n\n[... обрезано ...]"
        return text or "Не удалось извлечь текст."
    except Exception as e:
        return f"Ошибка загрузки {url}: {e}"


# ── Save ───────────────────────────────────────────────────────────────────────

def save_to_knowledge(filename: str, content: str) -> str:
    try:
        KNOWLEDGE_PATH.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in filename if c not in r'\/:*?"<>|').strip()
        if not safe_name:
            safe_name = f"material-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}"
        filepath = KNOWLEDGE_PATH / f"{safe_name}.md"
        filepath.write_text(content, encoding="utf-8")
        return f"Сохранено: {filepath}"
    except Exception as e:
        return f"Ошибка сохранения: {e}"


# ── Tools ──────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "fetch_url",
        "description": "Загружает текст веб-страницы или транскрипт YouTube-видео.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "save_to_knowledge",
        "description": "Сохраняет заметку в базу знаний. Вызывай когда заметка полностью готова.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Имя файла без расширения, формат: YYYY-MM-DD Название",
                },
                "content": {
                    "type": "string",
                    "description": "Полное содержимое заметки в markdown",
                },
            },
            "required": ["filename", "content"],
        },
    },
]


def run_tool(name: str, inputs: dict) -> str:
    if name == "fetch_url":
        return fetch_url(inputs["url"])
    if name == "save_to_knowledge":
        return save_to_knowledge(inputs["filename"], inputs["content"])
    return f"Неизвестный инструмент: {name}"


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — помощник, который формирует базу знаний для YouTube-канала «Убиваю БПМ» (российский и мировой хип-хоп, рэп-культура).

## ЗАДАЧА
Получаешь ссылки на материалы (новости, статьи, YouTube-видео). Для каждого источника:
1. Загрузи через fetch_url
2. Составь структурированную заметку
3. Сохрани через save_to_knowledge

## ФОРМАТ ЗАМЕТКИ

---
title: "Точное название материала"
date: YYYY-MM-DD
source: URL
tags:
  - персона или тема
type: материал
---

# Название

**Источник:** [домен](URL)
**Дата:** YYYY-MM-DD

## Ключевые факты

- Конкретный факт с именами и цифрами
- ...

## Контекст

2–3 абзаца: что произошло, почему важно для рэп-индустрии, что это означает.

## ПРАВИЛА
- Только факты из источника, без домыслов
- Имя файла: YYYY-MM-DD Краткое название (без спецсимволов)
- По одной заметке на каждый источник
- Теги — конкретные персоны и темы"""


# ── Agent loop ─────────────────────────────────────────────────────────────────

def ingest(urls: list[str], note: str | None = None) -> None:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print(f"\n[>] Источников: {len(urls)}")
    for u in urls:
        print(f"    {u}")

    user_msg = "Сохрани эти материалы в базу знаний:\n"
    for u in urls:
        user_msg += f"  {u}\n"
    if note:
        user_msg += f"\nКонтекст: {note}"

    messages = [{"role": "user", "content": user_msg}]
    print("\n[AI] Обрабатываю...\n" + "─" * 60)

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                if (
                    hasattr(event, "type")
                    and event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    print(event.delta.text, end="", flush=True)
            response = stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            print("\n" + "─" * 60)
            break

        if response.stop_reason == "tool_use":
            print()
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                short_input = json.dumps(block.input, ensure_ascii=False)
                if len(short_input) > 120:
                    short_input = short_input[:120] + "…"
                print(f"\n[tool] {block.name}({short_input})")
                result = run_tool(block.name, block.input)
                if block.name == "save_to_knowledge":
                    print(f"[OK] {result}")
                else:
                    preview = result[:200].replace("\n", " ")
                    print(f"    -> {preview}{'...' if len(result) > 200 else ''}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            print()
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    print("\n[OK] Готово.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if not ANTHROPIC_API_KEY:
        print("Ошибка: не задан ANTHROPIC_API_KEY.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Ingest materials into knowledge base")
    parser.add_argument("urls", nargs="+", metavar="URL")
    parser.add_argument("--note", metavar="TEXT", help="Дополнительный контекст")
    args = parser.parse_args()

    ingest(args.urls, note=args.note)


if __name__ == "__main__":
    main()
