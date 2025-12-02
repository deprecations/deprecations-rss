"""OpenAI deprecations scraper with individual model extraction."""

import re
from typing import List, Any
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class OpenAIScraper(EnhancedBaseScraper):
    """Scraper for OpenAI deprecations page."""

    provider_name = "OpenAI"
    url = "https://platform.openai.com/docs/deprecations"
    requires_playwright = True  # OpenAI uses Cloudflare protection

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from OpenAI's structured format."""
        items = []

        # Use Playwright JavaScript evaluation for dynamic content
        # This is a fallback - we'll actually parse the HTML we already have
        soup = BeautifulSoup(html, "html.parser")

        # Find the main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
        )

        if not main_content:
            return items

        # OpenAI uses date headers like "2025-04-28: o1-preview and o1-mini"
        # wrapped in div.anchor-heading-wrapper, followed by description and table

        # Find all heading wrapper divs
        date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")

        # Look for both wrapped and unwrapped headings for backward compatibility
        heading_containers = []

        # First, collect wrapped headings
        for wrapper in main_content.find_all("div", class_="anchor-heading-wrapper"):
            heading = wrapper.find(["h2", "h3", "h4"])
            if heading:
                heading_containers.append((wrapper, heading))

        # Then, collect unwrapped headings (that aren't already in wrappers)
        for heading in main_content.find_all(["h2", "h3", "h4"]):
            parent = heading.parent
            if not (
                parent.name == "div"
                and "anchor-heading-wrapper" in parent.get("class", [])
            ):
                heading_containers.append((heading, heading))

        for container, element in heading_containers:
            heading_text = element.get_text(strip=True)
            date_match = date_pattern.match(heading_text)

            if date_match:
                announcement_date = date_match.group(1)
                section_title = date_match.group(2)

                # Build the URL with anchor
                anchor_id = element.get("id") or announcement_date
                section_url = f"{self.url}#{anchor_id}"

                # Collect the context (text between heading and table)
                # Look for siblings of the container (wrapper or heading)
                context_parts = []
                sibling = container.next_sibling
                table = None

                while sibling:
                    if hasattr(sibling, "name"):
                        if sibling.name == "table":
                            table = sibling
                            break
                        elif sibling.name in ["h2", "h3", "h4"]:
                            # Next section, stop
                            break
                        elif (
                            sibling.name == "div"
                            and "anchor-heading-wrapper" in sibling.get("class", [])
                        ):
                            # Next wrapped section, stop
                            break
                        else:
                            text = sibling.get_text(strip=True)
                            if text:
                                context_parts.append(text)
                    elif isinstance(sibling, str) and sibling.strip():
                        context_parts.append(sibling.strip())

                    sibling = sibling.next_sibling

                section_context = " ".join(context_parts)

                # If we found a table, extract each row as a separate deprecation
                if table:
                    table_items = self._extract_from_table(
                        table, section_context, announcement_date, section_url
                    )
                    items.extend(table_items)
                else:
                    # No table, try to extract from text
                    text_items = self._extract_from_text(
                        section_context, section_title, announcement_date, section_url
                    )
                    items.extend(text_items)

        # Deduplicate by model_id, keeping the most recent announcement
        seen = {}
        for item in items:
            if item.model_id not in seen:
                seen[item.model_id] = item
            else:
                # Keep the item with the most recent announcement date
                existing = seen[item.model_id]
                if item.announcement_date > existing.announcement_date:
                    seen[item.model_id] = item

        return list(seen.values())

    def _extract_from_table(
        self, table: Any, context: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract individual model deprecations from a table."""
        items = []
        rows = table.find_all("tr")

        if len(rows) <= 1:
            return items

        # Parse headers
        headers = []
        for th in rows[0].find_all(["th", "td"]):
            headers.append(th.get_text(strip=True).upper())

        # Only process tables that have "MODEL" in at least one header
        # Skip tables that only have "SYSTEM" (these contain endpoints, not models)
        has_model_header = any("MODEL" in header for header in headers)
        if not has_model_header:
            return items

        # Find column indices
        shutdown_idx = None
        model_idx = None
        replacement_idx = None

        for i, header in enumerate(headers):
            if "SHUTDOWN" in header or "EOL" in header:
                shutdown_idx = i
            elif "DEPRECATED MODEL" in header and "PRICE" not in header:
                # Prioritize "DEPRECATED MODEL" over "DEPRECATED MODEL PRICE"
                model_idx = i
            elif ("MODEL" in header or "SYSTEM" in header) and "PRICE" not in header:
                # Only match MODEL if it's not a price column
                if model_idx is None:
                    model_idx = i
            elif "REPLACEMENT" in header or "RECOMMENDED" in header:
                replacement_idx = i

        # If we can't identify columns, use positional defaults
        if shutdown_idx is None and model_idx is None:
            # Common pattern: shutdown date, model, replacement
            if len(headers) >= 3:
                shutdown_idx = 0
                model_idx = 1
                replacement_idx = 2

        if model_idx is None:
            return items

        # Extract each row as a separate deprecation
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) <= model_idx:
                continue

            # Try to extract just the first code block if present
            code_tag = cells[model_idx].find("code")
            if code_tag:
                model_cell_text = code_tag.get_text(strip=True)
            else:
                model_cell_text = cells[model_idx].get_text(strip=True)

            # Clean up text - remove parenthetical notes
            if "(" in model_cell_text:
                model_cell_text = model_cell_text.split("(")[0].strip()

            # Skip empty or header-like rows
            if not model_cell_text or model_cell_text.upper() in [
                "MODEL",
                "SYSTEM",
                "NAME",
            ]:
                continue

            # Skip endpoints and systems (not actual models)
            if (
                model_cell_text.startswith("/")  # Endpoints like /v1/answers
                or " API" in model_cell_text  # Systems like "Assistants API"
                or " endpoint"
                in model_cell_text.lower()  # Systems like "Fine-tunes endpoint"
                or model_cell_text.startswith(
                    "OpenAI-Beta:"
                )  # Headers like OpenAI-Beta: assistants=v1
                or "fine-tuning training"
                in model_cell_text.lower()  # Features like "New fine-tuning training on..."
            ):
                continue

            # Split if multiple models in one cell (e.g., "o1-preview and o1-mini")
            model_names = []
            if " and " in model_cell_text:
                model_names = [m.strip() for m in model_cell_text.split(" and ")]
            else:
                model_names = [model_cell_text]

            # Extract shutdown date
            shutdown_date = announcement_date  # default
            if shutdown_idx is not None and shutdown_idx < len(cells):
                date_text = cells[shutdown_idx].get_text(strip=True)
                parsed_date = self.parse_date(date_text)
                if parsed_date:
                    shutdown_date = parsed_date

            # Extract replacement
            replacement_models = None
            if replacement_idx is not None and replacement_idx < len(cells):
                repl_text = cells[replacement_idx].get_text(strip=True)
                if repl_text and repl_text not in ["—", "-", "N/A"]:
                    replacement_models = self.parse_replacements(repl_text)

            # Create deprecation item for each model
            for model_name in model_names:
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_name,
                    model_name=model_name,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_models=replacement_models,
                    deprecation_context=context,
                    url=url,
                )

                items.append(item)

        return items

    def _extract_from_text(
        self, text: str, title: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract deprecations from unstructured text when no table is present."""
        items = []

        # Pattern to find model names and dates in text
        # Example: "gpt-4-32k will be deprecated on June 6, 2025"
        model_pattern = re.compile(
            r"([\w\-\.]+(?:-\d+k?|-preview|-turbo|-vision|-\d{4}))\s+(?:will be|is|are)\s+(?:deprecated|retired|shut down|removed)",
            re.IGNORECASE,
        )

        # Find shutdown dates
        shutdown_pattern = re.compile(
            r"(?:on|by|before)\s+(\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        )

        # Extract models mentioned in the text
        models_found = model_pattern.findall(text)
        shutdown_match = shutdown_pattern.search(text)

        shutdown_date = announcement_date
        if shutdown_match:
            parsed = self.parse_date(shutdown_match.group(1))
            if parsed:
                shutdown_date = parsed

        # If models found in text, create items for each
        for model in models_found:
            item = DeprecationItem(
                provider=self.provider_name,
                model_id=model,
                model_name=model,
                announcement_date=announcement_date,
                shutdown_date=shutdown_date,
                replacement_models=None,  # Would need LLM to extract this reliably
                deprecation_context=text,
                url=url,
            )
            items.append(item)

        # If no models found but we have a title, check if title contains multiple models
        if not items and title:
            # Skip non-model titles (endpoints, systems, features)
            if (
                title.startswith("/")  # Endpoints like /v1/answers
                or " API" in title  # Systems like "Assistants API"
                or " endpoint" in title.lower()  # Systems like "Fine-tunes endpoint"
                or title.startswith("OpenAI-Beta:")  # Headers
                or "fine-tuning training" in title.lower()  # Features
            ):
                return items

            # Split title if it contains "and" to handle cases like "o1-preview and o1-mini"
            if " and " in title:
                models = [m.strip() for m in title.split(" and ")]
                for model in models:
                    # Skip generic/ambiguous model names
                    if model.upper() in ["GPT", "EMBEDDINGS", "MODELS"]:
                        continue
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model,
                        model_name=model,
                        announcement_date=announcement_date,
                        shutdown_date=shutdown_date,
                        replacement_models=None,
                        deprecation_context=text,
                        url=url,
                    )
                    items.append(item)
            else:
                # Skip generic/ambiguous single model names
                if title.upper() in ["GPT", "EMBEDDINGS", "MODELS"]:
                    return items

                # Single model in title
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=title,
                    model_name=title,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_models=None,
                    deprecation_context=text,
                    url=url,
                )
                items.append(item)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """OpenAI page is well-structured, so we don't need this."""
        return []
