"""LLM-powered analysis to extract structured deprecation data."""

import os
from datetime import datetime
from typing import Optional

import instructor
from anthropic import Anthropic
from pydantic import BaseModel, Field


class DeprecationAnalysis(BaseModel):
    """Structured output from LLM analysis of a deprecation notice."""

    model_name: str = Field(
        description="The exact name/version of the deprecated model"
    )
    summary: str = Field(
        description="A clear, concise summary of the deprecation (max 300 chars)"
    )
    shutdown_date: Optional[str] = Field(
        default=None,
        description="The shutdown/deprecation date in ISO format (YYYY-MM-DD) if mentioned",
    )
    suggested_replacement: Optional[str] = Field(
        default=None, description="The suggested replacement model if mentioned"
    )
    deprecation_reason: Optional[str] = Field(
        default=None,
        description="The reason for deprecation if mentioned (e.g., 'superseded by newer model', 'low usage')",
    )


class LLMAnalyzer:
    """Analyzes deprecation content using Anthropic's Claude API with structured outputs."""

    def __init__(self, model_name: str = "claude-3-5-haiku-latest"):
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get(
            "ANTHROPIC_API_TOKEN"
        )
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY or ANTHROPIC_API_TOKEN environment variable required"
            )
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or None

        # Patch Anthropic client with instructor for structured outputs
        self.client = instructor.from_anthropic(
            client=Anthropic(api_key=api_key, base_url=base_url),
            mode=instructor.Mode.ANTHROPIC_TOOLS,
        )
        self.model_name = model_name

    def analyze_item(self, item: dict, existing_item: dict = None) -> dict:
        """
        Analyze a single deprecation item and extract structured data.

        Args:
            item: Dict with provider, title, content, url fields
            existing_item: Optional existing item to preserve first_observed date

        Returns:
            Enhanced item with extracted structured data
        """
        # Prepare the prompt with the deprecation information
        prompt = f"""
Analyze this AI model deprecation notice and extract structured information:

Provider: {item.get("provider", "Unknown")}
Title: {item.get("title", "")}
Content: {item.get("content", "")[:1000]}  # Limit content length

Extract:
1. The exact model name/version being deprecated
2. A clear, concise summary (under 300 chars) for RSS readers
3. The shutdown/deprecation date if mentioned (format as YYYY-MM-DD)
4. Any suggested replacement model
5. The reason for deprecation if mentioned

Be precise and factual. Only include information explicitly stated in the content.
"""

        try:
            # Use instructor to get structured output
            analysis = self.client.messages.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_model=DeprecationAnalysis,
                max_tokens=500,
            )

            # Start with original item
            enhanced = item.copy()

            # Add structured fields from analysis
            enhanced["model_name"] = analysis.model_name
            enhanced["summary"] = analysis.summary

            if analysis.shutdown_date:
                enhanced["shutdown_date"] = analysis.shutdown_date

            if analysis.suggested_replacement:
                enhanced["suggested_replacement"] = analysis.suggested_replacement

            if analysis.deprecation_reason:
                enhanced["deprecation_reason"] = analysis.deprecation_reason

            # Add tracking dates
            today = datetime.utcnow().strftime("%Y-%m-%d")
            if existing_item and "first_observed" in existing_item:
                # Preserve first_observed from existing item
                enhanced["first_observed"] = existing_item["first_observed"]
            else:
                # New item, set first_observed to today
                enhanced["first_observed"] = today

            enhanced["last_observed"] = today

            # Keep original content as raw_content for reference
            enhanced["raw_content"] = item.get("content", "")

            # Replace content with the summary for cleaner RSS
            enhanced["content"] = analysis.summary

            return enhanced

        except Exception as e:
            print(f"LLM analysis failed for item: {e}")
            # Return original item with observation dates if analysis fails
            item["first_observed"] = datetime.utcnow().strftime("%Y-%m-%d")
            item["last_observed"] = datetime.utcnow().strftime("%Y-%m-%d")
            return item

    def analyze_batch(
        self, items: list[dict], existing_data: list[dict] = None
    ) -> list[dict]:
        """
        Analyze multiple deprecation items.

        Args:
            items: List of deprecation items to analyze
            existing_data: Optional list of existing items to preserve first_observed dates

        Returns:
            List of enhanced items with structured data
        """
        if not items:
            return []

        # Create lookup for existing items by hash if provided
        existing_by_hash = {}
        if existing_data:
            from .main import hash_item

            existing_by_hash = {hash_item(item): item for item in existing_data}

        enhanced_items = []
        for i, item in enumerate(items, 1):
            print(f"  Analyzing item {i}/{len(items)}...")

            # Find existing item if available
            item_hash = item.get("_hash")
            existing_item = existing_by_hash.get(item_hash) if item_hash else None

            enhanced = self.analyze_item(item, existing_item)
            enhanced_items.append(enhanced)

        return enhanced_items
