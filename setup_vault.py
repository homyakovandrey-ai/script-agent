#!/usr/bin/env python3
"""
setup_vault.py - one-time converter: reads .docx scripts from source folder,
converts to .md, and saves them to the vault for the script agent to use.

Usage:
    python setup_vault.py <source_folder> [vault_folder]

Example:
    python setup_vault.py "d:/User Files/Desktop/убиваю бпм" vault
"""

import sys
import os
import glob
from pathlib import Path

try:
    import docx
except ImportError:
    print("Установи python-docx: pip install python-docx")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()


def docx_to_text(filepath: str) -> str:
    doc = docx.Document(filepath)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def convert_folder(source: Path, vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)

    # Collect all .docx files recursively
    docx_files = list(source.glob("**/*.docx")) + list(source.glob("*.docx"))
    docx_files = list(set(docx_files))

    if not docx_files:
        print(f"Не найдено .docx файлов в {source}")
        return

    print(f"Найдено файлов: {len(docx_files)}")
    ok, skip, err = 0, 0, 0

    for f in sorted(docx_files):
        # Skip temp files (Word creates ~$filename.docx)
        if f.name.startswith("~$"):
            skip += 1
            continue

        # Build output filename: parent folder name + file stem
        parent = f.parent.name
        stem = f.stem
        if parent == source.name:
            # file is at root level
            out_name = stem
        else:
            out_name = f"{parent} — {stem}" if parent.upper() != stem.upper() else stem

        # Sanitize
        safe_name = "".join(c for c in out_name if c not in r'\/:*?"<>|').strip()
        out_path = vault / f"{safe_name}.md"

        try:
            text = docx_to_text(str(f))
            if not text.strip():
                skip += 1
                continue

            # Add frontmatter with original path for reference
            md_content = f"---\nsource: {f.name}\n---\n\n{text}"
            out_path.write_text(md_content, encoding="utf-8")
            ok += 1
            try:
                print(f"  OK {safe_name}.md")
            except UnicodeEncodeError:
                print(f"  OK [converted]")
        except Exception as e:
            err += 1
            try:
                print(f"  ERR {f.name}: {e}")
            except UnicodeEncodeError:
                print(f"  ERR [encode error in filename]")

    print(f"\nГотово: {ok} конвертировано, {skip} пропущено, {err} ошибок")
    print(f"Vault: {vault.resolve()}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    source = Path(sys.argv[1])
    vault = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        os.getenv("VAULT_PATH", "./vault")
    )

    if not source.exists():
        print(f"Папка не найдена: {source}")
        sys.exit(1)

    print(f"Источник: {source.resolve()}")
    print(f"Vault:    {vault.resolve()}")
    print()
    convert_folder(source, vault)


if __name__ == "__main__":
    main()
