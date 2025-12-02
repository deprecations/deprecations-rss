"""Anthropic deprecations scraper with individual model extraction."""

from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class AnthropicScraper(EnhancedBaseScraper):
    """Scraper for Anthropic deprecations page."""

    provider_name = "Anthropic"
    url = "https://docs.anthropic.com/en/docs/about-claude/model-deprecations"
    requires_playwright = True  # Client-side rendering

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Anthropic's table format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content - use body as fallback since Anthropic doesn't use <main>
        main = soup.find("main") or soup.find("article") or soup.find("body") or soup

        for table in main.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]

            # Detect format by first header
            is_format2 = "retirement date" in headers[0].lower()

            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) < 2:
                    continue

                if is_format2:
                    # Format 2: Retirement Date | Deprecated Model | Replacement
                    shutdown_date = self.parse_date(cells[0])
                    model_name = cells[1]
                    replacement_str = (
                        cells[2]
                        if len(cells) > 2 and cells[2] not in ["—", "-", "N/A"]
                        else None
                    )
                    replacement_models = self.parse_replacements(replacement_str) if replacement_str else None
                    deprecated_date = ""
                else:
                    # Format 1: API Model Name | State | Deprecated | Tentative Retirement Date
                    model_name = cells[0]
                    deprecated_date = (
                        self.parse_date(cells[2]) if len(cells) > 2 else ""
                    )
                    shutdown_date = self.parse_date(cells[3]) if len(cells) > 3 else ""
                    replacement_models = None

                    # Skip active models with N/A deprecation
                    if cells[2].strip().upper() == "N/A":
                        continue

                # Use shutdown date, fall back to deprecated date
                final_date = shutdown_date or deprecated_date
                if not final_date or not model_name:
                    continue

                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date=deprecated_date or "",
                        shutdown_date=final_date,
                        replacement_models=replacement_models,
                        deprecation_context="",
                        url=self.url,
                    )
                )

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Anthropic uses tables, so no unstructured extraction needed."""
        return []
