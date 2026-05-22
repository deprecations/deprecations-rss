"""Tests for the Groq deprecations scraper."""

from src.scrapers.groq_scraper import GroqScraper


GROQ_DEPRECATIONS_MARKDOWN = """
---
title: Model Deprecation - GroqDocs
---

## [Model Deprecation](#model-deprecation)

Deprecation refers to the process of retiring older models or endpoints.

### [Production vs. Preview Models](#production-vs-preview-models)

Preview models may be discontinued at short notice with limited advance warning.

### [April 15, 2026: moonshotai/kimi-k2-instruct-0905](#april-15-2026-moonshotaikimik2instruct0905)

In line with our commitment to bringing you cutting-edge models, on March 23, 2026, we emailed users to announce the deprecation of `moonshotai/kimi-k2-instruct-0905` in favor of `openai/gpt-oss-120b`.

| Deprecated Model                 | Shutdown Date | Recommended Replacement Model ID |
| -------------------------------- | ------------- | -------------------------------- |
| moonshotai/kimi-k2-instruct-0905 | 04/15/26      | openai/gpt-oss-120b              |

### [December 31, 2025: playai-tts and playai-tts-arabic](#december-31-2025-playaitts-and-playaittsarabic)

In line with our commitment to bringing you cutting-edge models, on December 23, 2025, we emailed users to announce the deprecation of `playai-tts` and `playai-tts-arabic` in favor of the newer Orpheus text-to-speech models from Canopy Labs.

| Deprecated Model  | Shutdown Date | Recommended Replacement Model ID |
| ----------------- | ------------- | -------------------------------- |
| playai-tts        | 12/31/25      | canopylabs/orpheus-v1-english    |
| playai-tts-arabic | 12/31/25      | canopylabs/orpheus-arabic-saudi  |

### [October 2, 2025: deepseek-r1-distill-llama-70b](#october-2-2025-deepseekr1distillllama70b)

In line with our commitment to bringing you cutting-edge models, on September 2, 2025, we emailed users to announce the deprecation of `deepseek-r1-distill-llama-70b` in favor of `llama-3.3-70b-versatile` or `openai/gpt-oss-120b`.

| Deprecated Model              | Shutdown Date | Recommended Replacement Model ID               |
| ----------------------------- | ------------- | ---------------------------------------------- |
| deepseek-r1-distill-llama-70b | 10/02/25      | llama-3.3-70b-versatile or openai/gpt-oss-120b |

### [March 20, 2025: Mixtral 8x7B](#march-20-2025-mixtral-8x7b)

On March 5, 2025, we emailed all users of the `mixtral-8x7b-32768` model that we would be deprecating this model ID in favor of newer, more performant models.

| Model ID           | Shutdown Date | Recommended Replacement Model ID         |
| ------------------ | ------------- | ---------------------------------------- |
| mixtral-8x7b-32768 | 03/20/25      | mistral-saba-24b llama-3.3-70b-versatile |
"""


def test_groq_extracts_markdown_deprecation_history():
    """Groq markdown history tables should produce model-level items."""
    items = GroqScraper().extract_structured_deprecations(GROQ_DEPRECATIONS_MARKDOWN)

    assert [item.model_id for item in items] == [
        "moonshotai/kimi-k2-instruct-0905",
        "playai-tts",
        "playai-tts-arabic",
        "deepseek-r1-distill-llama-70b",
        "mixtral-8x7b-32768",
    ]
    assert all(item.provider == "Groq" for item in items)
    assert all(item.shutdown_date for item in items)


def test_groq_parses_dates_replacements_and_urls():
    """Groq-specific dates, replacements, and anchors should be normalized."""
    items = GroqScraper().extract_structured_deprecations(GROQ_DEPRECATIONS_MARKDOWN)
    by_model = {item.model_id: item for item in items}

    kimi = by_model["moonshotai/kimi-k2-instruct-0905"]
    assert kimi.announcement_date == "2026-03-23"
    assert kimi.deprecation_date == "2026-03-23"
    assert kimi.shutdown_date == "2026-04-15"
    assert kimi.replacement_models == ["openai/gpt-oss-120b"]
    assert kimi.url == (
        "https://console.groq.com/docs/deprecations"
        "#april-15-2026-moonshotaikimik2instruct0905"
    )

    deepseek = by_model["deepseek-r1-distill-llama-70b"]
    assert deepseek.replacement_models == [
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
    ]

    mixtral = by_model["mixtral-8x7b-32768"]
    assert mixtral.replacement_models == [
        "mistral-saba-24b",
        "llama-3.3-70b-versatile",
    ]


def test_groq_ignores_lifecycle_guidance_without_tables():
    """Generic deprecation policy text should not create false positives."""
    markdown = """
# Model Deprecation

### [Production vs. Preview Models](#production-vs-preview-models)

Preview models may be discontinued at short notice with limited advance warning.
"""

    assert GroqScraper().extract_structured_deprecations(markdown) == []


def test_groq_scrape_uses_markdown_source():
    """The provider registry should scrape Groq's deterministic markdown endpoint."""
    scraper = GroqScraper()
    assert scraper.get_source_url() == "https://console.groq.com/docs/deprecations.md"
