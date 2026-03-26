"""OpenAI deprecations scraper with individual model extraction."""

from __future__ import annotations

import re
from typing import Any, List

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


class OpenAIScraper(EnhancedBaseScraper):
    """Scraper for OpenAI deprecations page."""

    provider_name = "OpenAI"
    url = "https://platform.openai.com/docs/deprecations"
    markdown_url = "https://developers.openai.com/api/docs/deprecations.md"
    requires_playwright = False

    def get_source_url(self) -> str:
        """Prefer the public markdown source over the JS-heavy docs page."""
        return self.markdown_url

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from OpenAI's markdown or HTML formats."""
        if is_markdown(html):
            return self._extract_from_markdown(html)
        return self._extract_from_html(html)

    def _extract_from_markdown(self, content: str) -> List[DeprecationItem]:
        """Extract deprecations from the markdown source document."""
        items = []
        date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")

        for heading_text, body in split_markdown_sections(content):
            date_match = date_pattern.match(heading_text)
            if not date_match:
                continue

            announcement_date = date_match.group(1)
            section_title = date_match.group(2)
            anchor = slugify_heading(heading_text)
            section_url = f"{self.url}#{anchor}"

            lines = body.splitlines()
            tables = extract_markdown_tables(lines)
            context_parts = []
            table_items: list[DeprecationItem] = []

            if tables:
                first_table_start = tables[0][0]
                context_parts = [
                    line.strip()
                    for line in lines[:first_table_start]
                    if line.strip() and not line.strip().startswith("#")
                ]
                for _, _, block in tables:
                    table_items.extend(
                        self._extract_from_markdown_table(
                            block,
                            " ".join(context_parts),
                            announcement_date,
                            section_url,
                        )
                    )
            else:
                context_parts = [line.strip() for line in lines if line.strip()]

            section_context = " ".join(context_parts)
            if table_items:
                items.extend(table_items)
            else:
                items.extend(
                    self._extract_from_text(
                        section_context, section_title, announcement_date, section_url
                    )
                )

        deduped: dict[str, DeprecationItem] = {}
        for item in items:
            existing = deduped.get(item.model_id)
            if existing is None or item.announcement_date > existing.announcement_date:
                deduped[item.model_id] = item

        return list(deduped.values())

    def _extract_from_markdown_table(
        self, block: list[str], context: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract deprecations from a markdown table block."""
        headers, rows = parse_markdown_table(block)
        if not headers or not rows:
            return []

        header_text = [header.upper() for header in headers]
        has_model_header = any("MODEL" in header for header in header_text)
        if not has_model_header:
            return []

        shutdown_idx = None
        model_idx = None
        replacement_idx = None

        for idx, header in enumerate(header_text):
            if "SHUTDOWN" in header or "EOL" in header:
                shutdown_idx = idx
            elif "DEPRECATED MODEL" in header and "PRICE" not in header:
                model_idx = idx
            elif ("MODEL" in header or "SYSTEM" in header) and "PRICE" not in header:
                if model_idx is None:
                    model_idx = idx
            elif "REPLACEMENT" in header or "RECOMMENDED" in header:
                replacement_idx = idx

        if shutdown_idx is None and model_idx is None and len(header_text) >= 3:
            shutdown_idx = 0
            model_idx = 1
            replacement_idx = 2

        if model_idx is None:
            return []

        items = []
        for row in rows:
            if len(row) <= model_idx:
                continue

            model_names = self._extract_model_names_from_cell(row[model_idx])
            if not model_names:
                continue

            if any(
                model_name.upper() in {"MODEL", "SYSTEM", "NAME"}
                for model_name in model_names
            ):
                continue

            filtered_models = [
                model_name
                for model_name in model_names
                if not self._should_skip_model_name(model_name)
            ]
            if not filtered_models:
                continue

            shutdown_date = announcement_date
            if shutdown_idx is not None and shutdown_idx < len(row):
                parsed_date = self.parse_date(row[shutdown_idx])
                if parsed_date:
                    shutdown_date = parsed_date

            replacement_models = None
            if replacement_idx is not None and replacement_idx < len(row):
                replacement_models = self._parse_markdown_replacements(
                    row[replacement_idx]
                )

            for model_name in filtered_models:
                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date=announcement_date,
                        shutdown_date=shutdown_date,
                        replacement_models=replacement_models,
                        deprecation_context=context,
                        url=url,
                    )
                )

        return items

    def _clean_model_token(self, value: str) -> str:
        """Normalize extracted model tokens and strip doc footnote markers."""
        return value.strip().rstrip("*").strip()

    def _extract_model_names_from_cell(self, cell_text: str) -> list[str]:
        """Extract one or more concrete model IDs from a table cell."""
        code_spans = [
            self._clean_model_token(model)
            for model in extract_code_spans(cell_text)
            if self._clean_model_token(model)
        ]
        if code_spans:
            return code_spans

        plain_text = cell_text.strip()
        if "(" in plain_text:
            plain_text = plain_text.split("(", 1)[0].strip()

        if " and " in plain_text:
            return [part.strip() for part in plain_text.split(" and ") if part.strip()]

        return [plain_text] if plain_text else []

    def _parse_markdown_replacements(self, replacement_cell: str) -> list[str] | None:
        """Parse replacement model names from markdown cell text."""
        if not replacement_cell or replacement_cell in {"—", "-", "N/A"}:
            return None

        code_spans = [
            self._clean_model_token(model)
            for model in extract_code_spans(replacement_cell)
            if self._clean_model_token(model)
        ]
        if code_spans:
            return code_spans

        parsed = self.parse_replacements(replacement_cell)
        if not parsed:
            return None
        cleaned = [self._clean_model_token(model) for model in parsed if model.strip()]
        return cleaned or None

    def _should_skip_model_name(self, model_name: str) -> bool:
        """Return True when a row describes a system, endpoint, or feature."""
        return (
            model_name.startswith("/")
            or " API" in model_name
            or " endpoint" in model_name.lower()
            or model_name.startswith("OpenAI-Beta:")
            or "fine-tuning training" in model_name.lower()
        )

    def _extract_from_html(self, html: str) -> List[DeprecationItem]:
        """Fallback HTML parser for fixtures and older content."""
        items = []
        soup = BeautifulSoup(html, "html.parser")
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
        )
        if not main_content:
            return items

        date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")
        heading_containers = []

        for wrapper in main_content.find_all("div", class_="anchor-heading-wrapper"):
            heading = wrapper.find(["h2", "h3", "h4"])
            if heading:
                heading_containers.append((wrapper, heading))

        for heading in main_content.find_all(["h2", "h3", "h4"]):
            parent = heading.parent
            if not (
                parent.name == "div"
                and "anchor-heading-wrapper" in parent.get("class", [])
            ):
                heading_containers.append((heading, heading))

        for container, element in heading_containers:
            heading_text = element.get_text(strip=True)
            date_match = date_pattern.match(heading_text)
            if not date_match:
                continue

            announcement_date = date_match.group(1)
            section_title = date_match.group(2)
            anchor_id = element.get("id") or announcement_date
            section_url = f"{self.url}#{anchor_id}"

            context_parts = []
            sibling = container.next_sibling
            table = None
            while sibling:
                if hasattr(sibling, "name"):
                    nested_table = sibling if sibling.name == "table" else None
                    if sibling.name == "div":
                        nested_table = sibling.find("table")

                    if nested_table is not None:
                        table = nested_table
                        break
                    if sibling.name in ["h2", "h3", "h4"]:
                        break
                    if (
                        sibling.name == "div"
                        and "anchor-heading-wrapper" in sibling.get("class", [])
                    ):
                        break
                    text = sibling.get_text(" ", strip=True)
                    if text:
                        context_parts.append(text)
                elif isinstance(sibling, str) and sibling.strip():
                    context_parts.append(sibling.strip())
                sibling = sibling.next_sibling

            section_context = " ".join(context_parts)
            if table:
                items.extend(
                    self._extract_from_table(
                        table, section_context, announcement_date, section_url
                    )
                )
            else:
                items.extend(
                    self._extract_from_text(
                        section_context, section_title, announcement_date, section_url
                    )
                )

        deduped: dict[str, DeprecationItem] = {}
        for item in items:
            existing = deduped.get(item.model_id)
            if existing is None or item.announcement_date > existing.announcement_date:
                deduped[item.model_id] = item
        return list(deduped.values())

    def _extract_from_table(
        self, table: Any, context: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract individual model deprecations from an HTML table."""
        items = []
        rows = table.find_all("tr")
        if len(rows) <= 1:
            return items

        headers = [
            th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])
        ]
        has_model_header = any("MODEL" in header for header in headers)
        if not has_model_header:
            return items

        shutdown_idx = None
        model_idx = None
        replacement_idx = None

        for idx, header in enumerate(headers):
            if "SHUTDOWN" in header or "EOL" in header:
                shutdown_idx = idx
            elif "DEPRECATED MODEL" in header and "PRICE" not in header:
                model_idx = idx
            elif ("MODEL" in header or "SYSTEM" in header) and "PRICE" not in header:
                if model_idx is None:
                    model_idx = idx
            elif "REPLACEMENT" in header or "RECOMMENDED" in header:
                replacement_idx = idx

        if shutdown_idx is None and model_idx is None and len(headers) >= 3:
            shutdown_idx = 0
            model_idx = 1
            replacement_idx = 2

        if model_idx is None:
            return items

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) <= model_idx:
                continue

            code_models = [
                self._clean_model_token(code.get_text(strip=True))
                for code in cells[model_idx].find_all("code")
                if self._clean_model_token(code.get_text(strip=True))
            ]
            model_names = code_models or self._extract_model_names_from_cell(
                cells[model_idx].get_text(" ", strip=True)
            )
            if not model_names:
                continue
            if any(
                model_name.upper() in {"MODEL", "SYSTEM", "NAME"}
                for model_name in model_names
            ):
                continue

            filtered_models = [
                model_name
                for model_name in model_names
                if not self._should_skip_model_name(model_name)
            ]
            if not filtered_models:
                continue

            shutdown_date = announcement_date
            if shutdown_idx is not None and shutdown_idx < len(cells):
                parsed_date = self.parse_date(cells[shutdown_idx].get_text(strip=True))
                if parsed_date:
                    shutdown_date = parsed_date

            replacement_models = None
            if replacement_idx is not None and replacement_idx < len(cells):
                replacement_text = cells[replacement_idx].get_text(" ", strip=True)
                if replacement_text and replacement_text not in {"—", "-", "N/A"}:
                    replacement_models = self._parse_markdown_replacements(
                        replacement_text
                    )

            for model_name in filtered_models:
                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date=announcement_date,
                        shutdown_date=shutdown_date,
                        replacement_models=replacement_models,
                        deprecation_context=context,
                        url=url,
                    )
                )

        return items

    def _extract_from_text(
        self, text: str, title: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract deprecations from unstructured text when no table is present."""
        items = []
        model_pattern = re.compile(
            r"([\w\-\.]+(?:-\d+k?|-preview|-turbo|-vision|-\d{4}))\s+(?:will be|is|are)\s+(?:deprecated|retired|shut down|removed)",
            re.IGNORECASE,
        )
        shutdown_pattern = re.compile(
            r"(?:on|by|before)\s+(\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        )

        models_found = model_pattern.findall(text)
        shutdown_match = shutdown_pattern.search(text)
        shutdown_date = announcement_date
        if shutdown_match:
            parsed = self.parse_date(shutdown_match.group(1))
            if parsed:
                shutdown_date = parsed

        for model in models_found:
            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model,
                    model_name=model,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_models=None,
                    deprecation_context=text,
                    url=url,
                )
            )

        if not items and title:
            if self._should_skip_model_name(title):
                return items

            if " and " in title:
                models = [model.strip() for model in title.split(" and ")]
                for model in models:
                    if model.upper() in {"GPT", "EMBEDDINGS", "MODELS"}:
                        continue
                    items.append(
                        DeprecationItem(
                            provider=self.provider_name,
                            model_id=model,
                            model_name=model,
                            announcement_date=announcement_date,
                            shutdown_date=shutdown_date,
                            replacement_models=None,
                            deprecation_context=text,
                            url=url,
                        )
                    )
            elif title.upper() not in {"GPT", "EMBEDDINGS", "MODELS"}:
                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=title,
                        model_name=title,
                        announcement_date=announcement_date,
                        shutdown_date=shutdown_date,
                        replacement_models=None,
                        deprecation_context=text,
                        url=url,
                    )
                )

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """OpenAI deprecations are handled by structured parsing."""
        return []
