"""Helpers for parsing provider markdown pages."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable


SECTION_HEADING_RE = re.compile(r"^###\s+(.*)$", re.MULTILINE)
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")


def is_markdown(content: str) -> bool:
    """Best-effort detection for markdown documents."""
    stripped = content.lstrip()
    if not stripped:
        return False
    if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
        return False
    return stripped.startswith(("#", "***", "---", "####", "###"))


def slugify_heading(text: str) -> str:
    """Create a URL slug compatible with common docs anchors."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


def split_markdown_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content into level-3 sections."""
    matches = list(SECTION_HEADING_RE.finditer(content))
    sections: list[tuple[str, str]] = []

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        heading = match.group(1).strip()
        body = content[start:end].strip()
        sections.append((heading, body))

    return sections


def extract_markdown_tables(lines: Iterable[str]) -> list[tuple[int, int, list[str]]]:
    """Return markdown table blocks as (start, end, block_lines)."""
    line_list = list(lines)
    tables: list[tuple[int, int, list[str]]] = []
    index = 0

    while index < len(line_list) - 1:
        current = line_list[index].strip()
        next_line = line_list[index + 1].strip()
        if "|" not in current or not TABLE_SEPARATOR_RE.match(next_line):
            index += 1
            continue

        start = index
        block = [line_list[index], line_list[index + 1]]
        index += 2
        while index < len(line_list) and "|" in line_list[index]:
            block.append(line_list[index])
            index += 1

        tables.append((start, index, block))

    return tables


def parse_markdown_table(block_lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse a markdown table into headers and row cells."""
    if len(block_lines) < 2:
        return [], []

    def split_row(row: str) -> list[str]:
        stripped = row.strip().strip("|")
        return [cell.strip() for cell in stripped.split("|")]

    headers = split_row(block_lines[0])
    rows = [split_row(row) for row in block_lines[2:] if row.strip()]
    return headers, rows


def extract_code_spans(text: str) -> list[str]:
    """Extract inline code spans from markdown text."""
    return [match.strip() for match in CODE_SPAN_RE.findall(text)]
