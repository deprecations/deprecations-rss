"""Azure AI Foundry model deprecations scraper."""

from typing import Any, List
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class AzureFoundryScraper(EnhancedBaseScraper):
    """Scraper for Azure AI Foundry model lifecycle and deprecations page."""

    provider_name = "Azure"
    url = "https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/model-lifecycle-retirement"
    requires_playwright = False  # Microsoft Learn pages are static HTML

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Azure AI Foundry's model lifecycle table."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")

        for table in tables:
            headers = []
            header_row = table.find("tr")
            if not header_row:
                continue

            for th in header_row.find_all(["th", "td"]):
                headers.append(th.get_text(strip=True).upper())

            header_text = " ".join(headers).upper()
            keywords = ["MODEL", "RETIREMENT", "DEPRECATION", "LEGACY"]
            if not any(keyword in header_text for keyword in keywords):
                continue

            model_idx = None
            legacy_idx = None
            deprecation_idx = None
            retirement_idx = None
            replacement_idx = None

            for i, header in enumerate(headers):
                if "REPLACEMENT" in header or "SUGGESTED" in header:
                    replacement_idx = i
                elif "MODEL" in header and model_idx is None:
                    model_idx = i
                elif "LEGACY" in header:
                    legacy_idx = i
                elif "DEPRECATION" in header:
                    deprecation_idx = i
                elif "RETIREMENT" in header or "RETIRE" in header:
                    retirement_idx = i

            if model_idx is None or retirement_idx is None:
                continue

            rows = table.find_all("tr")[1:]

            for row in rows:
                cells = row.find_all("td")
                if len(cells) <= max(model_idx, retirement_idx):
                    continue

                model_id = self._extract_model_id_from_cell(cells[model_idx])
                if not model_id:
                    continue

                retirement_cell = cells[retirement_idx].get_text(strip=True)
                retirement_date = self.parse_date(retirement_cell)
                if not retirement_date:
                    continue

                announcement_date = retirement_date
                if deprecation_idx is not None and deprecation_idx < len(cells):
                    dep_text = cells[deprecation_idx].get_text(strip=True)
                    parsed_dep = self.parse_date(dep_text)
                    if parsed_dep:
                        announcement_date = parsed_dep

                if legacy_idx is not None and legacy_idx < len(cells):
                    legacy_text = cells[legacy_idx].get_text(strip=True)
                    parsed_legacy = self.parse_date(legacy_text)
                    if parsed_legacy and (
                        not announcement_date or parsed_legacy < announcement_date
                    ):
                        announcement_date = parsed_legacy

                replacement_models = None
                if replacement_idx is not None and replacement_idx < len(cells):
                    replacement_models = self._extract_replacement_models(
                        cells[replacement_idx]
                    )

                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_id,
                        announcement_date=announcement_date,
                        shutdown_date=retirement_date,
                        replacement_models=replacement_models,
                        deprecation_context=self._build_context(table, model_id),
                        url=f"{self.url}#timelines-for-foundry-models",
                    )
                )

        return items

    def _extract_model_id_from_cell(self, cell: Any) -> str:
        """Extract a stable model identifier from a model table cell."""
        for anchor in cell.find_all("a"):
            model_id = self._extract_model_id_from_href(anchor.get("href", ""))
            if model_id:
                return model_id

        text = cell.get_text(" ", strip=True)
        return self._normalize_identifier_text(text)

    def _extract_replacement_models(self, cell: Any) -> list[str] | None:
        """Extract stable replacement identifiers from the replacement cell."""
        identifiers: list[str] = []

        for anchor in cell.find_all("a"):
            model_id = self._extract_model_id_from_href(anchor.get("href", ""))
            if model_id and model_id not in identifiers:
                identifiers.append(model_id)

        if identifiers:
            return identifiers

        text = cell.get_text(" ", strip=True)
        if not text or text in ["—", "-", "N/A", "TBD", "NONE"]:
            return None

        parsed = [
            identifier
            for identifier in (
                self._normalize_identifier_text(part)
                for part in self.parse_replacements(text)
            )
            if identifier
        ]
        return parsed or None

    def _extract_model_id_from_href(self, href: str) -> str:
        """Extract a model identifier from known Azure model/replacement links."""
        if not href:
            return ""

        explore_match = re.search(r"/explore/models/([^/]+)/", href)
        if explore_match:
            return explore_match.group(1)

        parsed = urlparse(href)
        path_parts = [part for part in parsed.path.split("/") if part]
        if "landing" in path_parts:
            landing_idx = path_parts.index("landing")
            if landing_idx + 1 < len(path_parts):
                return path_parts[landing_idx + 1]

        return ""

    def _normalize_identifier_text(self, text: str) -> str:
        """Keep only identifier-like text; reject display labels."""
        cleaned = text.strip()
        if not cleaned or cleaned.upper() in ["N/A", "TBD", "NONE", "—", "-"]:
            return ""
        if " " in cleaned:
            return ""
        return cleaned

    def _build_context(self, table: Any, model_id: str) -> str:
        """Build context information for the deprecation."""
        context_parts = []

        current = table.find_previous_sibling()
        while current and len(context_parts) < 3:
            if hasattr(current, "get_text"):
                text = current.get_text(strip=True)
                if text and len(text) < 200:
                    context_parts.insert(0, text)
                    if current.name in ["h1", "h2", "h3", "h4"]:
                        break
            current = current.find_previous_sibling()

        context = " ".join(context_parts)
        if context:
            return context
        return f"Model lifecycle retirement information for {model_id}"

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Azure AI Foundry page has structured tables, so this is not needed."""
        return []
