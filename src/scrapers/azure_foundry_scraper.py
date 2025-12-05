"""Azure AI Foundry model deprecations scraper."""

from typing import List, Any
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

        # Find tables containing model deprecation information
        tables = soup.find_all("table")

        for table in tables:
            # Look for tables with model lifecycle information
            headers = []
            header_row = table.find("tr")
            if not header_row:
                continue

            for th in header_row.find_all(["th", "td"]):
                headers.append(th.get_text(strip=True).upper())

            # Check if this looks like a model deprecation table
            header_text = " ".join(headers).upper()
            keywords = ["MODEL", "RETIREMENT", "DEPRECATION", "LEGACY"]
            if not any(keyword in header_text for keyword in keywords):
                continue

            # Find column indices
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

            # Extract rows
            rows = table.find_all("tr")[1:]  # Skip header row

            for row in rows:
                cells = row.find_all("td")
                if len(cells) <= max(model_idx, retirement_idx):
                    continue

                model_name = cells[model_idx].get_text(strip=True)
                if not model_name or model_name.upper() in [
                    "N/A",
                    "TBD",
                    "NONE",
                    "—",
                    "-",
                ]:
                    continue

                # Extract retirement date
                retirement_cell = cells[retirement_idx].get_text(strip=True)
                retirement_date = self.parse_date(retirement_cell)
                if not retirement_date:
                    continue

                # Extract deprecation date if available
                announcement_date = retirement_date  # Default to retirement date
                if deprecation_idx is not None and deprecation_idx < len(cells):
                    dep_text = cells[deprecation_idx].get_text(strip=True)
                    parsed_dep = self.parse_date(dep_text)
                    if parsed_dep:
                        announcement_date = parsed_dep

                # Extract legacy date if available and use as announcement if earlier
                if legacy_idx is not None and legacy_idx < len(cells):
                    legacy_text = cells[legacy_idx].get_text(strip=True)
                    parsed_legacy = self.parse_date(legacy_text)
                    if parsed_legacy and (
                        not announcement_date or parsed_legacy < announcement_date
                    ):
                        announcement_date = parsed_legacy

                # Extract replacement if available
                replacement_models = None
                if replacement_idx is not None and replacement_idx < len(cells):
                    repl_text = cells[replacement_idx].get_text(strip=True)
                    if repl_text and repl_text not in ["—", "-", "N/A", "TBD"]:
                        replacement_models = self.parse_replacements(repl_text)

                # Create deprecation item
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_name,
                    model_name=model_name,
                    announcement_date=announcement_date,
                    shutdown_date=retirement_date,
                    replacement_models=replacement_models,
                    deprecation_context=self._build_context(table, model_name),
                    url=f"{self.url}#timelines-for-foundry-models",
                )
                items.append(item)

        return items

    def _build_context(self, table: Any, model_name: str) -> str:
        """Build context information for the deprecation."""
        context_parts = []

        # Look for preceding headings or paragraphs that provide context
        current = table.find_previous_sibling()
        while current and len(context_parts) < 3:
            if hasattr(current, "get_text"):
                text = current.get_text(strip=True)
                if text and len(text) < 200:  # Avoid very long text blocks
                    context_parts.insert(0, text)
                    if current.name in ["h1", "h2", "h3", "h4"]:
                        break  # Stop at heading
            current = current.find_previous_sibling()

        context = " ".join(context_parts)
        if context:
            return context
        return f"Model lifecycle retirement information for {model_name}"

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Azure AI Foundry page has structured tables, so this is not needed."""
        return []
