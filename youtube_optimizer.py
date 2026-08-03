#!/usr/bin/env python3
"""
youtube_optimizer.py — YouTube title + thumbnail brief generator
Analyses competitors, then produces 3 title options + thumbnail brief.

Usage:
    python youtube_optimizer.py
    python youtube_optimizer.py --topic "рэп баттлы" --transcript transcript.txt
"""

import os
import sys
import json
import re
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

if sys.stdout is not None and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import anthropic
import httpx
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-opus-4-7"

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — эксперт по YouTube-оптимизации: CTR-стратег, аналитик конкурентов, специалист по психологии заголовков и дизайну превью.

## КОМПЕТЕНЦИИ
- Психология заголовков: curiosity gap, числа и конкретика, эмоциональные триггеры, срочность, провокация
- Анализ конкурентов: паттерны успешных названий, формулы превью, тренды ниши
- Дизайн превью: композиция, цветовые контрасты, типографика, крючки внимания за 0.5 секунды
- CTR-оптимизация: соответствие названия и превью, A/B логика вариантов

## АЛГОРИТМ (строго по порядку)

1. Прочитай расшифровку — найди: главная тема, главный конфликт/интрига, ключевые слова, эмоция
2. Составь 2-3 точных поисковых запроса для YouTube (ищи похожие видео)
3. Выполни web_search для каждого запроса
4. Из результатов выбери 4-6 YouTube-ссылок на конкурирующие видео с высокими просмотрами
5. Для каждой ссылки вызови get_video_metadata чтобы получить реальные данные
6. Проанализируй паттерны: формулы заголовков, частые слова, структура успешных видео
7. Сформируй финальный результат в точном формате ниже

## ФОРМАТ ВЫВОДА (обязателен, строго соблюдать — все секции обязательны)

---

## АНАЛИЗ КОНКУРЕНТОВ

**Проанализировано видео:** [N]
**Паттерны заголовков:** [конкретные формулы — что повторяется у успешных видео]
**Паттерны превью:** [визуальные приёмы — лица, текст, цвета, композиция]
**Ключевые слова ниши:** [топ-слова из заголовков конкурентов]
**Топ конкурент:** [название видео] — [количество просмотров] просмотров

---

## РЕФЕРЕНСЫ ПРЕВЬЮ КОНКУРЕНТОВ

Для каждого из 3-5 топовых видео (которые ты проанализировал через get_video_metadata) — извлеки video_id из URL и сформируй блок. URL превью строится так: https://img.youtube.com/vi/{video_id}/maxresdefault.jpg

### Референс 1: [Название видео]
**URL превью:** https://img.youtube.com/vi/{video_id}/maxresdefault.jpg
**Просмотры:** [число]
**Что работает:**
- [конкретный визуальный приём]
- [конкретный визуальный приём]
**Что не работает:**
- [слабое место превью]

### Референс 2: [Название видео]
**URL превью:** https://img.youtube.com/vi/{video_id}/maxresdefault.jpg
**Просмотры:** [число]
**Что работает:**
- [приём]
**Что не работает:**
- [слабое место]

[и т.д. для 3-5 видео]

---

## НАЗВАНИЯ (3 варианта)

### Вариант 1: [ЗАГОЛОВОК]
**CTR-потенциал:** ★★★★★
**Почему сработает:** [1-2 предложения с конкретной аргументацией]
**Формула:** [curiosity gap / число + результат / провокация / социальное доказательство / и т.д.]

### Вариант 2: [ЗАГОЛОВОК]
**CTR-потенциал:** ★★★★☆
**Почему сработает:** [1-2 предложения]
**Формула:** [...]

### Вариант 3: [ЗАГОЛОВОК]
**CTR-потенциал:** ★★★★☆
**Почему сработает:** [1-2 предложения]
**Формула:** [...]

---

## ТЗ НА ПРЕВЬЮ (формат Nano Banana)

**Стратегия:** [1-2 предложения — какую эмоцию вызывает превью за 0.5 сек и почему зритель кликнет]

**Промпт для Nano Banana:**

```
[Полный готовый промпт на русском языке в формате Nano Banana Pro.
Писать естественным языком, полными предложениями — как инструктаж живому художнику.
НЕ использовать "tag soup" (перечисление через запятую без контекста).

Структура промпта (всё в одном тексте):
1. Главный субъект и его эмоция: точное описание человека/объекта + конкретная эмоция (шок, триумф, удивление, уверенность)
2. Композиция: расположение элементов, кадрирование (крупный план лица, половина кадра слева — человек, справа — текст и т.д.)
3. Фон и цвет: конкретный цвет фона + контрастный подход (жёлтый/фиолетовый, красный/циан, оранжевый/синий)
4. Освещение и стиль: студийный свет, яркий, насыщенный, YouTube thumbnail style
5. Технические параметры: 16:9, 1280x720

В конце отдельной строкой — инструкция по тексту:
Добавь на превью текст: "[ТЕКСТ ЗАГЛАВНЫМИ БУКВАМИ, 1-3 СЛОВА]" — [расположение на холсте, цвет, размер]
]
```

---"""

# ── Tools ──────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
    },
    {
        "name": "get_video_metadata",
        "description": (
            "Извлекает метаданные YouTube-видео через yt-dlp: заголовок, описание (первые 800 символов), "
            "теги, количество просмотров, лайки, дату публикации, название канала. "
            "Вызывай после web_search для каждого найденного конкурирующего видео."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Полный URL YouTube-видео (https://www.youtube.com/watch?v=...)",
                }
            },
            "required": ["url"],
        },
    },
]

# ── yt-dlp tool ────────────────────────────────────────────────────────────────

def get_video_metadata(url: str) -> dict:
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        if result.returncode != 0:
            return {"error": result.stderr[:400] or "yt-dlp returned non-zero exit code"}
        data = json.loads(result.stdout)
        return {
            "title": data.get("title"),
            "description": (data.get("description") or "")[:800],
            "tags": (data.get("tags") or [])[:20],
            "view_count": data.get("view_count"),
            "like_count": data.get("like_count"),
            "upload_date": data.get("upload_date"),
            "channel": data.get("channel"),
            "duration_seconds": data.get("duration"),
        }
    except subprocess.TimeoutExpired:
        return {"error": "Timeout: yt-dlp не ответил за 30 секунд"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}
    except FileNotFoundError:
        return {"error": "yt-dlp не найден — установи: pip install yt-dlp"}
    except Exception as e:
        return {"error": str(e)}


def run_tool(name: str, inputs: dict) -> str:
    if name == "get_video_metadata":
        result = get_video_metadata(inputs["url"])
        return json.dumps(result, ensure_ascii=False, indent=2)
    return f"Неизвестный инструмент: {name}"


def generate_pdf(text: str, topic: str, output_dir: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^\w\-]", "_", topic[:40]) if topic else "result"
    out_path = output_dir / f"optimizer_{slug}_{ts}.pdf"

    # ── Register Cyrillic font ──────────────────────────────────────────────────
    font_paths = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/ArialUnicodeMS.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    font_name = "Arial"
    for fp in font_paths:
        if fp.exists():
            pdfmetrics.registerFont(TTFont(font_name, str(fp)))
            break
    else:
        font_name = "Helvetica"

    bold_font = font_name + "-Bold" if font_name == "Helvetica" else font_name
    # For TTF we register a bold variant if available
    bold_path = Path("C:/Windows/Fonts/arialbd.ttf")
    if font_name != "Helvetica" and bold_path.exists():
        pdfmetrics.registerFont(TTFont(font_name + "Bold", str(bold_path)))
        bold_font = font_name + "Bold"

    # ── Styles ─────────────────────────────────────────────────────────────────
    base_styles = getSampleStyleSheet()
    normal = base_styles["Normal"]

    def S(name, **kw):
        if "fontName" not in kw:
            kw["fontName"] = font_name
        return ParagraphStyle(name, parent=normal, **kw)

    h1 = S("H1", fontSize=18, leading=24, spaceAfter=6, textColor=colors.HexColor("#0F1B3D"),
           fontName=bold_font)
    h2 = S("H2", fontSize=14, leading=20, spaceBefore=14, spaceAfter=4,
           textColor=colors.HexColor("#1E40AF"), fontName=bold_font)
    h3 = S("H3", fontSize=12, leading=17, spaceBefore=10, spaceAfter=3,
           textColor=colors.HexColor("#2563EB"), fontName=bold_font)
    body = S("Body", fontSize=10, leading=15, spaceAfter=4)
    small = S("Small", fontSize=9, leading=13, spaceAfter=2, textColor=colors.HexColor("#6B7280"))
    hr_color = colors.HexColor("#CBD5E1")

    def safe(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def md_inline(s):
        s = safe(s)
        s = re.sub(r"\*\*(.+?)\*\*", rf'<b>\1</b>', s)
        s = re.sub(r"\*(.+?)\*", rf'<i>\1</i>', s)
        return s

    story = []
    story.append(Paragraph("YouTube Optimizer — Результат", h1))
    if topic:
        story.append(Paragraph(f"Тема: {safe(topic)}", small))
    story.append(Paragraph(datetime.now().strftime("%d.%m.%Y %H:%M"), small))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=hr_color))
    story.append(Spacer(1, 4 * mm))

    lines = text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 2 * mm))
            continue
        if stripped.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            story.append(Spacer(1, 2 * mm))
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(md_inline(stripped[4:]), h3))
        elif stripped.startswith("## "):
            story.append(Paragraph(md_inline(stripped[3:]), h2))
        elif stripped.startswith("# "):
            story.append(Paragraph(md_inline(stripped[2:]), h1))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph("• " + md_inline(stripped[2:]), body))
        else:
            story.append(Paragraph(md_inline(stripped), body))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    doc.build(story)
    return out_path

# ── Agent loop ─────────────────────────────────────────────────────────────────

def optimize(transcript: str, topic: str = "", output_dir: Path | None = None) -> None:
    http_client = httpx.Client(trust_env=False)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http_client)
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "output"
    collected_text: list[str] = []

    topic_line = f"\nКлючевые слова / ниша: {topic}" if topic.strip() else ""
    user_msg = (
        "Проанализируй расшифровку и выполни полный алгоритм: "
        "найди конкурентов, получи их метаданные, затем сформируй названия и ТЗ на превью."
        f"{topic_line}\n\n"
        f"РАСШИФРОВКА ВИДЕО:\n{transcript}"
    )

    messages = [{"role": "user", "content": user_msg}]
    print("\n[AI] Агент работает...\n" + "─" * 60)

    while True:
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            betas=["web-search-2025-03-05"],
        ) as stream:
            for event in stream:
                if (
                    hasattr(event, "type")
                    and event.type == "content_block_delta"
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    print(event.delta.text, end="", flush=True)
                    collected_text.append(event.delta.text)
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

                # web_search and web_fetch are server-side — skip client-side execution
                if block.name in ("web_search", "web_fetch"):
                    continue

                result = run_tool(block.name, block.input)
                preview = result[:200].replace("\n", " ")
                print(f"    -> {preview}{'...' if len(result) > 200 else ''}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            if not tool_results:
                # Only server-side tools were called, nothing to send back
                break

            print()
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    full_text = "".join(collected_text)
    if full_text.strip():
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from pdf_report import build_pdf
            pdf_path = build_pdf(full_text, topic)
            if pdf_path:
                print(f"\n[PDF] Сохранён: {pdf_path}")
            else:
                print("\n[PDF] Ошибка: build_pdf вернул None")
        except Exception as e:
            print(f"\n[PDF] Ошибка генерации: {e}")
    print("\n[OK] Готово.")

# ── Input helpers ──────────────────────────────────────────────────────────────

def read_multiline_input() -> str:
    """Read multiline text until two consecutive empty lines."""
    print("Вставь расшифровку. Для завершения — нажми Enter дважды на пустой строке:\n")
    lines = []
    empty_streak = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            empty_streak += 1
            if empty_streak >= 2:
                break
            lines.append(line)
        else:
            empty_streak = 0
            lines.append(line)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if not ANTHROPIC_API_KEY:
        print("Ошибка: ANTHROPIC_API_KEY не задан.")
        print("Добавь в .env: ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="YouTube Video Optimizer — названия и ТЗ на превью из расшифровки"
    )
    parser.add_argument(
        "--topic", metavar="TEXT",
        help='Ключевые слова / ниша для поиска конкурентов, например: "рэп баттлы 2024"',
    )
    parser.add_argument(
        "--transcript", metavar="FILE",
        help="Путь к .txt файлу с расшифровкой (если не задан — интерактивный ввод)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  YouTube Video Optimizer")
    print("=" * 60)

    if args.transcript:
        path = Path(args.transcript)
        if not path.exists():
            print(f"Ошибка: файл не найден: {args.transcript}")
            sys.exit(1)
        transcript = path.read_text(encoding="utf-8").strip()
        print(f"Расшифровка: {args.transcript} ({len(transcript)} симв.)")
    else:
        print()
        transcript = read_multiline_input()

    if not transcript:
        print("Ошибка: расшифровка пуста.")
        sys.exit(1)

    topic = args.topic or ""
    if not topic:
        topic = input("\nКлючевые слова / ниша (Enter для пропуска): ").strip()

    optimize(transcript, topic)


if __name__ == "__main__":
    main()
