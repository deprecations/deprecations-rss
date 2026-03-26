"""Enhanced base scraper with caching and structured data extraction."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, List

import httpx

from .cache_manager import CacheManager
from .models import DeprecationItem


class EnhancedBaseScraper:
    """Base scraper with caching and enhanced extraction capabilities."""

    provider_name: str = "Unknown"
    url: str = ""
    requires_playwright: bool = False

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.client = httpx.Client(
            timeout=30, headers=self.headers, follow_redirects=True
        )
        self.cache_manager = CacheManager()

    def get_source_url(self) -> str:
        """Return the URL that should actually be fetched."""
        return self.url

    def fetch_with_httpx(self, url: str) -> str:
        """Fetch content using httpx."""
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def fetch_html(self, url: str) -> str:
        """Fetch provider content, using cache if available."""
        cached_html = self.cache_manager.get_cached_html(self.provider_name, url)
        if cached_html:
            print(f"  → Using cached content for {self.provider_name}")
            return cached_html

        print(f"  → Fetching fresh content for {self.provider_name}")
        html = self.fetch_with_httpx(url)
        self.cache_manager.save_html(self.provider_name, url, html)
        return html

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from structured content. Override in subclasses."""
        return []

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from unstructured text. Override in subclasses."""
        return []

    def parse_date(self, date_str: str) -> str:
        """Parse various date formats to ISO format."""
        if not date_str:
            return ""

        normalized = (
            date_str.replace("\xa0", " ")
            .replace("\u2010", "-")
            .replace("\u2011", "-")
            .replace("\u2012", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
            .replace("\u2212", "-")
            .strip()
        )

        normalized = re.sub(
            r"^(?:no\s+sooner\s+than|not\s+sooner\s+than|at\s+earliest|on)\s+",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = normalized.rstrip(". ")
        normalized = re.sub(r"\s*\([^)]*\)\s*", "", normalized).strip()
        normalized = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", normalized)

        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", normalized)
        if iso_match:
            return iso_match.group(0)

        month_match = re.search(
            r"([A-Za-z]+\s+\d{1,2},\s*\d{4}|\d{1,2}/\d{1,2}/\d{4})",
            normalized,
        )
        if month_match:
            normalized = month_match.group(1)

        if re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
            return normalized

        formats = [
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(normalized.strip(), fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return ""

    def parse_replacements(self, replacement_str: str) -> List[str] | None:
        """Parse replacement string into a list of model names."""
        if not replacement_str:
            return None

        normalized = replacement_str
        for separator in [" and ", " or ", ", "]:
            normalized = normalized.replace(separator, "|")

        if "or" in normalized and "|" not in normalized:
            parts = normalized.split("or")
            if len(parts) == 2:
                left, right = parts
                if ("-" in left or any(char.isdigit() for char in left)) and (
                    "-" in right or any(char.isdigit() for char in right)
                ):
                    normalized = normalized.replace("or", "|")

        models = [model.strip() for model in normalized.split("|") if model.strip()]
        return models if models else None

    def scrape(self) -> List[DeprecationItem]:
        """Main scraping method."""
        try:
            source_url = self.get_source_url()
            html = self.fetch_html(source_url)
            structured_items = self.extract_structured_deprecations(html)
            unstructured_items = self.extract_unstructured_deprecations(html)
            all_items = structured_items + unstructured_items

            seen = set()
            unique_items = []
            for item in all_items:
                if (item.provider, item.model_id) not in seen:
                    seen.add((item.provider, item.model_id))
                    unique_items.append(item)

            return unique_items
        except Exception as exc:
            print(f"✗ Error scraping {self.provider_name}: {exc}")
            raise

    def extract_table_deprecations(
        self,
        table: Any,
        section_context: str = "",
        announcement_date: str = "",
    ) -> List[DeprecationItem]:
        """Common method to extract deprecations from HTML tables."""
        items = []
        rows = table.find_all("tr")
        if len(rows) <= 1:
            return items

        headers = [
            th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])
        ]

        model_cols = ["model", "system", "deprecated model", "feature", "name"]
        date_cols = [
            "shutdown date",
            "retirement date",
            "eol",
            "end of life",
            "deprecated",
            "legacy",
        ]
        replacement_cols = [
            "replacement",
            "recommended replacement",
            "migration",
            "alternative",
        ]

        model_idx = next(
            (
                idx
                for idx, header in enumerate(headers)
                for col in model_cols
                if col in header
            ),
            None,
        )
        date_idx = next(
            (
                idx
                for idx, header in enumerate(headers)
                for col in date_cols
                if col in header
            ),
            None,
        )
        replacement_idx = next(
            (
                idx
                for idx, header in enumerate(headers)
                for col in replacement_cols
                if col in header
            ),
            None,
        )

        if model_idx is None:
            return items

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) <= model_idx:
                continue

            model_name = cells[model_idx]
            if not model_name or model_name.lower() in ["model", "name", "feature"]:
                continue

            shutdown_date = ""
            if date_idx is not None and date_idx < len(cells):
                shutdown_date = self.parse_date(cells[date_idx])

            replacement_models = None
            if replacement_idx is not None and replacement_idx < len(cells):
                replacement_text = cells[replacement_idx]
                if replacement_text and replacement_text not in [
                    "—",
                    "-",
                    "N/A",
                    "None",
                ]:
                    replacement_models = self.parse_replacements(replacement_text)

            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_name,
                    model_name=model_name,
                    announcement_date=announcement_date or shutdown_date,
                    shutdown_date=shutdown_date,
                    replacement_models=replacement_models,
                    deprecation_context=section_context,
                    url=self.url,
                    content_hash=DeprecationItem._compute_hash(
                        f"{model_name}{shutdown_date}{section_context}"
                    ),
                )
            )

        return items
