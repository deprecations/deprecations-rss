"""Cohere deprecations scraper with parser-based model extraction."""

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


class CohereScraper(EnhancedBaseScraper):
    """Scraper for Cohere deprecations page."""

    provider_name = "Cohere"
    url = "https://docs.cohere.com/docs/deprecations"
    markdown_url = "https://docs.cohere.com/docs/deprecations.md"
    requires_playwright = False
    require_shutdown_dates = True

    def get_source_url(self) -> str:
        """Prefer the markdown source for deterministic parsing."""
        return self.markdown_url

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Cohere's markdown or HTML pages."""
        if is_markdown(html):
            return self._extract_from_markdown(html)
        return self._extract_from_html(html)

    def _extract_from_markdown(self, content: str) -> List[DeprecationItem]:
        """Extract model deprecations directly from the markdown source."""
        items: list[DeprecationItem] = []

        for heading_text, body in split_markdown_sections(content):
            if not re.match(r"^\d{4}-\d{2}-\d{2}:", heading_text):
                continue

            announcement_date, title = heading_text.split(":", 1)
            title = title.strip()
            section_url = f"{self.url}#{slugify_heading(heading_text)}"
            lines = body.splitlines()
            context = " ".join(line.strip() for line in lines if line.strip())

            if announcement_date == "2026-04-04":
                items.extend(
                    self._extract_embed_and_aya_section(
                        lines, announcement_date, context, section_url
                    )
                )
                continue

            if announcement_date == "2025-09-15":
                items.extend(
                    self._extract_command_models_section(
                        lines, announcement_date, context, section_url
                    )
                )
                continue

            tables = extract_markdown_tables(lines)
            for _, _, block in tables:
                headers, rows = parse_markdown_table(block)
                if not headers:
                    continue
                items.extend(
                    self._extract_markdown_table_rows(
                        headers, rows, announcement_date, context, section_url
                    )
                )

        return items

    def _extract_embed_and_aya_section(
        self, lines: list[str], announcement_date: str, context: str, url: str
    ) -> List[DeprecationItem]:
        """Extract model rows from the Embed/Aya retirement section."""
        retired_models = self._extract_bullets_after_marker(
            lines, "the following models will be retired:"
        )
        embedding_replacements = self._extract_nested_bullets_after_marker(
            lines, "* Embedding tasks alternatives:"
        )
        chat_replacements = self._extract_nested_bullets_after_marker(
            lines, "* Chat tasks alternatives:"
        )

        items = []
        for model in retired_models:
            replacement_models = (
                embedding_replacements
                if model.startswith("embed-")
                else chat_replacements
            )
            shutdown_date = self.parse_date("April 4, 2026")
            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_models=replacement_models or None,
                    deprecation_context=context,
                    url=url,
                )
            )

        return items

    def _extract_command_models_section(
        self, lines: list[str], announcement_date: str, context: str, url: str
    ) -> List[DeprecationItem]:
        """Extract explicitly deprecated command models from the September 2025 section."""
        deprecated_models = []
        capture = False
        started = False
        for line in lines:
            stripped = line.strip()
            if stripped == "Deprecated Models:":
                capture = True
                continue
            if not capture:
                continue
            if not stripped and not started:
                continue
            if not stripped:
                break
            if stripped.startswith("*"):
                started = True
                for code_span in extract_code_spans(stripped):
                    if self._looks_like_model(code_span):
                        deprecated_models.append(code_span)

        replacement_models = []
        for line in lines:
            if "recommend you use" in line.lower():
                replacement_models = [
                    model
                    for model in extract_code_spans(line)
                    if self._looks_like_model(model)
                ]
                break

        items = []
        for model in deprecated_models:
            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model,
                    announcement_date=announcement_date,
                    shutdown_date="",
                    replacement_models=replacement_models or None,
                    deprecation_context=context,
                    url=url,
                )
            )
        return items

    def _extract_markdown_table_rows(
        self,
        headers: list[str],
        rows: list[list[str]],
        announcement_date: str,
        context: str,
        url: str,
    ) -> List[DeprecationItem]:
        """Extract model rows from markdown tables."""
        header_map = {header.lower(): idx for idx, header in enumerate(headers)}
        model_idx = header_map.get("deprecated model")
        shutdown_idx = header_map.get("shutdown date")
        replacement_idx = header_map.get("recommended replacement")
        if model_idx is None or shutdown_idx is None:
            return []

        items = []
        for row in rows:
            if len(row) <= max(model_idx, shutdown_idx):
                continue

            model_ids = [
                model
                for model in extract_code_spans(row[model_idx])
                if self._looks_like_model(model)
            ]
            shutdown_date = self.parse_date(row[shutdown_idx])
            replacement_models = None
            if replacement_idx is not None and replacement_idx < len(row):
                replacement_models = [
                    model
                    for model in extract_code_spans(row[replacement_idx])
                    if self._looks_like_model(model)
                ]

            for model_id in model_ids:
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
        """Fallback HTML parser that handles simple table-based cases."""
        soup = BeautifulSoup(html, "html.parser")
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="markdown")
        )
        if not main:
            return []

        items = []
        for table in main.find_all("table"):
            items.extend(self.extract_table_deprecations(table))
        return [item for item in items if self._looks_like_model(item.model_id)]

    def _extract_bullets_after_marker(self, lines: list[str], marker: str) -> list[str]:
        """Extract top-level bullet code spans after a marker line."""
        items: list[str] = []
        capture = False
        started = False
        for line in lines:
            stripped = line.strip()
            if marker.lower() in stripped.lower():
                capture = True
                continue
            if not capture:
                continue
            if not stripped and not started:
                continue
            if not stripped:
                break
            if stripped.startswith("* "):
                started = True
                items.extend(extract_code_spans(stripped))
        return [item for item in items if self._looks_like_model(item)]

    def _extract_nested_bullets_after_marker(
        self, lines: list[str], marker: str
    ) -> list[str]:
        """Extract nested bullet code spans after a marker line."""
        items: list[str] = []
        capture = False
        for line in lines:
            if line.strip() == marker:
                capture = True
                continue
            if not capture:
                continue
            if line.startswith("  * ") or line.startswith("    * "):
                items.extend(extract_code_spans(line))
                continue
            if line.strip() and not line.startswith(" "):
                break
        return [item for item in items if self._looks_like_model(item)]

    def _looks_like_model(self, value: str) -> bool:
        """Return True for model identifiers, False for endpoints/features."""
        lowered = value.lower()
        return lowered.startswith(("command", "embed", "rerank", "c4ai", "aya"))

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Cohere deprecations are handled by structured parsing."""
        return []
