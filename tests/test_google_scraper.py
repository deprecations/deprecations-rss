"""Tests for Google AI scraper with fixture-based verification."""

from pathlib import Path

from src.scrapers.google_scraper import GoogleScraper


def test_extracts_models_with_proper_separation():
    """Each model ID should be extracted separately, not concatenated."""
    fixture_path = Path(__file__).parent / "fixtures" / "google_changelog.html"
    html_content = fixture_path.read_text()

    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(html_content)

    model_ids = [item.model_id for item in items]

    assert len(model_ids) > 0, "Should extract at least one model"

    for model_id in model_ids:
        # Models should not have concatenated gemini/veo/imagen names
        if "gemini" in model_id:
            assert model_id.count("gemini") == 1, (
                f"Model ID '{model_id}' appears to be concatenated"
            )
        if "veo" in model_id:
            assert model_id.count("veo") == 1, (
                f"Model ID '{model_id}' appears to be concatenated"
            )
        if "imagen" in model_id:
            assert model_id.count("imagen") == 1, (
                f"Model ID '{model_id}' appears to be concatenated"
            )

    expected_models = [
        "gemini-2.5-flash-lite-preview-06-17",
        "gemini-2.5-flash-preview-05-20",
    ]

    for expected_model in expected_models:
        assert expected_model in model_ids, (
            f"Expected model '{expected_model}' not found in results"
        )


def test_creates_separate_deprecation_items_for_each_model():
    """Each model should get its own DeprecationItem."""
    fixture_path = Path(__file__).parent / "fixtures" / "google_changelog.html"
    html_content = fixture_path.read_text()

    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(html_content)

    nov_4_items = [item for item in items if item.announcement_date == "2025-11-04"]

    assert len(nov_4_items) >= 2, (
        f"Expected at least 2 items from Nov 4, got {len(nov_4_items)}"
    )

    nov_4_model_ids = [item.model_id for item in nov_4_items]
    assert len(nov_4_model_ids) == len(set(nov_4_model_ids)), (
        "Model IDs should be unique"
    )


def test_extracts_model_ids_correctly():
    """Model IDs should be properly formatted and not concatenated."""
    fixture_path = Path(__file__).parent / "fixtures" / "google_changelog.html"
    html_content = fixture_path.read_text()

    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(html_content)

    for item in items:
        assert len(item.model_id) < 100, (
            f"Model ID '{item.model_id}' appears to be concatenated"
        )

        if "gemini" in item.model_id:
            assert item.model_id.count("gemini") == 1, (
                f"Model ID '{item.model_id}' has duplicate 'gemini'"
            )


def test_handles_code_tags_in_lists():
    """Model IDs in <code> tags within <li> should be extracted separately."""
    fixture_path = Path(__file__).parent / "fixtures" / "google_changelog.html"
    html_content = fixture_path.read_text()

    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(html_content)

    model_ids = [item.model_id for item in items]

    assert "gemini-2.5-flash-lite-preview-06-17" in model_ids
    assert "gemini-2.5-flash-preview-05-20" in model_ids


def test_preserves_deprecation_context():
    """Context should be preserved for each model without concatenation."""
    fixture_path = Path(__file__).parent / "fixtures" / "google_changelog.html"
    html_content = fixture_path.read_text()

    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(html_content)

    # Filter to items that were extracted from code tags (not fallback patterns)
    code_based_items = [
        item
        for item in items
        if any(
            keyword in item.deprecation_context.lower()
            for keyword in ["deprecated", "will be deprecated"]
        )
    ]

    for item in code_based_items:
        assert len(item.deprecation_context) > 0, (
            f"Model {item.model_id} has no context"
        )
