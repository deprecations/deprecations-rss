"""Google AI/Gemini deprecations scraper."""

from __future__ import annotations

import re
from typing import List

from ..base_scraper import EnhancedBaseScraper
from ..markdown_utils import extract_code_spans
from ..models import DeprecationItem

HEADING_RE = re.compile(r'^(#{2,3})\s+(.*?)\s*\{%\s*id="([^"]+)"\s*%\}\s*$')
TABLE_RE = re.compile(r"\{%\s*table\s*%\}(.*?)\{%\s*/table\s*%\}", re.DOTALL)
ROW_SEPARATOR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)
CELL_RE = re.compile(r"^[ \t]*\*(?:[ \t]+|$)", re.MULTILINE)
MODEL_ID_RE = re.compile(r"^(?:gemini|embedding|text-embedding|imagen|veo|lyria)-\S+$")


class GoogleScraper(EnhancedBaseScraper):
    """Scraper for the Gemini API deprecations page.

    The page moved from ai.google.dev to aistudio.google.com and is rendered
    client-side. Its Markdoc source is published for machine readers at
    ``<page>.md`` (see https://aistudio.google.com/llms.txt), so that is parsed
    instead of HTML.
    """

    provider_name = "Google"
    url = "https://aistudio.google.com/docs/deprecations"
    markdown_url = f"{url}.md"
    requires_playwright = False

    def get_source_url(self) -> str:
        return self.markdown_url

    def extract_structured_deprecations(self, content: str) -> List[DeprecationItem]:
        """Extract rows with a concrete shutdown date from the Markdoc tables."""
        by_model: dict[str, DeprecationItem] = {}
        for section, anchor, headers, rows in self._tables(content):
            columns = {header.lower(): idx for idx, header in enumerate(headers)}
            if "model" not in columns or "shutdown date" not in columns:
                continue

            for cells in rows:
                item = self._row_item(cells, columns, section, anchor)
                if item is None:
                    continue
                existing = by_model.get(item.model_id)
                if existing is None or item.shutdown_date < existing.shutdown_date:
                    by_model[item.model_id] = item

        return list(by_model.values())

    def _tables(self, content: str):
        """Yield (section, anchor, headers, rows) for each {% table %} block."""
        parent, section, anchor = "", "Gemini deprecations", ""
        position = 0
        for match in TABLE_RE.finditer(content):
            for line in content[position : match.start()].splitlines():
                heading = HEADING_RE.match(line)
                if not heading:
                    continue
                level, title, anchor = heading.groups()
                if level == "##":
                    parent, section = title, title
                else:
                    section = f"{parent}: {title}" if parent else title
            position = match.end()

            rows = [
                [cell.strip() for cell in CELL_RE.split(block)[1:]]
                for block in ROW_SEPARATOR_RE.split(match.group(1))
            ]
            rows = [row for row in rows if row]
            if rows:
                yield section, anchor, rows[0], rows[1:]

    def _row_item(
        self, cells: list[str], columns: dict[str, int], section: str, anchor: str
    ) -> DeprecationItem | None:
        def cell(name: str) -> str:
            idx = columns.get(name)
            return cells[idx] if idx is not None and idx < len(cells) else ""

        model_ids = extract_code_spans(cell("model")) or [cell("model")]
        model_id = model_ids[0].strip()
        if not MODEL_ID_RE.match(model_id):
            return None

        # "No shutdown date announced", "N/A" and "Coming soon" do not parse.
        shutdown_date = self.parse_date(cell("shutdown date"))
        if not shutdown_date:
            return None

        release_date = self.parse_date(cell("release date"))
        # Replacements are the code spans before any parenthesised note, which
        # often names the deprecated model again.
        replacement_text = cell("recommended replacement").split("(", 1)[0]
        replacements = [
            model
            for model in extract_code_spans(replacement_text)
            if MODEL_ID_RE.match(model)
        ] or None

        context = [f"Gemini deprecations table: {section}."]
        if release_date:
            context.append(f"Release date: {release_date}.")
        context.append(f"Shutdown date: {shutdown_date}.")
        if replacements:
            context.append(f"Recommended replacement: {', '.join(replacements)}.")

        return DeprecationItem(
            provider=self.provider_name,
            model_id=model_id,
            announcement_date=shutdown_date,
            shutdown_date=shutdown_date,
            deprecation_date=shutdown_date,
            replacement_models=replacements,
            deprecation_context=" ".join(context),
            url=f"{self.url}#{anchor}" if anchor else self.url,
        )
