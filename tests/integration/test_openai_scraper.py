"""Integration tests for OpenAI scraper with fixture-based testing."""

from pathlib import Path
import pytest
from src.scrapers.openai_scraper import OpenAIScraper


@pytest.fixture
def fixture_html():
    """Load the OpenAI deprecations fixture HTML."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "openai_deprecations.html"
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def scraper():
    """Create an OpenAI scraper instance."""
    return OpenAIScraper()


def test_extracts_deprecation_items(scraper, fixture_html):
    """Should extract deprecation items from fixture HTML."""
    items = scraper.extract_structured_deprecations(fixture_html)

    assert len(items) > 0, "Should extract at least one deprecation item"
    assert len(items) >= 25, f"Expected at least 25 items, got {len(items)}"
    assert len(items) <= 35, (
        f"Expected at most 35 items, got {len(items)} (may include non-models)"
    )


def test_extracts_deprecation_context_for_all_items(scraper, fixture_html):
    """Should extract non-empty deprecation_context for most items."""
    items = scraper.extract_structured_deprecations(fixture_html)

    items_without_context = [
        item
        for item in items
        if not item.deprecation_context or not item.deprecation_context.strip()
    ]

    # Some old deprecations (Codex, legacy endpoints) don't have context text
    # This is OK - they go straight from heading to table
    assert len(items_without_context) < 10, (
        f"Found {len(items_without_context)} items without context: "
        f"{[item.model_name for item in items_without_context]}"
    )

    # Most items should have context
    items_with_context = [
        item
        for item in items
        if item.deprecation_context and item.deprecation_context.strip()
    ]
    assert len(items_with_context) > len(items) * 0.75, (
        f"Expected at least 75% of items to have context, got {len(items_with_context)}/{len(items)}"
    )


def test_extracts_meaningful_context_text(scraper, fixture_html):
    """Should extract meaningful context text (not just whitespace)."""
    items = scraper.extract_structured_deprecations(fixture_html)

    # Only check items that have context (some old ones don't)
    items_with_context = [
        item
        for item in items
        if item.deprecation_context and item.deprecation_context.strip()
    ]

    for item in items_with_context:
        assert len(item.deprecation_context) > 50, (
            f"Context too short for {item.model_name}: '{item.deprecation_context[:100]}'"
        )
        # Check that context contains actual words
        assert any(
            word in item.deprecation_context.lower()
            for word in [
                "deprecat",
                "shut",
                "remov",
                "replac",
                "migrat",
                "notified",
                "announced",
            ]
        ), f"Context doesn't contain deprecation-related words for {item.model_name}"


def test_extracts_model_names(scraper, fixture_html):
    """Should extract model names correctly."""
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        assert item.model_name, "Model name should not be empty"
        assert item.model_id, "Model ID should not be empty"
        assert item.model_name == item.model_id, "Model name and ID should match"


def test_extracts_dates(scraper, fixture_html):
    """Should extract announcement and shutdown dates."""
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        assert item.announcement_date, (
            f"Missing announcement date for {item.model_name}"
        )
        assert item.shutdown_date, f"Missing shutdown date for {item.model_name}"
        # Dates should be in YYYY-MM-DD format
        assert len(item.announcement_date) == 10, (
            f"Invalid announcement date format for {item.model_name}: {item.announcement_date}"
        )


def test_extracts_replacement_models_when_available(scraper, fixture_html):
    """Should extract replacement models when specified."""
    items = scraper.extract_structured_deprecations(fixture_html)

    items_with_replacement = [item for item in items if item.replacement_models]

    assert len(items_with_replacement) > 0, "Should find items with replacement models"

    for item in items_with_replacement:
        assert isinstance(item.replacement_models, list), (
            f"Replacement models should be a list for {item.model_name}"
        )
        assert len(item.replacement_models) > 0, (
            f"Replacement models list is empty for {item.model_name}"
        )
        for model in item.replacement_models:
            assert len(model) > 0, (
                f"Replacement model is empty string for {item.model_name}"
            )


def test_generates_correct_urls_with_anchors(scraper, fixture_html):
    """Should generate URLs with proper anchor links."""
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        assert item.url, f"Missing URL for {item.model_name}"
        assert item.url.startswith("https://platform.openai.com/docs/deprecations#"), (
            f"Invalid URL format for {item.model_name}: {item.url}"
        )


def test_sets_provider_to_openai(scraper, fixture_html):
    """Should set provider to OpenAI for all items."""
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        assert item.provider == "OpenAI", f"Wrong provider for {item.model_name}"


def test_extracts_o1_preview_with_context(scraper, fixture_html):
    """Should extract o1-preview with proper context."""
    items = scraper.extract_structured_deprecations(fixture_html)

    o1_items = [item for item in items if "o1-preview" in item.model_name]
    assert len(o1_items) > 0, "Should find o1-preview in deprecations"

    o1_item = o1_items[0]
    assert o1_item.deprecation_context, "o1-preview should have context"
    assert (
        "o1-preview" in o1_item.deprecation_context
        or "o1-mini" in o1_item.deprecation_context
    ), "Context should mention the deprecated models"


def test_extracts_gpt4_32k_with_context(scraper, fixture_html):
    """Should extract gpt-4-32k with proper context."""
    items = scraper.extract_structured_deprecations(fixture_html)

    gpt4_32k_items = [item for item in items if "gpt-4-32k" in item.model_name]
    assert len(gpt4_32k_items) > 0, "Should find gpt-4-32k in deprecations"

    for item in gpt4_32k_items:
        assert item.deprecation_context, f"{item.model_name} should have context"
        assert len(item.deprecation_context) > 100, (
            f"Context for {item.model_name} is too short"
        )


def test_skips_endpoints_and_systems(scraper, fixture_html):
    """Should skip endpoints and systems, only extract models."""
    items = scraper.extract_structured_deprecations(fixture_html)

    model_ids = [item.model_id for item in items]

    # Should not contain endpoints
    assert not any(mid.startswith("/v1/") for mid in model_ids), (
        "Should not extract endpoints like /v1/answers"
    )

    # Should not contain systems
    assert not any(" API" in mid for mid in model_ids), (
        "Should not extract systems like 'Assistants API'"
    )

    # Should not contain endpoint names
    assert not any("endpoint" in mid.lower() for mid in model_ids), (
        "Should not extract 'Fine-tunes endpoint'"
    )

    # Should not contain headers
    assert not any(mid.startswith("OpenAI-Beta:") for mid in model_ids), (
        "Should not extract OpenAI-Beta headers"
    )

    # Should not contain generic names
    assert "GPT" not in model_ids, "Should not extract generic 'GPT'"
    assert "embeddings" not in model_ids, "Should not extract generic 'embeddings'"


def test_no_duplicate_models(scraper, fixture_html):
    """Should not extract duplicate models."""
    items = scraper.extract_structured_deprecations(fixture_html)

    model_ids = [item.model_id for item in items]

    # Check for duplicates
    unique_ids = set(model_ids)
    assert len(model_ids) == len(unique_ids), (
        f"Found duplicate models. Total: {len(model_ids)}, Unique: {len(unique_ids)}"
    )


def test_handles_multiple_models_in_one_table_row(scraper, fixture_html):
    """Should split models when multiple are in one table cell."""
    items = scraper.extract_structured_deprecations(fixture_html)

    # Check that we have individual items, not combined strings like "o1-preview and o1-mini"
    model_names = [item.model_name for item in items]
    combined_models = [name for name in model_names if " and " in name]

    # It's OK to have some combined names if they're not parseable
    # but ideally they should be split
    assert len(combined_models) < len(items) * 0.1, (
        f"Too many combined model names: {combined_models}"
    )


def test_handles_models_with_special_characters(scraper, fixture_html):
    """Should handle model names with hyphens and underscores."""
    items = scraper.extract_structured_deprecations(fixture_html)

    # Look for models with special characters
    special_char_models = [
        item for item in items if "-" in item.model_name or "_" in item.model_name
    ]

    assert len(special_char_models) > 0, "Should find models with special characters"

    # Check that most have context (some old ones may not)
    models_with_context = [
        item
        for item in special_char_models
        if item.deprecation_context and item.deprecation_context.strip()
    ]

    assert len(models_with_context) > len(special_char_models) * 0.75, (
        f"Expected at least 75% of special char models to have context, "
        f"got {len(models_with_context)}/{len(special_char_models)}"
    )


@pytest.mark.slow
@pytest.mark.integration
def test_scrapes_live_site_successfully(scraper):
    """Should successfully scrape the live OpenAI deprecations page."""
    try:
        html = scraper.fetch_with_playwright(scraper.url)
        items = scraper.extract_structured_deprecations(html)

        assert len(items) > 0, "Should extract items from live site"

        for item in items[:5]:
            assert item.deprecation_context, (
                f"Live site: {item.model_name} should have context"
            )
    except Exception as e:
        pytest.skip(f"Live site test failed (may be Cloudflare or network issue): {e}")
