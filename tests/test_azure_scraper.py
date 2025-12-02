"""Tests for Azure AI Foundry scraper."""

from pathlib import Path
from src.scrapers.azure_foundry_scraper import AzureFoundryScraper


def test_extracts_valid_models_from_fixture():
    """Verify scraper extracts only valid model names from fixture."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)

    # Verify we got some items
    assert len(items) > 0, "Should extract at least one deprecation item"

    # Verify no items have invalid/placeholder model IDs
    invalid_placeholders = ["N/A", "TBD", "NONE", "—", "-"]
    for item in items:
        assert item.model_id not in invalid_placeholders, (
            f"Model ID should not be a placeholder: {item.model_id}"
        )
        assert item.model_id.strip(), "Model ID should not be empty"

        # Model name should match model ID
        assert item.model_name == item.model_id, (
            f"Model name ({item.model_name}) should match model ID ({item.model_id})"
        )


def test_extracts_valid_dates():
    """Verify all extracted items have valid dates."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)

    for item in items:
        # Should have shutdown date
        assert item.shutdown_date is not None, (
            f"Item {item.model_id} should have a shutdown date"
        )

        # Should have announcement date
        assert item.announcement_date is not None, (
            f"Item {item.model_id} should have an announcement date"
        )

        # Announcement should be before or equal to shutdown
        assert item.announcement_date <= item.shutdown_date, (
            f"Announcement date ({item.announcement_date}) should be before "
            f"shutdown date ({item.shutdown_date}) for {item.model_id}"
        )


def test_extracts_provider_correctly():
    """Verify provider is set correctly."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)

    for item in items:
        assert item.provider == "Azure", (
            f"Provider should be 'Azure', got '{item.provider}'"
        )


def test_handles_replacement_models():
    """Verify replacement models are extracted when available."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)

    # Some items should have replacement models
    with_replacement = [item for item in items if item.replacement_models]
    without_replacement = [item for item in items if not item.replacement_models]

    # We expect some items to have replacements and some not to
    assert len(with_replacement) > 0, "Should have some items with replacement models"
    assert len(without_replacement) > 0, (
        "Should have some items without replacement models"
    )

    # Replacement models should not be placeholders
    invalid_placeholders = ["N/A", "TBD", "NONE", "—", "-"]
    for item in with_replacement:
        assert isinstance(item.replacement_models, list), (
            f"Replacement models should be a list: {item.replacement_models}"
        )
        for model in item.replacement_models:
            assert model not in invalid_placeholders, (
                f"Replacement model should not be a placeholder: {model}"
            )


def test_includes_url_for_each_item():
    """Verify each item has a URL."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)

    for item in items:
        assert item.url, f"Item {item.model_id} should have a URL"
        assert item.url.startswith("http"), f"URL should be absolute: {item.url}"


def test_does_not_duplicate_models():
    """Verify no duplicate models are extracted from a single table row."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)

    # Check that we don't have exact duplicates (same model, same dates)
    seen = set()
    for item in items:
        key = (item.model_id, item.shutdown_date, item.announcement_date)
        assert key not in seen, (
            f"Duplicate item found: {item.model_id} with dates "
            f"{item.announcement_date} - {item.shutdown_date}"
        )
        seen.add(key)


def test_extracts_known_models():
    """Verify specific known models are extracted."""
    scraper = AzureFoundryScraper()
    fixture_path = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"

    with open(fixture_path, "r") as f:
        html = f.read()

    items = scraper.extract_structured_deprecations(html)
    model_ids = [item.model_id for item in items]

    # Check for some known models that should be in the fixture
    expected_models = [
        "Llama-2-7b",
        "Llama-2-13b",
        "Llama-2-70b",
        "Phi-3-mini-4k-instruct",
    ]

    for expected in expected_models:
        assert expected in model_ids, (
            f"Expected model '{expected}' not found in extracted items"
        )
