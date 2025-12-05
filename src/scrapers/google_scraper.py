"""Google AI/Gemini deprecations scraper with individual model extraction."""

import re
from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class GoogleScraper(EnhancedBaseScraper):
    """Scraper for Google AI/Gemini deprecations page."""

    provider_name = "Google"
    url = "https://ai.google.dev/gemini-api/docs/changelog"
    requires_playwright = False  # Static content, httpx is fine

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Google AI changelog format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return items

        # Google AI uses date-based sections with h2 headers
        sections = content.find_all(["h2", "h3"])

        for section_header in sections:
            section_title = section_header.get_text(strip=True)

            # Skip non-date sections
            date_match = re.search(r"(\w+ \d+, \d{4})", section_title)
            if not date_match:
                continue

            section_date = self.parse_date(date_match.group(1))

            # Look for deprecation info after the header
            next_elem = section_header.next_sibling

            while next_elem:
                if hasattr(next_elem, "name"):
                    if next_elem.name in ["h2", "h3"]:
                        # Next section
                        break

                    text = next_elem.get_text(strip=True)

                    # Look for deprecation patterns
                    if any(
                        keyword in text.lower()
                        for keyword in [
                            "deprecated",
                            "deprecation",
                            "no longer supported",
                            "removed",
                            "will be deprecated",
                            "retirement",
                        ]
                    ):
                        # Find all <code> tags that contain model IDs
                        code_tags = next_elem.find_all("code")

                        if code_tags:
                            for code_tag in code_tags:
                                model_id = code_tag.get_text(strip=True).lower()

                                # Verify it's a valid model ID pattern
                                if not re.match(
                                    r"^gemini-[a-zA-Z0-9\-\.]+$", model_id
                                ) and not re.match(
                                    r"^(veo|imagen)-[a-zA-Z0-9\-\.]+$", model_id
                                ):
                                    continue

                                # Get context from the parent list item or paragraph
                                context_elem = code_tag.find_parent(["li", "p"])
                                if context_elem:
                                    # Use the immediate parent's text as primary context
                                    deprecation_context = context_elem.get_text(
                                        " ", strip=True
                                    )

                                    # If context is too short, try grandparent
                                    if len(deprecation_context) < 30:
                                        grandparent = context_elem.find_parent(
                                            ["li", "p"]
                                        )
                                        if grandparent:
                                            deprecation_context = grandparent.get_text(
                                                " ", strip=True
                                            )
                                else:
                                    deprecation_context = text

                                # Look for shutdown date in context
                                future_date_match = re.search(
                                    r"(\w+ \d+(?:st|nd|rd|th)?)[:\s]",
                                    deprecation_context,
                                )
                                deprecation_date = ""
                                if future_date_match:
                                    date_str = future_date_match.group(1).rstrip(
                                        "stndrdth"
                                    )
                                    # Try to parse with current year
                                    try:
                                        parsed_date = self.parse_date(
                                            f"{date_str}, {section_date[:4]}"
                                        )
                                        if parsed_date and parsed_date >= section_date:
                                            deprecation_date = parsed_date
                                    except (ValueError, AttributeError):
                                        pass

                                if not deprecation_date:
                                    deprecation_date = section_date

                                # Clean up model name
                                model_name = model_id.replace("-", " ").title()

                                # Look for replacement models in context
                                replacement_str = None
                                repl_patterns = [
                                    r"redirect(?:ing)?\s+to\s+(gemini-[a-zA-Z0-9\-\.]+)",
                                    r"use\s+([a-z]+\s+\d+)",
                                    r"use\s+(gemini-[a-zA-Z0-9\-\.]+)",
                                    r"replaced\s+(?:by|with)\s+(gemini-[a-zA-Z0-9\-\.]+)",
                                ]
                                for pattern in repl_patterns:
                                    repl_match = re.search(
                                        pattern, deprecation_context.lower()
                                    )
                                    if repl_match:
                                        replacement_str = repl_match.group(1)
                                        break

                                replacement_models = (
                                    self.parse_replacements(replacement_str)
                                    if replacement_str
                                    else None
                                )

                                item = DeprecationItem(
                                    provider=self.provider_name,
                                    model_id=model_id,
                                    model_name=model_name,
                                    announcement_date=section_date,
                                    shutdown_date=deprecation_date
                                    if deprecation_date != section_date
                                    else "",
                                    replacement_models=replacement_models,
                                    deprecation_context=deprecation_context,
                                    url=f"{self.url}#{section_date.replace('-', '')}",
                                )
                                items.append(item)
                        else:
                            # Fallback: extract from text if no code tags
                            if "gemini" in text.lower():
                                general_model_patterns = [
                                    r"gemini\s+1\.0\s+pro\s+vision",
                                    r"gemini\s+1\.0\s+pro",
                                    r"gemini\s+1\.5\s+(?:pro|flash)",
                                ]

                                for pattern in general_model_patterns:
                                    if re.search(pattern, text.lower()):
                                        model_name = re.search(
                                            pattern, text.lower()
                                        ).group(0)
                                        model_id = model_name.lower().replace(" ", "-")

                                        future_date_match = re.search(
                                            r"(\w+ \d+, \d{4})", text
                                        )
                                        deprecation_date = ""
                                        if future_date_match:
                                            parsed_date = self.parse_date(
                                                future_date_match.group(1)
                                            )
                                            if (
                                                parsed_date
                                                and parsed_date > section_date
                                            ):
                                                deprecation_date = parsed_date

                                        if not deprecation_date:
                                            deprecation_date = section_date

                                        item = DeprecationItem(
                                            provider=self.provider_name,
                                            model_id=model_id,
                                            model_name=model_name.title(),
                                            announcement_date=section_date,
                                            shutdown_date=deprecation_date
                                            if deprecation_date != section_date
                                            else "",
                                            replacement_models=None,
                                            deprecation_context=text,
                                            url=f"{self.url}#{section_date.replace('-', '')}",
                                        )
                                        items.append(item)
                                        break

                next_elem = next_elem.next_sibling

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Google AI uses structured changelog, so no unstructured extraction needed."""
        return []
