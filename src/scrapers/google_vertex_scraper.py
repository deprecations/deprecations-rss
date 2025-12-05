"""Google Vertex AI deprecations scraper with individual model extraction."""

import re
from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class GoogleVertexScraper(EnhancedBaseScraper):
    """Scraper for Google Vertex AI deprecations page."""

    provider_name = "Google Vertex"
    url = "https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations"
    requires_playwright = False  # Static content, httpx is fine

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Google's format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return items

        # Google uses sections with h2 headers followed by deprecation info
        sections = content.find_all(["h2", "h3"])

        for section_header in sections:
            section_title = section_header.get_text(strip=True)

            # Look for deprecation info after the header
            next_elem = section_header.next_sibling
            deprecation_date = ""
            shutdown_date = ""
            context_parts = []

            while next_elem:
                if hasattr(next_elem, "name"):
                    if next_elem.name in ["h2", "h3"]:
                        # Next section
                        break

                    text = next_elem.get_text(strip=True)

                    # Look for deprecation/shutdown dates
                    if "Deprecation date:" in text or "deprecation date:" in text:
                        # Extract dates from format: "Deprecation date: June 24, 2025. Shutdown date: June 24, 2026."
                        dep_match = re.search(r"Deprecation date[:\s]+([^.]+)", text)
                        shut_match = re.search(r"Shutdown date[:\s]+([^.]+)", text)

                        if dep_match:
                            deprecation_date = self.parse_date(
                                dep_match.group(1).strip()
                            )
                        if shut_match:
                            shutdown_date = self.parse_date(shut_match.group(1).strip())

                    # Collect context
                    if text:
                        context_parts.append(text)

                    # Look for model lists
                    if next_elem.name == "ul":
                        # Extract individual models from list
                        for li in next_elem.find_all("li"):
                            li_text = li.get_text(strip=True)

                            # Check if this contains a model ID
                            model_match = re.search(
                                r"([\w-]+@\d+|imagegeneration@\d+)", li_text
                            )
                            if model_match:
                                model_id = model_match.group(1)

                                # Clean model name from the text
                                model_name = li_text.split(":")[0].strip()
                                if "models" in model_name:
                                    model_name = model_name.replace(
                                        "models", ""
                                    ).strip()

                                item = DeprecationItem(
                                    provider=self.provider_name,
                                    model_id=model_id,
                                    model_name=f"Imagen {model_id}"
                                    if "imagen" in model_id
                                    else model_name,
                                    announcement_date=deprecation_date,
                                    shutdown_date=shutdown_date,
                                    replacement_models=["Imagen 3"]
                                    if "imagen" in li_text.lower()
                                    else None,
                                    deprecation_context=" ".join(context_parts),
                                    url=f"{self.url}#{section_header.get('id', '')}",
                                )
                                items.append(item)
                            else:
                                # Non-model features like "Image captioning"
                                feature_name = li_text.strip()
                                if feature_name and any(
                                    keyword in feature_name.lower()
                                    for keyword in ["caption", "question", "vqa"]
                                ):
                                    item = DeprecationItem(
                                        provider=self.provider_name,
                                        model_id=feature_name.lower().replace(" ", "-"),
                                        model_name=feature_name,
                                        announcement_date=deprecation_date,
                                        shutdown_date=shutdown_date,
                                        replacement_models=None,
                                        deprecation_context=" ".join(context_parts),
                                        url=f"{self.url}#{section_header.get('id', '')}",
                                    )
                                    items.append(item)

                next_elem = next_elem.next_sibling

            # If we found dates but no specific models, create entry for the section
            if (deprecation_date or shutdown_date) and not any(
                item
                for item in items
                if item.deprecation_context == " ".join(context_parts)
            ):
                # Clean section title
                model_name = section_title
                if "deprecation" in model_name.lower():
                    model_name = (
                        model_name.replace("deprecation", "")
                        .replace("deprecations", "")
                        .strip()
                    )

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

        # Also check for tables (in case format changes)
        for table in content.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            # Parse headers
            headers = [
                th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])
            ]

            # Find column indices
            feature_idx = None
            deprecated_idx = None
            shutdown_idx = None
            details_idx = None

            for i, header in enumerate(headers):
                if "feature" in header or "model" in header or "api" in header:
                    feature_idx = i
                elif "deprecat" in header and "date" in header:
                    deprecated_idx = i
                elif "shutdown" in header or "removal" in header or "end" in header:
                    shutdown_idx = i
                elif "detail" in header or "note" in header or "description" in header:
                    details_idx = i

            # Default to positional if headers unclear
            if feature_idx is None:
                feature_idx = 0
            if deprecated_idx is None and len(headers) > 1:
                deprecated_idx = 1
            if shutdown_idx is None and len(headers) > 2:
                shutdown_idx = 2

            # Extract each row
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]

                if len(cells) <= feature_idx:
                    continue

                feature = cells[feature_idx]
                if not feature or feature.lower() in ["feature", "model", "api"]:
                    continue

                # Parse dates
                deprecated_date = ""
                if deprecated_idx is not None and deprecated_idx < len(cells):
                    deprecated_date = self.parse_date(cells[deprecated_idx])

                shutdown_date = ""
                if shutdown_idx is not None and shutdown_idx < len(cells):
                    shutdown_date = self.parse_date(cells[shutdown_idx])

                # Get details/context
                details = ""
                if details_idx is not None and details_idx < len(cells):
                    details = cells[details_idx]

                # Extract replacement from details if present
                replacement_str = None
                if details:
                    repl_match = re.search(
                        r"(?:migrate to|use|replacement:?)\s*([A-Za-z0-9\-\s]+)",
                        details,
                        re.IGNORECASE,
                    )
                    if repl_match:
                        replacement_str = repl_match.group(1).strip()

                replacement_models = (
                    self.parse_replacements(replacement_str)
                    if replacement_str
                    else None
                )

                # Handle special case: Imagen versions
                if "imagen" in feature.lower():
                    # Imagen might list multiple models in one row
                    model_pattern = re.compile(r"imagegeneration@\d+")
                    models = model_pattern.findall(details + " " + feature)

                    if models:
                        # Create separate item for each model
                        for model in models:
                            item = DeprecationItem(
                                provider=self.provider_name,
                                model_id=model,
                                model_name=f"Imagen {model}",
                                announcement_date=deprecated_date,
                                shutdown_date=shutdown_date,
                                replacement_models=["Imagen 3"]
                                if "imagen 3" in details.lower()
                                else replacement_models,
                                deprecation_context=details or f"{feature} deprecation",
                                url=self.url,
                            )
                            items.append(item)
                    else:
                        # Generic Imagen item
                        item = DeprecationItem(
                            provider=self.provider_name,
                            model_id=feature,
                            model_name=feature,
                            announcement_date=deprecated_date,
                            shutdown_date=shutdown_date,
                            replacement_models=replacement_models,
                            deprecation_context=details or f"{feature} deprecation",
                            url=self.url,
                        )
                        items.append(item)
                else:
                    # Regular deprecation item
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=feature,
                        model_name=feature,
                        announcement_date=deprecated_date,
                        shutdown_date=shutdown_date,
                        replacement_models=replacement_models,
                        deprecation_context=details or f"{feature} will be shut down",
                        url=self.url,
                    )
                    items.append(item)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Google uses tables, so no unstructured extraction needed."""
        return []
