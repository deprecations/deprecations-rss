"""Google Vertex AI partner-model deprecations scraper."""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class GoogleVertexScraper(EnhancedBaseScraper):
    """Scraper for Google Vertex AI partner-model deprecation notices."""

    provider_name = "Google Vertex"
    url = "https://docs.cloud.google.com/vertex-ai/generative-ai/docs/deprecations/partner-models"
    requires_playwright = False

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract partner-model deprecations from Google's HTML page."""
        items = []
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return items

        for section_header in content.find_all("h2"):
            section_name = section_header.get_text(" ", strip=True)
            section_nodes = []
            sibling = section_header.next_sibling
            while sibling:
                if getattr(sibling, "name", None) == "h2":
                    break
                if hasattr(sibling, "get_text"):
                    section_nodes.append(sibling)
                sibling = sibling.next_sibling

            section_text = " ".join(
                node.get_text(" ", strip=True)
                for node in section_nodes
                if node.get_text(" ", strip=True)
            )
            if (
                "deprecated as of" not in section_text.lower()
                or "shut down on" not in section_text.lower()
            ):
                continue

            deprecated_match = re.search(
                r"deprecated as of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                section_text,
                re.IGNORECASE,
            )
            shutdown_match = re.search(
                r"shut down on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                section_text,
                re.IGNORECASE,
            )
            if not deprecated_match or not shutdown_match:
                continue

            model_id = self._extract_model_id(section_nodes) or section_name
            if not model_id:
                continue

            items.append(
                DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_id,
                    model_name=section_name,
                    announcement_date=self.parse_date(deprecated_match.group(1)),
                    shutdown_date=self.parse_date(shutdown_match.group(1)),
                    replacement_models=None,
                    deprecation_context=section_text,
                    url=f"{self.url}#{section_header.get('id', '')}",
                )
            )

        return items

    def _extract_model_id(self, section_nodes: list) -> str:
        """Extract the model ID from a section's metadata table."""
        for node in section_nodes:
            if getattr(node, "name", None) != "table":
                continue
            for row in node.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) < 2:
                    continue
                label = cells[0].get_text(" ", strip=True).lower()
                value = cells[1].get_text(" ", strip=True)
                if label == "model id" and value:
                    return value
        return ""

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Google partner-model deprecations are structured in section content."""
        return []
