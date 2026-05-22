"""Groq model deprecations scraper."""

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
    split_markdown_sections,
)
from ..models import DeprecationItem


class GroqScraper(EnhancedBaseScraper):
    """Scraper for Groq model deprecation notices."""

    provider_name = "Groq"
    url = "https://console.groq.com/docs/deprecations"
    markdown_url = "https://console.groq.com/docs/deprecations.md"
    requires_playwright = False
    require_shutdown_dates = True

    def get_source_url(self) -> str:
        """Prefer Groq's markdown source for deterministic parsing."""
        return self.markdown_url

    def parse_date(self, date_str: str) -> str:
        """Parse Groq dates, including compact MM/DD/YY shutdown dates."""
        parsed = super().parse_date(date_str)
        if parsed:
            return parsed

        normalized = (date_str or "").replace("\\.", ".").strip().rstrip(".")
        short_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", normalized)
        if short_match:
            month, day, year = (int(part) for part in short_match.groups())
            return f"20{year:02d}-{month:02d}-{day:02d}"

        return ""

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Groq markdown or HTML."""
        if is_markdown(html):
            return self._extract_from_markdown(html)
        return self._extract_from_html(html)

    def _extract_from_markdown(self, content: str) -> List[DeprecationItem]:
        """Extract deprecation history entries from Groq's markdown page."""
        items: list[DeprecationItem] = []

        for raw_heading, body in split_markdown_sections(content):
            heading_text, anchor = self._parse_linked_heading(raw_heading)
            heading_date = self._extract_heading_date(heading_text)
            if not heading_date:
                continue

            lines = body.splitlines()
            tables = extract_markdown_tables(lines)
            if not tables:
                continue

            section_url = f"{self.url}#{anchor}" if anchor else self.url
            first_table_start = tables[0][0]
            context = " ".join(
                line.strip()
                for line in lines[:first_table_start]
                if line.strip() and not line.strip().startswith("#")
            )
            announcement_date = self._extract_announcement_date(
                context, fallback_year=heading_date[:4]
            )

            for _, _, block in tables:
                headers, rows = parse_markdown_table(block)
                items.extend(
                    self._extract_table_rows(
                        headers, rows, announcement_date, context, section_url
                    )
                )

        return self._dedupe_items(items)

    def _extract_table_rows(
        self,
        headers: list[str],
        rows: list[list[str]],
        announcement_date: str,
        context: str,
        url: str,
    ) -> List[DeprecationItem]:
        """Extract Groq deprecation rows from a markdown table."""
        header_map = {header.lower(): idx for idx, header in enumerate(headers)}
        model_idx = header_map.get("deprecated model", header_map.get("model id"))
        shutdown_idx = header_map.get("shutdown date")
        replacement_idx = header_map.get("recommended replacement model id")
        if model_idx is None or shutdown_idx is None:
            return []

        items = []
        for row in rows:
            if len(row) <= max(model_idx, shutdown_idx):
                continue

            model_ids = self._extract_model_ids(row[model_idx])
            shutdown_date = self.parse_date(row[shutdown_idx])
            if not model_ids or not shutdown_date:
                continue

            replacement_models = None
            if replacement_idx is not None and replacement_idx < len(row):
                replacement_models = self._extract_model_ids(row[replacement_idx])

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
        """Fallback parser for rendered Groq HTML tables."""
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup.find("article") or soup
        items = []
        for table in main.find_all("table"):
            items.extend(self.extract_table_deprecations(table))
        return [item for item in items if self._looks_like_model_id(item.model_id)]

    def _parse_linked_heading(self, heading: str) -> tuple[str, str]:
        """Return display text and anchor from a markdown linked heading."""
        match = re.fullmatch(r"\[(?P<text>.+)]\(#(?P<anchor>[^)]+)\)", heading)
        if not match:
            return heading, ""
        return match.group("text"), match.group("anchor")

    def _extract_heading_date(self, heading: str) -> str:
        """Extract the shutdown/deprecation heading date from a section title."""
        date_text = heading.split(":", 1)[0].strip()
        return self.parse_date(date_text)

    def _extract_announcement_date(self, context: str, fallback_year: str) -> str:
        """Extract the provider announcement date from section prose when available."""
        full_date_match = re.search(
            r"\bon\s+([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s*\d{4})\b",
            context,
        )
        if full_date_match:
            return self.parse_date(full_date_match.group(1))

        day_without_year_match = re.search(
            r"\bon\s+([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?)\b",
            context,
        )
        if day_without_year_match and fallback_year:
            return self.parse_date(
                f"{day_without_year_match.group(1)}, {fallback_year}"
            )

        return ""

    def _extract_model_ids(self, text: str) -> list[str]:
        """Extract one or more model IDs from table cells or code spans."""
        code_spans = extract_code_spans(text)
        candidates = code_spans or re.split(r"\s+(?:or|and)\s+|,|\s+", text)
        model_ids: list[str] = []
        for candidate in candidates:
            cleaned = re.sub(r"\([^)]*\)", "", candidate).strip(" `.;")
            if self._looks_like_model_id(cleaned) and cleaned not in model_ids:
                model_ids.append(cleaned)
        return model_ids

    def _looks_like_model_id(self, value: str) -> bool:
        """Return True for Groq model identifiers and False for prose fragments."""
        if not value or any(char.isspace() for char in value):
            return False
        lowered = value.lower().strip()
        if lowered in {"n/a", "none", "model", "model-id"}:
            return False
        if lowered.startswith(("http://", "https://")):
            return False
        if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*[a-z0-9]", lowered):
            return False
        return any(separator in lowered for separator in ["-", "/", "."])

    def _dedupe_items(self, items: list[DeprecationItem]) -> list[DeprecationItem]:
        """Deduplicate by model ID, preferring richer context."""
        deduped: dict[str, DeprecationItem] = {}
        for item in items:
            existing = deduped.get(item.model_id)
            if existing is None or len(item.deprecation_context or "") > len(
                existing.deprecation_context or ""
            ):
                deduped[item.model_id] = item
        return list(deduped.values())

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Groq deprecations are handled by structured history tables."""
        return []
