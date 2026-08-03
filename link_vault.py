#!/usr/bin/env python3
"""
link_vault.py — adds Obsidian wikilinks between notes.

For each key entity (artist, topic), scans every script and:
  1. Adds [[Entity]] wikilink on first mention in the body text
  2. Updates frontmatter with related: list
  3. Creates an index note for each entity listing all related scripts
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

VAULT = Path(os.getenv("VAULT_PATH", "./vault"))

# ─── Entity definitions ────────────────────────────────────────────────────────
# Format: ("Display Name for index note", "wikilink target filename", [regex patterns])
# Patterns are case-insensitive and matched against body text only.
# Use \b or word boundaries where safe. Avoid overly broad patterns.

ENTITIES = [
    # ── Russian artists ──
    ("Моргенштерн", "Моргенштерн", [
        r"моргенштерн\w*", r"\bморген[аеуомьё]\w*", r"\bморгена\b", r"\bморгену\b",
        r"\bморгеном\b", r"\bморгене\b",
    ]),
    ("Оксимирон", "Оксимирон", [
        r"оксимирон\w*", r"\bокси\b", r"\bмирон\w*\b(?= (не|и|или|в|с|на|за|от|про|об|из|к|у))",
    ]),
    ("Кизару", "Кизару", [r"кизару\w*"]),
    ("Фэйс", "Фэйс", [r"\bфэйс\w*", r"\bface\b"]),
    ("Инстасамка", "Инстасамка", [r"инстасамк\w+", r"\bсамк[ауиой]\b"]),
    ("Мэйби Бэйби", "Мэйби Бэйби", [r"мэйби\s*бэйби\w*", r"maybe\s*baby"]),
    ("Скриптонит", "Скриптонит", [r"скриптонит\w*"]),
    ("Биг Бэби Тейп", "Биг Бэби Тейп", [
        r"биг\s*бэби\s*тейп\w*", r"\bтейп[аеуомь]?\b",
    ]),
    ("Платина", "Платина", [r"\bплатин[аыуое]\b", r"\bplatina\b"]),
    ("Ганвест", "Ганвест", [r"ганвест\w*"]),
    ("Меллстрой", "Меллстрой", [r"меллстро[йяею]\w*", r"mellstroy"]),
    ("Слава КПСС", "Слава КПСС", [r"слава\s*кпсс", r"\bбукер\b"]),
    ("Фараон", "Фараон", [r"\bфараон\w*"]),
    ("Паша Техник", "Паша Техник", [r"паш[аиуе]\s*техник\w*", r"техник\w*\b"]),
    ("Скалли Милано", "Скалли Милано", [r"скалли\s*милан\w*"]),
    ("Некоглай", "Некоглай", [r"некоглай\w*"]),
    ("Хаски", "Хаски", [r"\bхаски\b"]),
    ("Найн Майс", "Найн Майс", [r"найн\s*майс\w*", r"9mice", r"\b9\s*mice\b"]),
    ("Обла", "Обла", [r"\bобл[аыуое]\b"]),
    ("Бабангида", "Бабангида", [r"бабангид\w*", r"\bбаба?н\w*\b"]),
    ("Слава МЭРЛОУ", "Слава МЭРЛОУ", [r"слав[аы]\s*мэрл\w+", r"\bмэрлоу\b"]),
    ("Бульвар Депо", "Бульвар Депо", [r"бульвар\s*депо\w*", r"\bдепо\b(?!\s*поезд)"]),
    ("Джарахов", "Джарахов", [r"джарахов\w*"]),
    ("Джиган", "Джиган", [r"\bджиган\w*"]),
    ("Канье Уэст", "Канье Уэст", [r"кань[её]\s*уэст\w*", r"\bканье\b", r"\bkanye\b"]),
    ("Дрейк", "Дрейк", [r"\bдрейк\w*", r"\bdrake\b"]),
    ("Эминем", "Эминем", [r"\bэминем\w*", r"\beminem\b"]),
    ("Кендрик Ламар", "Кендрик Ламар", [r"кендрик\s*ламар\w*", r"\bкендрик\b"]),
    ("Дидди", "Дидди", [r"\bдидди\b", r"\bdiddy\b", r"\bp\.?\s*diddy\b"]),
    ("21 Сэвэдж", "21 Сэвэдж", [r"21\s*с[эе]в[эе]дж\w*", r"21\s*savage"]),
    ("Тентасьон", "Тентасьон", [r"тентасьон\w*", r"xxxtentacion", r"xxx\s*tentacion"]),
    ("Текаши", "Текаши", [r"текаши\w*", r"6ix9ine", r"\bтекаш\w+\b"]),
    # ── Themes / shows ──
    ("Оксимирон vs Слава КПСС", "Морген Окси Версус", [
        r"версус\w*\b(?=.{0,60}(окси|слав[ая]|мирон))",
    ]),
]


def strip_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). frontmatter_block includes --- delimiters."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm = text[: end + 5]   # includes closing ---\n
            body = text[end + 5 :]
            return fm, body
    return "", text


def update_frontmatter_related(fm: str, related: list[str]) -> str:
    """Insert or replace `related:` field in frontmatter YAML."""
    if not related:
        return fm
    related_yaml = "related:\n" + "".join(f"  - '[[{r}]]'\n" for r in related)
    # Remove existing related: block if present
    fm = re.sub(r"^related:.*?(?=^\w|\Z)", "", fm, flags=re.MULTILINE | re.DOTALL)
    # Insert before closing ---
    fm = fm.rstrip()
    if fm.endswith("---"):
        fm = fm[:-3].rstrip() + "\n" + related_yaml + "---\n"
    else:
        fm += "\n" + related_yaml + "---\n"
    return fm


# Regex to detect already-wikified spans: [[...]] or (вставить ...) — skip these
SKIP_ZONES_RE = re.compile(
    r"\[\[.*?\]\]"           # existing wikilink
    r"|https?://\S+"         # URLs
    r"|\(вставить[^)]*\)"    # insert markers
    r"|\[[^\]]{1,200}\]",    # any markdown link/ref
    re.IGNORECASE,
)


def add_wikilinks(body: str, entity_patterns: list[tuple[str, str, list[str]]]) -> tuple[str, list[str]]:
    """
    Add first-occurrence [[wikilink]] for each entity in body text.
    Returns (modified_body, list_of_matched_entity_names).
    """
    matched = []

    for display_name, link_target, patterns in entity_patterns:
        combined = "|".join(f"(?:{p})" for p in patterns)
        regex = re.compile(combined, re.IGNORECASE)

        # Find first match that is NOT inside a skip zone
        skip_spans = set()
        for m in SKIP_ZONES_RE.finditer(body):
            skip_spans.add((m.start(), m.end()))

        first_match = None
        for m in regex.finditer(body):
            # Check if inside a skip zone
            inside_skip = any(s <= m.start() and m.end() <= e for s, e in skip_spans)
            if not inside_skip:
                first_match = m
                break

        if first_match:
            orig = first_match.group(0)
            replacement = f"[[{link_target}|{orig}]]"
            body = body[: first_match.start()] + replacement + body[first_match.end() :]
            matched.append(display_name)
            # Rebuild skip_spans after modification would be needed for subsequent passes
            # but since we process entities one by one and only replace first match, it's fine

    return body, matched


def create_index_note(entity_name: str, link_target: str, scripts: list[str]) -> None:
    """Create or overwrite an index note for an entity."""
    idx_path = VAULT.parent / f"{link_target}.md"
    lines = [
        "---",
        f"title: {entity_name}",
        "tags:",
        "  - индекс",
        "  - персона",
        "---",
        "",
        f"# {entity_name}",
        "",
        f"Все сценарии канала, упоминающие **{entity_name}** ({len(scripts)} шт.):",
        "",
    ]
    for s in sorted(scripts):
        lines.append(f"- [[Сценарии/{s}]]")
    lines.append("")
    idx_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    md_files = sorted(VAULT.glob("*.md"))
    print(f"Files to process: {len(md_files)}")

    # entity_name → list of script stems that mention it
    entity_mentions: dict[str, list[str]] = defaultdict(list)

    changed = 0
    for i, path in enumerate(md_files):
        if i % 100 == 0:
            print(f"  {i}/{len(md_files)}...")

        try:
            original = path.read_text(encoding="utf-8")
            fm, body = strip_frontmatter(original)

            if not body.strip():
                continue

            new_body, matched = add_wikilinks(body, ENTITIES)

            if matched:
                new_fm = update_frontmatter_related(fm, matched)
                new_text = new_fm + new_body
                if new_text != original:
                    path.write_text(new_text, encoding="utf-8")
                    changed += 1
                for name in matched:
                    entity_mentions[name].append(path.stem)

        except Exception as e:
            print(f"  ERR {path.name}: {e}")

    print(f"\nModified files: {changed}")

    # Create index notes in vault root (parent of Сценарии)
    print("\nCreating index notes...")
    idx_created = 0
    for display_name, link_target, _ in ENTITIES:
        scripts = entity_mentions.get(display_name, [])
        if scripts:
            create_index_note(display_name, link_target, scripts)
            idx_created += 1
            print(f"  {link_target}.md ({len(scripts)} scripts)")

    print(f"\nIndex notes created: {idx_created}")
    print("Done.")


if __name__ == "__main__":
    main()
