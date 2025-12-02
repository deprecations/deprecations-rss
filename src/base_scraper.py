"""Enhanced base scraper with caching and structured data extraction."""

import httpx
import re
from typing import List, Any
from playwright.sync_api import sync_playwright
from datetime import datetime

from .cache_manager import CacheManager
from .models import DeprecationItem


class EnhancedBaseScraper:
    """Base scraper with caching and enhanced extraction capabilities."""

    provider_name: str = "Unknown"
    url: str = ""
    requires_playwright: bool = False

    def __init__(self):
        # Browser-like headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        self.client = httpx.Client(
            timeout=30, headers=self.headers, follow_redirects=True
        )
        self.cache_manager = CacheManager()

    def fetch_with_httpx(self, url: str) -> str:
        """Fetch content using httpx (for simple pages)."""
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def fetch_with_playwright(self, url: str) -> str:
        """Fetch content using Playwright (for JS-heavy pages)."""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.headers["User-Agent"],
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)  # Wait for dynamic content
                html = page.content()
            finally:
                browser.close()

            return html

    def fetch_html(self, url: str) -> str:
        """Fetch HTML, using cache if available."""
        # Check cache first
        cached_html = self.cache_manager.get_cached_html(self.provider_name, url)
        if cached_html:
            print(f"  → Using cached HTML for {self.provider_name}")
            return cached_html

        # Fetch fresh content
        print(f"  → Fetching fresh content for {self.provider_name}")
        if self.requires_playwright:
            html = self.fetch_with_playwright(url)
        else:
            html = self.fetch_with_httpx(url)

        # Save to cache
        self.cache_manager.save_html(self.provider_name, url, html)

        return html

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from structured HTML (tables, etc). Override in subclasses."""
        return []

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from unstructured text. Override in subclasses."""
        return []

    def parse_date(self, date_str: str) -> str:
        """Parse various date formats to ISO format."""
        if not date_str:
            return ""

        # Strip region/context information in parentheses
        # e.g., "May 20, 2025 (us-east-1 and us-west-2)" -> "May 20, 2025"
        date_str = re.sub(r"\s*\([^)]*\)\s*", "", date_str).strip()

        # Already in ISO format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

        # Common formats to try
        formats = [
            "%B %d, %Y",  # January 31, 2025
            "%b %d, %Y",  # Jan 31, 2025
            "%B %dth, %Y",  # July 15th, 2025
            "%b %dth, %Y",  # Jul 15th, 2025
            "%Y-%m-%d",  # 2025-01-31
            "%m/%d/%Y",  # 01/31/2025
            "%d/%m/%Y",  # 31/01/2025
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return ""

    def parse_replacements(self, replacement_str: str) -> List[str] | None:
        """Parse replacement string into list of model names.

        Handles cases like:
        - "gpt-4" -> ["gpt-4"]
        - "gpt-4 and gpt-4-turbo" -> ["gpt-4", "gpt-4-turbo"]
        - "gpt-4 or gpt-4-turbo" -> ["gpt-4", "gpt-4-turbo"]
        - "gpt-image-1orgpt-image-1-mini" -> ["gpt-image-1", "gpt-image-1-mini"]
        - None -> None
        """
        if not replacement_str:
            return None

        # Split on common separators (and, or, comma)
        # First normalize the separators
        normalized = replacement_str
        for separator in [" and ", " or ", ", "]:
            normalized = normalized.replace(separator, "|")

        # Handle concatenated "or" without spaces (e.g., "model1ormodel2")
        # Only split if it looks like model names on both sides
        # (contains hyphens or numbers, typical of model identifiers)
        if "or" in normalized and "|" not in normalized:
            # Check if it looks like concatenated model names
            parts = normalized.split("or")
            if len(parts) == 2:
                left, right = parts
                # If both sides look like model names (contain hyphen or digit), split on "or"
                if ("-" in left or any(c.isdigit() for c in left)) and (
                    "-" in right or any(c.isdigit() for c in right)
                ):
                    normalized = normalized.replace("or", "|")

        # Split and clean up
        models = [m.strip() for m in normalized.split("|") if m.strip()]

        return models if models else None

    def scrape(self) -> List[DeprecationItem]:
        """Main scraping method."""
        try:
            html = self.fetch_html(self.url)

            # Try structured extraction first
            structured_items = self.extract_structured_deprecations(html)

            # Then unstructured
            unstructured_items = self.extract_unstructured_deprecations(html)

            # Combine and deduplicate
            all_items = structured_items + unstructured_items

            # Deduplicate by model_id
            seen = set()
            unique_items = []
            for item in all_items:
                if (item.provider, item.model_id) not in seen:
                    seen.add((item.provider, item.model_id))
                    unique_items.append(item)

            return unique_items

        except Exception as e:
            print(f"✗ Error scraping {self.provider_name}: {e}")
            raise

    def extract_table_deprecations(
        self,
        table: Any,  # BeautifulSoup table element
        section_context: str = "",
        announcement_date: str = "",
    ) -> List[DeprecationItem]:
        """Common method to extract deprecations from HTML tables."""
        items = []
        rows = table.find_all("tr")

        if len(rows) <= 1:
            return items

        # Extract headers to understand column positions
        headers = []
        header_row = rows[0]
        for th in header_row.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True).lower())

        # Common column name patterns
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

        # Find column indices
        model_idx = next(
            (i for i, h in enumerate(headers) for m in model_cols if m in h), None
        )
        date_idx = next(
            (i for i, h in enumerate(headers) for d in date_cols if d in h), None
        )
        replacement_idx = next(
            (i for i, h in enumerate(headers) for r in replacement_cols if r in h), None
        )

        if model_idx is None:
            return items

        # Extract data from each row
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
                repl = cells[replacement_idx]
                if repl and repl not in ["—", "-", "N/A", "None"]:
                    replacement_models = self.parse_replacements(repl)

            # Create deprecation item
            item = DeprecationItem(
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

            items.append(item)

        return items
