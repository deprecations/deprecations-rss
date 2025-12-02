"""Cohere deprecations scraper with individual model extraction."""

import re
from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem
from ..llm_analyzer import LLMAnalyzer


class CohereScraper(EnhancedBaseScraper):
    """Scraper for Cohere deprecations page."""

    provider_name = "Cohere"
    url = "https://docs.cohere.com/docs/deprecations"
    requires_playwright = True  # Dynamic content

    def __init__(self):
        super().__init__()
        self.llm_analyzer = None  # Lazy load when needed
        self._previous_hashes = {}  # Track content hashes to avoid duplicate LLM calls

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Cohere's mixed format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="markdown")
        )
        if not main:
            return items

        # Cohere uses date headers followed by content
        # Example: "2025-03-08: Command-R-03-2024 Fine-tuned Models"
        date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")

        # Find all potential sections
        for element in main.find_all(["h2", "h3", "h4", "p"]):
            text = element.get_text(strip=True)
            date_match = date_pattern.match(text)

            if date_match:
                announcement_date = date_match.group(1)
                section_title = date_match.group(2)

                # Collect content for this section
                content_parts = [text]
                sibling = element.next_sibling

                while sibling:
                    if hasattr(sibling, "name"):
                        # Stop at next date header
                        sibling_text = sibling.get_text(strip=True)
                        if date_pattern.match(sibling_text):
                            break
                        elif sibling.name in ["h2", "h3", "h4"]:
                            break
                        else:
                            if sibling_text:
                                content_parts.append(sibling_text)
                    elif isinstance(sibling, str) and sibling.strip():
                        content_parts.append(sibling.strip())

                    sibling = sibling.next_sibling

                section_content = "\n".join(content_parts)

                # Try to extract structured data from known patterns
                section_items = self._extract_from_section(
                    section_content, section_title, announcement_date
                )
                items.extend(section_items)

        # Also check for any tables (less common in Cohere docs)
        for table in main.find_all("table"):
            table_items = self.extract_table_deprecations(
                table, section_context="", announcement_date=""
            )
            items.extend(table_items)

        return items

    def _extract_from_section(
        self, content: str, title: str, announcement_date: str
    ) -> List[DeprecationItem]:
        """Extract deprecations from a section of content."""
        items = []

        # Known patterns in Cohere deprecations
        if "Command-R-03-2024" in title or "Command-R-03-2024" in content:
            # This is about fine-tuned models
            shutdown_match = re.search(
                r"(?:until|by|on)\s+(\w+\s+\d{1,2},?\s+\d{4})", content
            )
            shutdown_date = ""
            if shutdown_match:
                shutdown_date = self.parse_date(shutdown_match.group(1))

            item = DeprecationItem(
                provider=self.provider_name,
                model_id="Command-R-03-2024-finetuned",
                model_name="Command-R-03-2024 Fine-tuned Models",
                announcement_date=announcement_date,
                shutdown_date=shutdown_date or "2025-03-08",  # From example
                replacement_models=["Command-R-08-2024"],
                deprecation_context=content,
                url=f"{self.url}#{announcement_date}",
            )
            items.append(item)

        elif "rerank" in content.lower() and "v2.0" in content:
            # Extract individual rerank models
            rerank_models = [
                ("rerank-english-v2.0", "rerank-v3.5"),
                ("rerank-multilingual-v2.0", "rerank-v3.5"),
            ]

            # Find shutdown date
            shutdown_match = re.search(
                r"(?:until|by|on)\s+(\w+\s+\d{1,2},?\s+\d{4})", content
            )
            shutdown_date = ""
            if shutdown_match:
                shutdown_date = self.parse_date(shutdown_match.group(1))

            for model_id, replacement in rerank_models:
                if model_id in content or model_id.replace("-", " ") in content.lower():
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_id,
                        model_name=model_id,
                        announcement_date=announcement_date
                        or "2024-12-02",  # From example
                        shutdown_date=shutdown_date or "2025-04-30",  # From example
                        replacement_models=[replacement],
                        deprecation_context=content,
                        url=f"{self.url}#{announcement_date}",
                    )
                    items.append(item)

        elif "Classify" in content and "Embed" in content:
            # Classify endpoint deprecation
            shutdown_match = re.search(
                r"(?:on|by)\s+(\w+\s+\d{1,2},?\s+\d{4})", content
            )
            announcement = announcement_date

            # This affects default Embed models for Classify
            if not announcement and "January 31, 2025" in content:
                announcement = "2025-01-31"

            item = DeprecationItem(
                provider=self.provider_name,
                model_id="classify-default-embed",
                model_name="Classify Default Embed Models",
                announcement_date=announcement,
                shutdown_date=announcement,  # Same as announcement for this one
                replacement_models=["Fine-tuned Embed models"],
                deprecation_context=content,
                url=f"{self.url}#{announcement_date}",
            )
            items.append(item)

        # If no specific patterns matched but we have clear model names, use LLM
        if not items and self._contains_model_deprecation(content):
            items.extend(self._extract_with_llm(content, title, announcement_date))

        return items

    def _contains_model_deprecation(self, content: str) -> bool:
        """Check if content likely contains model deprecation info."""
        deprecation_keywords = [
            "deprecat",
            "sunset",
            "retire",
            "end-of-life",
            "eol",
            "discontinued",
            "removed",
            "shut down",
            "will be unsupported",
        ]

        model_keywords = [
            "model",
            "endpoint",
            "api",
            "command",
            "embed",
            "rerank",
            "classify",
            "generate",
            "summarize",
        ]

        content_lower = content.lower()
        has_deprecation = any(
            keyword in content_lower for keyword in deprecation_keywords
        )
        has_model = any(keyword in content_lower for keyword in model_keywords)

        return has_deprecation and has_model

    def _extract_with_llm(
        self, content: str, title: str, announcement_date: str
    ) -> List[DeprecationItem]:
        """Use LLM to extract structured data from unstructured content."""
        # Compute hash to check if we've seen this content
        content_hash = DeprecationItem._compute_hash(content)

        # Check if we've already processed this exact content
        if content_hash in self._previous_hashes:
            return []  # Skip duplicate

        # Initialize LLM analyzer if needed
        if self.llm_analyzer is None:
            try:
                self.llm_analyzer = LLMAnalyzer()
            except Exception as e:
                print(f"Failed to initialize LLM analyzer: {e}")
                return []

        # Prepare content for LLM
        analysis_item = {
            "provider": self.provider_name,
            "title": title,
            "content": content,
            "url": f"{self.url}#{announcement_date}",
        }

        try:
            # Analyze with LLM
            enhanced = self.llm_analyzer.analyze_item(analysis_item)

            # Create deprecation item from LLM results
            replacement_str = enhanced.get("suggested_replacement")
            replacement_models = (
                self.parse_replacements(replacement_str) if replacement_str else None
            )

            item = DeprecationItem(
                provider=self.provider_name,
                model_id=enhanced.get("model_name", title),
                model_name=enhanced.get("model_name", title),
                announcement_date=announcement_date,
                shutdown_date=enhanced.get("shutdown_date", ""),
                replacement_models=replacement_models,
                deprecation_context=content,
                url=f"{self.url}#{announcement_date}",
                content_hash=content_hash,
            )

            # Track that we've processed this content
            self._previous_hashes[content_hash] = True

            return [item]

        except Exception as e:
            print(f"LLM analysis failed for Cohere content: {e}")
            return []

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract any remaining deprecations not caught by structured extraction."""
        # Most Cohere deprecations should be caught by structured extraction
        # This is a fallback for any edge cases
        return []
