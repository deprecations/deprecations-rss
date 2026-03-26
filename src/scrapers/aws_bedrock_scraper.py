"""AWS Bedrock deprecations scraper with individual model extraction."""

from datetime import datetime
from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class AWSBedrockScraper(EnhancedBaseScraper):
    """Scraper for AWS Bedrock model lifecycle page."""

    provider_name = "AWS Bedrock"
    url = "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html"
    requires_playwright = False

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from AWS Bedrock's table format."""
        items: list[DeprecationItem] = []
        soup = BeautifulSoup(html, "html.parser")

        content = soup.find("div", id="main-content") or soup.find("main")
        if not content:
            return items

        for table in content.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            expanded_rows = self._expand_table_rows(table)
            headers = [header.lower() for header in expanded_rows[0]]

            is_lifecycle_table = any("legacy" in header for header in headers)
            if not is_lifecycle_table:
                continue

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

            if model_idx is None:
                model_idx = 0

            for cells in expanded_rows[1:]:
                if len(cells) <= model_idx:
                    continue

                model_id = cells[model_idx]
                if not model_id or model_id.lower() in ["model", "name"]:
                    continue

                legacy_date = ""
                if legacy_idx is not None and legacy_idx < len(cells):
                    legacy_date = self.parse_date(cells[legacy_idx])

                eol_date = ""
                if eol_idx is not None and eol_idx < len(cells):
                    eol_date = self.parse_date(cells[eol_idx])

                replacement_models = None
                if replacement_idx is not None and replacement_idx < len(cells):
                    repl_text = cells[replacement_idx]
                    if repl_text and repl_text not in ["—", "-", "N/A", "TBD", "NA"]:
                        replacement_models = self.parse_replacements(repl_text)

                if not (legacy_date or eol_date):
                    continue

                items.append(
                    DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_id,
                        announcement_date=legacy_date or eol_date,
                        shutdown_date=eol_date or legacy_date,
                        replacement_models=replacement_models,
                        deprecation_context=self._build_context(
                            model_id, legacy_date, eol_date, replacement_models
                        ),
                        url=self.url,
                    )
                )

        return self._merge_duplicate_models(items)

    def _expand_table_rows(self, table) -> list[list[str]]:
        """Expand rowspans so each row has a full set of cells."""
        raw_rows = table.find_all("tr")
        if not raw_rows:
            return []

        header_cells = raw_rows[0].find_all(["th", "td"])
        total_cols = len(header_cells)
        expanded_rows: list[list[str]] = []
        rowspans: dict[int, list[str | int]] = {}

        for row in raw_rows:
            rendered: list[str] = []
            cells = row.find_all(["th", "td"])
            cell_idx = 0

            for col_idx in range(total_cols):
                if col_idx in rowspans and rowspans[col_idx][0] > 0:
                    rendered.append(str(rowspans[col_idx][1]))
                    rowspans[col_idx][0] -= 1
                    if rowspans[col_idx][0] == 0:
                        del rowspans[col_idx]
                    continue

                if cell_idx >= len(cells):
                    rendered.append("")
                    continue

                cell = cells[cell_idx]
                cell_idx += 1
                text = cell.get_text(" ", strip=True)
                rendered.append(text)

                rowspan = int(cell.get("rowspan", 1))
                if rowspan > 1:
                    rowspans[col_idx] = [rowspan - 1, text]

            expanded_rows.append(rendered)

        return expanded_rows

    def _build_context(
        self,
        model_id: str,
        legacy_date: str,
        eol_date: str,
        replacement_models: list[str] | None,
    ) -> str:
        """Build standardized context for a single lifecycle row."""
        context_parts = [f"Model {model_id}"]
        if legacy_date:
            context_parts.append(f"entered legacy status on {legacy_date}")
        if eol_date:
            if legacy_date:
                context_parts.append(f"and will reach end-of-life on {eol_date}")
            else:
                context_parts.append(f"will reach end-of-life on {eol_date}")
        if replacement_models:
            context_parts.append(
                f"Recommended replacement: {', '.join(replacement_models)}"
            )
        return ". ".join(context_parts) + "."

    def _merge_duplicate_models(
        self, items: list[DeprecationItem]
    ) -> list[DeprecationItem]:
        """Merge duplicate rows that represent different regional schedules."""
        by_model: dict[str, DeprecationItem] = {}

        for item in items:
            existing = by_model.get(item.model_id)
            if existing is None:
                by_model[item.model_id] = item
                continue

            existing.announcement_date = self._earliest_date(
                existing.announcement_date, item.announcement_date
            )
            existing.shutdown_date = self._earliest_date(
                existing.shutdown_date, item.shutdown_date
            )

            if item.deprecation_context not in existing.deprecation_context:
                existing.deprecation_context += (
                    f" Additional regional schedule: {item.deprecation_context}"
                )

            if not existing.replacement_models and item.replacement_models:
                existing.replacement_models = item.replacement_models

        return list(by_model.values())

    def _earliest_date(self, left: str, right: str) -> str:
        """Return the earliest non-empty ISO date."""
        if not left:
            return right
        if not right:
            return left
        left_dt = datetime.fromisoformat(left)
        right_dt = datetime.fromisoformat(right)
        return left if left_dt <= right_dt else right

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """AWS uses tables, so no unstructured extraction needed."""
        return []
