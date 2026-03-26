"""Anthropic deprecations scraper with individual model extraction."""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..markdown_utils import (
    extract_code_spans,
    extract_markdown_tables,
    is_markdown,
    parse_markdown_table,
    slugify_heading,
    split_markdown_sections,
)
from ..models import DeprecationItem


class AnthropicScraper(EnhancedBaseScraper):
    """Scraper for Anthropic deprecations page."""

    provider_name = "Anthropic"
    url = "https://platform.claude.com/docs/en/about-claude/model-deprecations"
    markdown_url = (
        "https://platform.claude.com/docs/en/about-claude/model-deprecations.md"
    )
    requires_playwright = False

    def get_source_url(self) -> str:
        """Prefer the public markdown source over rendered HTML."""
        return self.markdown_url

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Anthropic's markdown or HTML format."""
        if is_markdown(html):
            return self._extract_from_markdown(html)
        return self._extract_from_html(html)

    def _extract_from_markdown(self, content: str) -> List[DeprecationItem]:
        """Extract deprecations from the markdown source document."""
        items: list[DeprecationItem] = []

        model_status_match = re.search(
            r"## Model status\n(?P<body>.*?)(?:\n## |\Z)", content, re.DOTALL
        )
        if model_status_match:
            items.extend(
                self._extract_model_status_markdown(model_status_match.group("body"))
            )

        date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")
        for heading_text, body in split_markdown_sections(content):
            date_match = date_pattern.match(heading_text)
            if not date_match:
                continue

            announcement_date = date_match.group(1)
            anchor = slugify_heading(heading_text)
            section_url = f"{self.url}#{anchor}"

            lines = body.splitlines()
            tables = extract_markdown_tables(lines)
            if not tables:
                continue

            first_table_start = tables[0][0]
            context = " ".join(
                line.strip()
                for line in lines[:first_table_start]
                if line.strip() and not line.strip().startswith("#")
            )

            for _, _, block in tables:
                headers, rows = parse_markdown_table(block)
                if not headers:
                    continue
                items.extend(
                    self._extract_markdown_history_rows(
                        headers, rows, announcement_date, context, section_url
                    )
                )

        return self._dedupe_items(items)

    def _extract_model_status_markdown(self, body: str) -> List[DeprecationItem]:
        """Extract deprecated rows from Anthropic's model status markdown table."""
        lines = body.splitlines()
        tables = extract_markdown_tables(lines)
        if not tables:
            return []

        headers, rows = parse_markdown_table(tables[0][2])
        header_map = {header.lower(): idx for idx, header in enumerate(headers)}
        model_idx = header_map.get("api model name")
        state_idx = header_map.get("current state")
        deprecated_idx = header_map.get("deprecated")
        retirement_idx = header_map.get("tentative retirement date")
        if None in {model_idx, state_idx, deprecated_idx, retirement_idx}:
            return []

        items = []
        for row in rows:
            if len(row) <= retirement_idx:
                continue

            model_ids = extract_code_spans(row[model_idx])
            model_id = model_ids[0] if model_ids else row[model_idx].strip()
            current_state = row[state_idx].strip().lower()
            deprecated_date = self.parse_date(row[deprecated_idx])
            shutdown_date = self.parse_date(row[retirement_idx])

            if current_state not in {"deprecated", "retired"}:
                continue
            if not shutdown_date or not model_id:
                continue

            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_id,
                    announcement_date=deprecated_date,
                    shutdown_date=shutdown_date,
                    replacement_models=None,
                    deprecation_context="Model status table entry.",
                    url=self.url,
                )
            )

        return items

    def _extract_markdown_history_rows(
        self,
        headers: list[str],
        rows: list[list[str]],
        announcement_date: str,
        context: str,
        url: str,
    ) -> List[DeprecationItem]:
        """Extract rows from Anthropic's markdown deprecation history tables."""
        items = []
        header_text = [header.lower() for header in headers]
        is_history_table = header_text[:3] == [
            "retirement date",
            "deprecated model",
            "recommended replacement",
        ]
        if not is_history_table:
            return items

        for row in rows:
            if len(row) < 2:
                continue

            shutdown_date = self.parse_date(row[0])
            model_ids = extract_code_spans(row[1])
            model_id = model_ids[0] if model_ids else row[1].strip()
            replacement_models = (
                extract_code_spans(row[2]) if len(row) > 2 and row[2].strip() else None
            )

            if not shutdown_date or not model_id:
                continue

            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_id,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_models=replacement_models or None,
                    deprecation_context=context,
                    url=url,
                )
            )

        return items

    def _extract_from_html(self, html: str) -> List[DeprecationItem]:
        """Fallback HTML parser for existing fixtures/content."""
        items = []
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup.find("article") or soup.find("body") or soup

        for table in main.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
            if not headers:
                continue

            announcement_date, section_context = self._get_section_metadata(table)
            is_format2 = "retirement date" in headers[0].lower()

            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) < 2:
                    continue

                if is_format2:
                    shutdown_date = self.parse_date(cells[0])
                    model_id = cells[1]
                    replacement_str = (
                        cells[2]
                        if len(cells) > 2 and cells[2] not in {"—", "-", "N/A"}
                        else None
                    )
                    replacement_models = (
                        self.parse_replacements(replacement_str)
                        if replacement_str
                        else None
                    )
                    deprecated_date = announcement_date
                else:
                    model_id = cells[0]
                    deprecated_date = (
                        self.parse_date(cells[2]) if len(cells) > 2 else ""
                    ) or announcement_date
                    shutdown_date = self.parse_date(cells[3]) if len(cells) > 3 else ""
                    replacement_models = None
                    if len(cells) > 2 and cells[2].strip().upper() == "N/A":
                        continue

                final_date = shutdown_date or deprecated_date
                if not final_date or not model_id:
                    continue

                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_id,
                        announcement_date=deprecated_date or "",
                        shutdown_date=final_date,
                        replacement_models=replacement_models,
                        deprecation_context=section_context,
                        url=self.url,
                    )
                )

        return self._dedupe_items(items)

    def _get_section_metadata(self, table) -> tuple[str, str]:
        """Extract announcement date and nearby explanatory context for a table."""
        announcement_date = ""
        context_parts: list[str] = []

        current = table
        while current and current.find_previous_sibling() is None:
            current = current.parent

        current = current.find_previous_sibling() if current else None
        while current:
            if current.name in ["h2", "h3", "h4"]:
                heading_text = current.get_text(" ", strip=True)
                date_match = re.match(r"^(\d{4}-\d{2}-\d{2}):", heading_text)
                if date_match:
                    announcement_date = date_match.group(1)
                break
            if current.name == "p":
                text = current.get_text(" ", strip=True)
                if text:
                    context_parts.insert(0, text)
            current = current.find_previous_sibling()

        return announcement_date, " ".join(context_parts)

    def _dedupe_items(self, items: list[DeprecationItem]) -> list[DeprecationItem]:
        """Deduplicate items, preferring entries with more context."""
        deduped: dict[str, DeprecationItem] = {}
        for item in items:
            existing = deduped.get(item.model_id)
            if existing is None:
                deduped[item.model_id] = item
                continue

            existing_score = (1 if existing.announcement_date else 0) + len(
                existing.deprecation_context or ""
            )
            item_score = (1 if item.announcement_date else 0) + len(
                item.deprecation_context or ""
            )
            if item_score > existing_score:
                deduped[item.model_id] = item

        return list(deduped.values())

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Anthropic deprecations are handled by structured parsing."""
        return []
