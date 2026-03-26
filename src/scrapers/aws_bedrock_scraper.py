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
        """Extract deprecations from AWS Bedrock lifecycle tables."""
        items: list[DeprecationItem] = []
        soup = BeautifulSoup(html, "html.parser")

        content = soup.find("div", id="main-content") or soup.find("main")
        if not content:
            return items

        active_model_ids = self._build_active_model_id_map(content)

        for table in content.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            expanded_rows = self._expand_table_rows(table)
            headers = [header.lower() for header in expanded_rows[0]]

            is_lifecycle_table = any("legacy" in header for header in headers)
            if not is_lifecycle_table:
                continue

            model_version_idx = None
            model_id_idx = None
            legacy_idx = None
            eol_idx = None
            replacement_idx = None
            replacement_id_idx = None

            for i, header in enumerate(headers):
                if "model id" in header and "recommended" not in header and model_id_idx is None:
                    model_id_idx = i
                elif (
                    "model version" in header or "model name" in header
                ) and model_version_idx is None:
                    model_version_idx = i
                elif "legacy" in header and "date" in header:
                    legacy_idx = i
                elif ("eol" in header or "end of life" in header) and "date" in header:
                    eol_idx = i
                elif "recommended model id" in header and replacement_id_idx is None:
                    replacement_id_idx = i
                elif (
                    "replac" in header or "migration" in header
                ) and "id" not in header and replacement_idx is None:
                    replacement_idx = i

            if model_version_idx is None and model_id_idx is None:
                continue

            for cells in expanded_rows[1:]:
                model_version = (
                    cells[model_version_idx]
                    if model_version_idx is not None and model_version_idx < len(cells)
                    else ""
                )
                direct_model_id = (
                    cells[model_id_idx]
                    if model_id_idx is not None and model_id_idx < len(cells)
                    else ""
                )
                model_id = direct_model_id or active_model_ids.get(model_version, "")

                if not model_id or model_id.lower() in ["model", "name"]:
                    continue

                legacy_date = ""
                if legacy_idx is not None and legacy_idx < len(cells):
                    legacy_date = self.parse_date(cells[legacy_idx])

                eol_date = ""
                if eol_idx is not None and eol_idx < len(cells):
                    eol_date = self.parse_date(cells[eol_idx])

                replacement_models = None
                replacement_text = ""
                if replacement_id_idx is not None and replacement_id_idx < len(cells):
                    replacement_text = cells[replacement_id_idx]
                elif replacement_idx is not None and replacement_idx < len(cells):
                    replacement_text = cells[replacement_idx]
                if replacement_text and replacement_text not in ["—", "-", "N/A", "TBD", "NA"]:
                    replacement_models = self.parse_replacements(replacement_text)

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
                            model_id, model_version, legacy_date, eol_date, replacement_models
                        ),
                        url=self.url,
                    )
                )

        return self._merge_duplicate_models(items)

    def _build_active_model_id_map(self, content) -> dict[str, str]:
        """Map active model version labels to Bedrock model IDs."""
        active_model_ids: dict[str, str] = {}

        for table in content.find_all("table"):
            header = table.find_previous(["h2", "h3"])
            heading_text = header.get_text(" ", strip=True).lower() if header else ""
            if "active versions" not in heading_text:
                continue

            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            headers = [
                cell.get_text(" ", strip=True).lower()
                for cell in rows[0].find_all(["th", "td"])
            ]
            if "model id" not in headers:
                continue

            model_version_idx = next(
                (i for i, header in enumerate(headers) if header in {"model name", "model version"}),
                None,
            )
            model_id_idx = headers.index("model id")
            if model_version_idx is None:
                continue

            for row in rows[1:]:
                cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
                if len(cells) <= max(model_version_idx, model_id_idx):
                    continue
                model_version = cells[model_version_idx]
                model_id = cells[model_id_idx]
                if model_version and model_id:
                    active_model_ids[model_version] = model_id

        return active_model_ids

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
        model_version: str,
        legacy_date: str,
        eol_date: str,
        replacement_models: list[str] | None,
    ) -> str:
        """Build standardized context for a single lifecycle row."""
        context_parts = [f"Model ID {model_id}"]
        if model_version and model_version != model_id:
            context_parts.append(f"({model_version})")
        if legacy_date:
            context_parts.append(f"entered legacy status on {legacy_date}")
        if eol_date:
            if legacy_date:
                context_parts.append(f"and will reach end-of-life on {eol_date}")
            else:
                context_parts.append(f"will reach end-of-life on {eol_date}")
        if replacement_models:
            context_parts.append(
                f"Recommended replacement IDs: {', '.join(replacement_models)}"
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
