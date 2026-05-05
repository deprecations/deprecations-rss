"""Google AI/Gemini deprecations scraper."""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class GoogleScraper(EnhancedBaseScraper):
    """Scraper for the Google AI/Gemini model deprecations table."""

    provider_name = "Google"
    url = "https://ai.google.dev/gemini-api/docs/deprecations"
    changelog_url = "https://ai.google.dev/gemini-api/docs/changelog"
    requires_playwright = False

    _NO_SHUTDOWN_MARKERS = {
        "no shutdown date announced",
        "no shut down date announced",
        "no shutdown announced",
    }

    def scrape(self) -> List[DeprecationItem]:
        """Combine current deprecation tables with older explicit changelog notices."""
        table_html = self.fetch_html(self.url)
        changelog_html = self.fetch_html(self.changelog_url)
        table_items = self.extract_structured_deprecations(table_html)
        changelog_items = self._extract_changelog_deprecations(changelog_html)

        by_model = {item.model_id: item for item in table_items}
        for item in changelog_items:
            by_model.setdefault(item.model_id, item)
        return list(by_model.values())

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract only rows with concrete shutdown dates from Gemini tables."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return []

        items: list[DeprecationItem] = []
        for table in content.find_all("table"):
            headers = self._table_headers(table)
            header_map = {header.lower(): idx for idx, header in enumerate(headers)}
            model_idx = header_map.get("model")
            release_idx = header_map.get("release date")
            shutdown_idx = header_map.get("shutdown date")
            replacement_idx = header_map.get("recommended replacement")
            if model_idx is None or shutdown_idx is None:
                continue

            section_name, section_url = self._table_section(table)
            for row in table.find_all("tr")[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(model_idx, shutdown_idx):
                    continue

                model_id = cells[model_idx].get_text(" ", strip=True)
                if not self._looks_like_model_id(model_id):
                    continue

                shutdown_text = cells[shutdown_idx].get_text(" ", strip=True)
                if self._is_non_actionable_shutdown(shutdown_text):
                    continue

                shutdown_date = self.parse_date(shutdown_text)
                if not shutdown_date:
                    # Rows like "Coming soon" are lifecycle warnings but not dated
                    # deprecations. Exclude them from the feed until a date lands.
                    continue

                release_date = ""
                if release_idx is not None and release_idx < len(cells):
                    release_date = self.parse_date(
                        cells[release_idx].get_text(" ", strip=True)
                    )

                replacement_models = None
                if replacement_idx is not None and replacement_idx < len(cells):
                    replacement_models = self._parse_replacements(
                        cells[replacement_idx]
                    )

                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_id,
                        announcement_date=shutdown_date,
                        shutdown_date=shutdown_date,
                        deprecation_date=shutdown_date,
                        replacement_models=replacement_models,
                        deprecation_context=self._build_context(
                            section_name,
                            release_date,
                            shutdown_date,
                            replacement_models,
                        ),
                        url=section_url,
                    )
                )

        return self._dedupe_items(items)

    def _table_headers(self, table) -> list[str]:
        header_row = table.find("tr")
        if not header_row:
            return []
        return [
            cell.get_text(" ", strip=True) for cell in header_row.find_all(["th", "td"])
        ]

    def _table_section(self, table) -> tuple[str, str]:
        heading = table.find_previous(["h2", "h3", "h4"])
        if not heading:
            return "Gemini deprecations", self.url
        heading_text = heading.get_text(" ", strip=True)
        heading_id = heading.get("id", "")
        return heading_text, f"{self.url}#{heading_id}" if heading_id else self.url

    def _looks_like_model_id(self, value: str) -> bool:
        normalized = value.strip()
        if not normalized or normalized.lower() == "preview models":
            return False
        return bool(
            re.match(
                r"^(gemini|embedding|text-embedding|imagen|veo|lyria)-[A-Za-z0-9_.-]+$",
                normalized,
            )
        )

    def _is_non_actionable_shutdown(self, shutdown_text: str) -> bool:
        normalized = shutdown_text.strip().lower()
        return not normalized or normalized in self._NO_SHUTDOWN_MARKERS

    def _parse_replacements(self, cell) -> list[str] | None:
        text = cell.get_text(" ", strip=True)
        if not text or text in {"—", "-", "---", "N/A"}:
            return None
        replacements = [
            replacement
            for replacement in self.parse_replacements(text) or []
            if self._looks_like_model_id(replacement)
        ]
        return replacements or None

    def _build_context(
        self,
        section_name: str,
        release_date: str,
        shutdown_date: str,
        replacement_models: list[str] | None,
    ) -> str:
        parts = [f"Gemini deprecations table: {section_name}."]
        if release_date:
            parts.append(f"Release date: {release_date}.")
        parts.append(f"Shutdown date: {shutdown_date}.")
        if replacement_models:
            parts.append(f"Recommended replacement: {', '.join(replacement_models)}.")
        return " ".join(parts)

    def _dedupe_items(self, items: list[DeprecationItem]) -> list[DeprecationItem]:
        by_model: dict[str, DeprecationItem] = {}
        for item in items:
            existing = by_model.get(item.model_id)
            if existing is None or item.shutdown_date < existing.shutdown_date:
                by_model[item.model_id] = item
        return list(by_model.values())

    def _extract_changelog_deprecations(self, html: str) -> list[DeprecationItem]:
        """Extract explicit historical notices omitted from the lifecycle tables."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return []

        items: list[DeprecationItem] = []
        for section_header in content.find_all(["h2", "h3"]):
            section_title = section_header.get_text(" ", strip=True)
            section_date_match = re.search(r"(\w+ \d{1,2}, \d{4})", section_title)
            if not section_date_match:
                continue
            section_date = self.parse_date(section_date_match.group(1))
            if not section_date:
                continue

            for notice_text in self._section_notice_texts(section_header):
                items.extend(self._items_from_notice_text(notice_text, section_date))

        return self._dedupe_items(items)

    def _section_notice_texts(self, section_header) -> list[str]:
        notices: list[str] = []
        sibling = section_header.next_sibling
        while sibling:
            if getattr(sibling, "name", None) in ["h2", "h3"]:
                break
            if getattr(sibling, "name", None) in ["p", "li"]:
                text = sibling.get_text(" ", strip=True)
                if self._has_deprecation_language(text):
                    notices.append(text)
            if getattr(sibling, "name", None) in ["ul", "ol"]:
                for item in sibling.find_all("li", recursive=False):
                    text = item.get_text(" ", strip=True)
                    if self._has_deprecation_language(text):
                        notices.append(text)
            sibling = sibling.next_sibling
        return notices

    def _has_deprecation_language(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            phrase in lowered
            for phrase in [
                "deprecation announcement",
                "will be shut down",
                "has been shut down",
                "are shut down",
                "is shut down",
                "now shut down",
                "no longer supported",
                "removed",
                "will be deprecated",
            ]
        )

    def _items_from_notice_text(
        self, text: str, section_date: str
    ) -> list[DeprecationItem]:
        items: list[DeprecationItem] = []
        normalized = " ".join(text.split())

        items.extend(self._extract_grouped_shutdowns(normalized, section_date))
        items.extend(self._extract_single_shutdowns(normalized, section_date))
        items.extend(self._extract_shutdown_lists(normalized, section_date))
        items.extend(self._extract_no_longer_supported(normalized, section_date))

        return self._dedupe_items(items)

    def _extract_grouped_shutdowns(
        self, text: str, section_date: str
    ) -> list[DeprecationItem]:
        items: list[DeprecationItem] = []
        if "following models will be shut down:" not in text.lower():
            return []

        year = section_date[:4]
        group_re = re.compile(
            r"([A-Z][a-z]+\s+\d{1,2})(?:st|nd|rd|th)?:\s*(.*?)(?=(?:[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?:)|$)"
        )
        for match in group_re.finditer(text):
            shutdown_date = self.parse_date(f"{match.group(1)}, {year}")
            if not shutdown_date:
                continue
            for model_id in self._model_ids_before_replacement_text(match.group(2)):
                items.append(
                    self._changelog_item(model_id, section_date, shutdown_date, text)
                )
        return items

    def _extract_single_shutdowns(
        self, text: str, section_date: str
    ) -> list[DeprecationItem]:
        items: list[DeprecationItem] = []
        date_pattern = r"(?P<date>[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)"
        model_pattern = r"(?P<model>(?:gemini|embedding|text-embedding|imagen|veo|lyria)-[A-Za-z0-9_.-]+)"

        list_patterns = [
            rf"following models will be shut down(?: on)?\s+{date_pattern}:\s*(?P<models>.*)$",
            rf"shut down for\s+(?P<models>.*?)\s+coming\s+{date_pattern}",
        ]
        for pattern in list_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                shutdown_date = self._parse_notice_date(
                    match.group("date"), section_date
                )
                if not shutdown_date:
                    continue
                for model_id in self._model_ids_before_replacement_text(
                    match.group("models")
                ):
                    items.append(
                        self._changelog_item(
                            model_id, section_date, shutdown_date, text
                        )
                    )

        direct_patterns = [
            rf"{model_pattern}[^.;:]{{0,80}}\bwill be shut down(?: on)?\s+{date_pattern}",
            rf"{model_pattern}[^.;:]{{0,80}}\bwill be deprecated on\s+{date_pattern}",
        ]
        for pattern in direct_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                shutdown_date = self._parse_notice_date(
                    match.group("date"), section_date
                )
                model_id = match.group("model")
                if shutdown_date and self._looks_like_model_id(model_id):
                    items.append(
                        self._changelog_item(
                            model_id, section_date, shutdown_date, text
                        )
                    )

        return items

    def _extract_shutdown_lists(
        self, text: str, section_date: str
    ) -> list[DeprecationItem]:
        lowered = text.lower()
        if not any(
            phrase in lowered
            for phrase in [
                "following models are shut down",
                "following model is shut down",
                "models are now shut down",
                "is shut down",
                "has been shut down",
            ]
        ):
            return []

        if "will be shut down" in lowered or "will be deprecated" in lowered:
            return []

        model_text = text
        for separator in [" Use ", " See ", " Refer "]:
            model_text = model_text.split(separator, 1)[0]
        return [
            self._changelog_item(model_id, section_date, section_date, text)
            for model_id in self._model_ids_before_replacement_text(model_text)
        ]

    def _extract_no_longer_supported(
        self, text: str, section_date: str
    ) -> list[DeprecationItem]:
        lowered = text.lower()
        model_ids: list[str] = []
        if "gemini 1.0 pro vision" in lowered and (
            "removed" in lowered or "deprecated" in lowered
        ):
            model_ids.append("gemini-1.0-pro-vision")
        elif "gemini 1.0 pro" in lowered and "no longer supported" in lowered:
            model_ids.append("gemini-1.0-pro")

        return [
            self._changelog_item(model_id, section_date, section_date, text)
            for model_id in model_ids
        ]

    def _parse_notice_date(self, raw_date: str, section_date: str) -> str:
        if not re.search(r"\d{4}", raw_date):
            raw_date = f"{raw_date}, {section_date[:4]}"
        return self.parse_date(raw_date)

    def _model_ids_before_replacement_text(self, text: str) -> list[str]:
        model_text = re.split(
            r"\b(?:Use|See|Refer|instead|now points to|redirected to)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return [
            model_id
            for model_id in re.findall(
                r"\b(?:gemini|embedding|text-embedding|imagen|veo|lyria)-[A-Za-z0-9_.-]+\b",
                model_text,
            )
            if self._looks_like_model_id(model_id)
        ]

    def _changelog_item(
        self, model_id: str, announcement_date: str, shutdown_date: str, context: str
    ) -> DeprecationItem:
        return DeprecationItem(
            provider=self.provider_name,
            model_id=model_id,
            announcement_date=announcement_date,
            shutdown_date=shutdown_date,
            replacement_models=None,
            deprecation_context=context,
            url=f"{self.changelog_url}#{announcement_date.replace('-', '')}",
        )

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Gemini deprecations are extracted from official structured sources."""
        return []
