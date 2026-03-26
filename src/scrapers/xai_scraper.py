"""xAI deprecations scraper with markdown-first detection."""

from __future__ import annotations

import re
from typing import Any, List

from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..markdown_utils import extract_code_spans, is_markdown
from ..models import DeprecationItem


class XAIScraper(EnhancedBaseScraper):
    """Scraper for xAI model deprecations and obsolescence notices."""

    provider_name = "xAI"
    url = "https://docs.x.ai/developers/models"
    models_markdown_url = "https://docs.x.ai/developers/models.md"
    migration_markdown_url = "https://docs.x.ai/developers/migration/models.md"
    requires_playwright = False

    def scrape(self) -> List[DeprecationItem]:
        """Fetch markdown sources and return any explicit xAI deprecation notices."""
        items: list[DeprecationItem] = []
        for source_url in [self.models_markdown_url, self.migration_markdown_url]:
            content = self.fetch_html(source_url)
            items.extend(self.extract_structured_deprecations(content))
            items.extend(self.extract_unstructured_deprecations(content))

        seen = set()
        unique_items = []
        for item in items:
            if (item.provider, item.model_id) not in seen:
                seen.add((item.provider, item.model_id))
                unique_items.append(item)
        return unique_items

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from xAI markdown or HTML pages."""
        if is_markdown(html):
            return self._extract_markdown_deprecations(html)

        items = []
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        for table in tables:
            headers = table.find("thead") or table.find("tr")
            if not headers:
                continue
            if "model" not in headers.get_text().lower():
                continue
            items.extend(self._extract_from_models_table(table))

        deprecated_sections = soup.find_all(
            lambda tag: (
                tag.name in ["div", "section", "p"]
                and "deprecat" in tag.get_text().lower()
            )
        )
        for section in deprecated_sections:
            items.extend(self._extract_from_deprecated_section(section))
        return items

    def _extract_markdown_deprecations(self, content: str) -> List[DeprecationItem]:
        """Extract only explicit markdown deprecation/obsolete model mentions."""
        items = []
        lines = content.splitlines()

        # Table rows in models.md could eventually include deprecated/obsolete tags.
        for line in lines:
            if "|" not in line:
                continue
            lowered = line.lower()
            if "deprecated" not in lowered and "obsolete" not in lowered:
                continue
            for model_name in extract_code_spans(line):
                if model_name.startswith("grok-"):
                    items.append(
                        DeprecationItem(
                            provider=self.provider_name,
                            model_id=model_name,
                            model_name=model_name,
                            announcement_date="",
                            shutdown_date="",
                            replacement_models=None,
                            deprecation_context=line.strip(),
                            url=self.url,
                        )
                    )

        # Migration docs may mention concrete deprecated models in prose.
        prose_patterns = [
            r"`(grok-[a-z0-9\-.]+)`[^\n]{0,120}\bdeprecated\b",
            r"\bdeprecated\b[^\n]{0,120}`(grok-[a-z0-9\-.]+)`",
            r"`(grok-[a-z0-9\-.]+)`[^\n]{0,120}\bobsolete\b",
            r"\bobsolete\b[^\n]{0,120}`(grok-[a-z0-9\-.]+)`",
        ]
        for pattern in prose_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                model_name = match.group(1)
                context_start = max(0, match.start() - 120)
                context_end = min(len(content), match.end() + 120)
                context = content[context_start:context_end].strip()
                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date="",
                        shutdown_date="",
                        replacement_models=None,
                        deprecation_context=context,
                        url=self.url,
                    )
                )

        # The current public markdown explicitly describes the workflow but names no deprecated models.
        return items

    def _has_deprecation_indicator(self, row_element) -> bool:
        """Check if a table row has a deprecation indicator."""
        row_classes = " ".join(row_element.get("class", []))
        row_text = row_element.get_text().lower()
        deprecation_indicators = ["deprecated", "legacy", "discontinued", "sunset"]

        for indicator in deprecation_indicators:
            if indicator in row_classes.lower() or indicator in row_text:
                return True

        style = row_element.get("style", "")
        if "line-through" in style.lower():
            return True

        return "⊖" in row_text or "⊝" in row_text or "🚫" in row_text

    def _extract_from_models_table(self, table: Any) -> List[DeprecationItem]:
        """Extract model information from a standard models table."""
        items = []
        rows = table.find_all("tr")
        if len(rows) <= 1:
            return items

        headers = [
            th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])
        ]
        model_idx = None
        status_idx = None
        date_idx = None
        description_idx = None

        for idx, header in enumerate(headers):
            if "model" in header or "name" in header:
                model_idx = idx
            elif "status" in header or "state" in header:
                status_idx = idx
            elif "date" in header or "deprecated" in header:
                date_idx = idx
            elif "description" in header or "notes" in header:
                description_idx = idx

        if model_idx is None:
            return items

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) <= model_idx:
                continue

            model_name = cells[model_idx].get_text(strip=True)
            if not model_name or model_name.lower() in ["model", "name"]:
                continue

            is_deprecated = self._has_deprecation_indicator(row)
            if not is_deprecated and status_idx is not None and status_idx < len(cells):
                status_text = cells[status_idx].get_text(strip=True).lower()
                if any(
                    word in status_text
                    for word in ["deprecat", "legacy", "discontinued"]
                ):
                    is_deprecated = True
            if not is_deprecated:
                continue

            deprecation_date = ""
            if date_idx is not None and date_idx < len(cells):
                deprecation_date = self.parse_date(cells[date_idx].get_text(strip=True))

            description = ""
            if description_idx is not None and description_idx < len(cells):
                description = cells[description_idx].get_text(strip=True)

            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_name,
                    model_name=model_name,
                    announcement_date=deprecation_date,
                    shutdown_date=deprecation_date,
                    replacement_models=None,
                    deprecation_context=description,
                    url=self.url,
                )
            )

        return items

    def _extract_from_deprecated_section(self, section: Any) -> List[DeprecationItem]:
        """Extract model names from HTML sections explicitly mentioning deprecation."""
        items = []
        text = section.get_text()
        deprecation_patterns = [
            r"(grok-[a-z0-9\-]+)(?:\s+model)?\s+(?:is|has\s+been|will\s+be|is\s+being)\s+deprecat",
            r"deprecat(?:ed|ing)\s+(?:model[s]?)?\s*:?\s*['\"]?(grok-[a-z0-9\-]+)['\"]?",
            r"legacy\s+(?:model[s]?)?\s*:?\s*['\"]?(grok-[a-z0-9\-]+)['\"]?",
            r"discontinued\s+(?:model[s]?)?\s*:?\s*['\"]?(grok-[a-z0-9\-]+)['\"]?",
        ]

        for pattern in deprecation_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                model_name = match.group(1)
                context_start = max(0, match.start() - 100)
                context_end = min(len(text), match.end() + 100)
                context = text[context_start:context_end].strip()
                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date="",
                        shutdown_date="",
                        replacement_models=None,
                        deprecation_context=context,
                        url=self.url,
                    )
                )
        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecated models from unstructured HTML content only."""
        if is_markdown(html):
            return []

        items = []
        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text()
        deprecation_patterns = [
            r"(grok-[a-z0-9\-]+)(?:\s+model)?\s+(?:is|has\s+been|will\s+be|is\s+being)\s+deprecat",
            r"deprecat(?:ed|ing)\s+(?:model[s]?)?\s*:?\s*['\"]?(grok-[a-z0-9\-]+)['\"]?",
            r"legacy\s+(?:model[s]?)?\s*:?\s*['\"]?(grok-[a-z0-9\-]+)['\"]?",
            r"discontinued\s+(?:model[s]?)?\s*:?\s*['\"]?(grok-[a-z0-9\-]+)['\"]?",
        ]

        for pattern in deprecation_patterns:
            for match in re.finditer(pattern, text_content, re.IGNORECASE):
                model_name = match.group(1)
                context_start = max(0, match.start() - 100)
                context_end = min(len(text_content), match.end() + 100)
                context = text_content[context_start:context_end].strip()
                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date="",
                        shutdown_date="",
                        replacement_models=None,
                        deprecation_context=context,
                        url=self.url,
                    )
                )

        return items
