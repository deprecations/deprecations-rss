"""Google Vertex AI model availability scraper for tracking model lifecycle."""

import re
from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class GoogleVertexModelsScraper(EnhancedBaseScraper):
    """Scraper for Google Vertex AI model availability and lifecycle page."""

    provider_name = "Google Vertex AI"
    url = "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models"
    requires_playwright = False  # Static content, httpx is fine

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract model lifecycle information from Google's models page."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return items

        # Look for deprecation notices in the model lifecycle section
        sections = content.find_all(["h2", "h3", "h4"])

        for section_header in sections:
            section_title = section_header.get_text(strip=True)

            # Look for lifecycle, deprecation, or availability sections
            if not any(
                keyword in section_title.lower()
                for keyword in [
                    "lifecycle",
                    "deprecat",
                    "availab",
                    "sunset",
                    "retire",
                    "discontinu",
                ]
            ):
                continue

            # Look for deprecation info after the header
            next_elem = section_header.next_sibling
            deprecation_date = ""
            shutdown_date = ""
            context_parts = []

            while next_elem:
                if hasattr(next_elem, "name"):
                    if next_elem.name in ["h2", "h3", "h4"]:
                        # Next section
                        break

                    text = next_elem.get_text(strip=True)

                    # Look for date patterns
                    date_patterns = [
                        r"deprecated[:\s]+([^.]+)",
                        r"sunset[:\s]+([^.]+)",
                        r"retire[sd][:\s]+([^.]+)",
                        r"end[s]?[:\s]+([^.]+)",
                        r"discontinu[ed][:\s]+([^.]+)",
                        r"available until[:\s]+([^.]+)",
                        r"support ends?[:\s]+([^.]+)",
                    ]

                    for pattern in date_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            date_str = match.group(1).strip()
                            parsed_date = self.parse_date(date_str)
                            if parsed_date:
                                if not deprecation_date:
                                    deprecation_date = parsed_date
                                if not shutdown_date:
                                    shutdown_date = parsed_date

                    # Collect context
                    if text:
                        context_parts.append(text)

                    # Look for tables with model information
                    if next_elem.name == "table":
                        rows = next_elem.find_all("tr")
                        if len(rows) > 1:
                            # Parse table headers
                            headers = [
                                th.get_text(strip=True).lower()
                                for th in rows[0].find_all(["th", "td"])
                            ]

                            # Find relevant columns
                            model_idx = None
                            status_idx = None
                            date_idx = None

                            for i, header in enumerate(headers):
                                if "model" in header or "name" in header:
                                    model_idx = i
                                elif any(
                                    word in header
                                    for word in ["status", "availab", "lifecycle"]
                                ):
                                    status_idx = i
                                elif any(
                                    word in header for word in ["date", "until", "end"]
                                ):
                                    date_idx = i

                            # Process table rows
                            for row in rows[1:]:
                                cells = [
                                    td.get_text(strip=True) for td in row.find_all("td")
                                ]

                                if len(cells) <= (model_idx or 0):
                                    continue

                                model_name = (
                                    cells[model_idx] if model_idx is not None else ""
                                )
                                status = (
                                    cells[status_idx]
                                    if status_idx is not None
                                    and status_idx < len(cells)
                                    else ""
                                )
                                date = (
                                    cells[date_idx]
                                    if date_idx is not None and date_idx < len(cells)
                                    else ""
                                )

                                # Check if this row indicates deprecation
                                if any(
                                    keyword in (status + date).lower()
                                    for keyword in [
                                        "deprecat",
                                        "sunset",
                                        "retire",
                                        "discontinu",
                                        "end",
                                    ]
                                ):
                                    parsed_date = (
                                        self.parse_date(date) if date else shutdown_date
                                    )

                                    item = DeprecationItem(
                                        provider=self.provider_name,
                                        model_id=model_name.lower().replace(" ", "-"),
                                        model_name=model_name,
                                        announcement_date=deprecation_date,
                                        shutdown_date=parsed_date,
                                        replacement_models=None,
                                        deprecation_context=f"{status}. {' '.join(context_parts)}".strip(),
                                        url=f"{self.url}#{section_header.get('id', '')}",
                                    )
                                    items.append(item)

                    # Look for lists with model information
                    elif next_elem.name in ["ul", "ol"]:
                        for li in next_elem.find_all("li"):
                            li_text = li.get_text(strip=True)

                            # Look for model patterns and deprecation info
                            model_patterns = [
                                r"([\w-]+(?:\s+\d+)?)\s*[:-]",  # Model name followed by colon/dash
                                r"(text-\w+-\d+)",  # text-model patterns
                                r"(gpt-\w+)",  # gpt patterns
                                r"(palm-\w+)",  # palm patterns
                                r"(gemini-\w+)",  # gemini patterns
                                r"(claude-\w+)",  # claude patterns
                            ]

                            for pattern in model_patterns:
                                model_match = re.search(pattern, li_text, re.IGNORECASE)
                                if model_match:
                                    model_name = model_match.group(1)

                                    # Check if this item mentions deprecation/lifecycle
                                    if any(
                                        keyword in li_text.lower()
                                        for keyword in [
                                            "deprecat",
                                            "sunset",
                                            "retire",
                                            "discontinu",
                                            "end",
                                        ]
                                    ):
                                        # Try to extract date from the list item
                                        date_match = re.search(
                                            r"(\w+\s+\d{1,2},?\s+\d{4})", li_text
                                        )
                                        item_date = (
                                            self.parse_date(date_match.group(1))
                                            if date_match
                                            else shutdown_date
                                        )

                                        item = DeprecationItem(
                                            provider=self.provider_name,
                                            model_id=model_name.lower().replace(
                                                " ", "-"
                                            ),
                                            model_name=model_name,
                                            announcement_date=deprecation_date,
                                            shutdown_date=item_date,
                                            replacement_models=None,
                                            deprecation_context=li_text,
                                            url=f"{self.url}#{section_header.get('id', '')}",
                                        )
                                        items.append(item)
                                    break

                next_elem = next_elem.next_sibling

            # If we found dates but no specific models, create entry for the section
            if (deprecation_date or shutdown_date) and not any(
                item
                for item in items
                if item.deprecation_context == " ".join(context_parts)
            ):
                # Clean section title
                model_name = section_title
                if any(
                    word in model_name.lower()
                    for word in ["lifecycle", "deprecation", "availability"]
                ):
                    model_name = re.sub(
                        r"\b(?:lifecycle|deprecation|availability)\b",
                        "",
                        model_name,
                        flags=re.IGNORECASE,
                    ).strip()

                if model_name:
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name.lower().replace(" ", "-"),
                        model_name=model_name,
                        announcement_date=deprecation_date,
                        shutdown_date=shutdown_date,
                        replacement_models=None,
                        deprecation_context=" ".join(context_parts),
                        url=f"{self.url}#{section_header.get('id', '')}",
                    )
                    items.append(item)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Google models page is structured, so no unstructured extraction needed."""
        return []
