"""AWS Bedrock deprecations scraper with individual model extraction."""

from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class AWSBedrockScraper(EnhancedBaseScraper):
    """Scraper for AWS Bedrock model lifecycle page."""

    provider_name = "AWS Bedrock"
    url = "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html"
    requires_playwright = False  # Can try httpx first

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from AWS Bedrock's table format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        content = soup.find("div", id="main-content") or soup.find("main")
        if not content:
            return items

        # AWS uses tables for model lifecycle
        for table in content.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            # Check headers to identify deprecation tables
            headers = [
                th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])
            ]

            # Look for tables with legacy/EOL columns
            is_lifecycle_table = any(
                keyword in " ".join(headers)
                for keyword in ["legacy", "eol", "end of life", "deprecat"]
            )

            if not is_lifecycle_table:
                continue

            # Find column indices
            model_idx = None
            legacy_idx = None
            eol_idx = None
            replacement_idx = None

            for i, header in enumerate(headers):
                if (
                    "model version" in header or "model name" in header
                ) and model_idx is None:
                    model_idx = i
                elif "legacy" in header and "date" in header:
                    legacy_idx = i
                elif ("eol" in header or "end of life" in header) and "date" in header:
                    eol_idx = i
                elif (
                    "replac" in header or "migration" in header
                ) and "id" not in header:
                    replacement_idx = i

            # Default to positional
            if model_idx is None:
                model_idx = 0

            # Process each row
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]

                if len(cells) <= model_idx:
                    continue

                model_name = cells[model_idx]

                # Skip empty or header rows
                if not model_name or model_name.lower() in ["model", "name"]:
                    continue

                # Extract dates
                legacy_date = ""
                if legacy_idx is not None and legacy_idx < len(cells):
                    legacy_date = self.parse_date(cells[legacy_idx])

                eol_date = ""
                if eol_idx is not None and eol_idx < len(cells):
                    eol_date = self.parse_date(cells[eol_idx])

                # Extract replacement
                replacement_models = None
                if replacement_idx is not None and replacement_idx < len(cells):
                    repl_text = cells[replacement_idx]
                    if repl_text and repl_text not in ["—", "-", "N/A", "TBD"]:
                        replacement_models = self.parse_replacements(repl_text)

                # Build context
                context_parts = [f"Model {model_name}"]
                if legacy_date:
                    context_parts.append(f"entered legacy status on {legacy_date}")
                if eol_date:
                    if legacy_date:
                        context_parts.append(
                            f"and will reach end-of-life on {eol_date}"
                        )
                    else:
                        context_parts.append(f"will reach end-of-life on {eol_date}")
                if replacement_models:
                    replacement_str = ", ".join(replacement_models)
                    context_parts.append(f"Recommended replacement: {replacement_str}")

                context = ". ".join(context_parts) + "."

                # Create deprecation item
                if legacy_date or eol_date:
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date=legacy_date or eol_date,
                        shutdown_date=eol_date or legacy_date,
                        replacement_models=replacement_models,
                        deprecation_context=context,
                        url=self.url,
                    )
                    items.append(item)

        # If no tables found with httpx, might need playwright
        if not items and not self.requires_playwright:
            print(
                f"  → No tables found with httpx, trying Playwright for {self.provider_name}"
            )
            self.requires_playwright = True
            html = self.fetch_html(self.url)
            return self.extract_structured_deprecations(html)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """AWS uses tables, so no unstructured extraction needed."""
        return []
