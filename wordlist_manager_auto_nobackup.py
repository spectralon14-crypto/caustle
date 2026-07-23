#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ANNOTATION_RE = re.compile(r"\s*:\s*\S+\s*\(\d+\)")
PAREN_RE = re.compile(r"\([^)]*\)")


def read_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Tidak dapat membaca file: {path}")


def clean_word(token: str) -> str:
    return token.strip().strip('"“”‘’`,;')


def parse_batch(lines: list[str]) -> tuple[set[str], set[str], set[str]]:
    additions: set[str] = set()
    removals: set[str] = set()
    ignored: set[str] = set()

    for raw_line in lines:
        line = raw_line.replace("\r", " ")
        line = ANNOTATION_RE.sub(" ", line)
        line = PAREN_RE.sub(" ", line)

        mode = "ensure"
        for raw_token in line.split():
            if raw_token in {"+", "-", "#"}:
                mode = {"+": "add", "-": "remove", "#": "ignore"}[raw_token]
                continue

            if len(raw_token) > 1 and raw_token[0] in "+-#":
                symbol = raw_token[0]
                raw_token = raw_token[1:]
                mode = {"+": "add", "-": "remove", "#": "ignore"}[symbol]

            word = clean_word(raw_token)
            if not word:
                mode = "ensure"
                continue

            if mode == "remove":
                removals.add(word)
            elif mode == "ignore":
                ignored.add(word)
            else:
                additions.add(word)

            mode = "ensure"

    return additions, removals, ignored


def sort_words(words: set[str]) -> list[str]:
    return sorted(words, key=lambda word: (word.casefold(), word))


def write_crlf(path: Path, words: list[str]) -> None:
    content = "\r\n".join(words)
    if words:
        content += "\r\n"
    path.write_text(content, encoding="utf-8", newline="")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Perbarui master, kosongkan batch, dan hapus backup lama."
    )
    parser.add_argument("master", type=Path)
    parser.add_argument("batch", type=Path)
    args = parser.parse_args()

    master = args.master.resolve()
    batch = args.batch.resolve()

    if not master.exists():
        raise FileNotFoundError(f"Master tidak ditemukan: {master}")
    if not batch.exists():
        raise FileNotFoundError(f"Batch tidak ditemukan: {batch}")
    if master == batch:
        raise ValueError("master.txt dan batch.txt tidak boleh file yang sama.")

    master_words = {line.strip() for line in read_lines(master) if line.strip()}
    additions, removals, ignored = parse_batch(read_lines(batch))

    actually_added = additions - master_words
    already_present = additions & master_words
    actually_removed = removals & master_words
    removal_not_found = removals - master_words

    updated_words = (master_words | additions) - removals
    ordered_words = sort_words(updated_words)

    temp = master.with_name(f".{master.stem}_temporary{master.suffix}")
    old_backup = master.with_name(f"{master.stem}_backup{master.suffix}")

    try:
        write_crlf(temp, ordered_words)

        verification = {line.strip() for line in read_lines(temp) if line.strip()}
        if verification != updated_words:
            raise RuntimeError("Pemeriksaan hasil gagal; master lama tidak diubah.")

        os.replace(temp, master)
        batch.write_text("", encoding="utf-8")

        if old_backup.exists():
            old_backup.unlink()

    except Exception:
        if temp.exists():
            temp.unlink()
        raise

    print("\nSELESAI")
    print(f"Master awal                : {len(master_words):,}")
    print(f"Benar-benar ditambahkan    : {len(actually_added):,}")
    print(f"Sudah ada                  : {len(already_present):,}")
    print(f"Benar-benar dihapus        : {len(actually_removed):,}")
    print(f"Hapus tapi tidak ditemukan : {len(removal_not_found):,}")
    print(f"Diabaikan dengan #         : {len(ignored):,}")
    print(f"Master akhir               : {len(updated_words):,}")
    print(f"Master diperbarui          : {master}")
    print(f"Batch telah dikosongkan    : {batch}")
    print("Backup permanen            : tidak dibuat")


if __name__ == "__main__":
    main()
