"""Tests for Azure AI Foundry scraper."""

from pathlib import Path
from src.scrapers.azure_foundry_scraper import AzureFoundryScraper


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "azure_foundry_lifecycle.html"


def _load_items():
    scraper = AzureFoundryScraper()
    with open(FIXTURE_PATH, "r") as f:
        html = f.read()
    return scraper, scraper.extract_structured_deprecations(html)


def test_extracts_valid_models_from_fixture():
    """Verify scraper extracts only valid model IDs from fixture."""
    _, items = _load_items()

    assert len(items) > 0, "Should extract at least one deprecation item"

    invalid_placeholders = ["N/A", "TBD", "NONE", "—", "-"]
    for item in items:
        assert item.model_id not in invalid_placeholders, (
            f"Model ID should not be a placeholder: {item.model_id}"
        )
        assert item.model_id.strip(), "Model ID should not be empty"
        assert item.model_id.strip(), f"Model ID should not be blank: {item.model_id}"
        assert " " not in item.model_id, (
            f"Model ID should not be a display label: {item.model_id}"
        )


def test_extracts_valid_dates():
    """Verify all extracted items have valid dates."""
    _, items = _load_items()

    for item in items:
        assert item.shutdown_date is not None, (
            f"Item {item.model_id} should have a shutdown date"
        )
        assert item.announcement_date is not None, (
            f"Item {item.model_id} should have an announcement date"
        )
        assert item.announcement_date <= item.shutdown_date, (
            f"Announcement date ({item.announcement_date}) should be before "
            f"shutdown date ({item.shutdown_date}) for {item.model_id}"
        )


def test_extracts_provider_correctly():
    """Verify provider is set correctly."""
    _, items = _load_items()

    for item in items:
        assert item.provider == "Azure", (
            f"Provider should be 'Azure', got '{item.provider}'"
        )


def test_handles_replacement_models():
    """Verify replacement models are extracted when available."""
    _, items = _load_items()

    with_replacement = [item for item in items if item.replacement_models]
    without_replacement = [item for item in items if not item.replacement_models]

    assert len(with_replacement) > 0, "Should have some items with replacement models"
    assert len(without_replacement) > 0, (
        "Should have some items without replacement models"
    )

    invalid_placeholders = ["N/A", "TBD", "NONE", "—", "-"]
    for item in with_replacement:
        assert isinstance(item.replacement_models, list), (
            f"Replacement models should be a list: {item.replacement_models}"
        )
        for model in item.replacement_models:
            assert model not in invalid_placeholders, (
                f"Replacement model should not be a placeholder: {model}"
            )
            assert " " not in model, (
                f"Replacement model should be an identifier, not a display label: {model}"
            )


def test_includes_url_for_each_item():
    """Verify each item has a URL."""
    _, items = _load_items()

    for item in items:
        assert item.url, f"Item {item.model_id} should have a URL"
        assert item.url.startswith("http"), f"URL should be absolute: {item.url}"


def test_does_not_duplicate_models():
    """Verify no duplicate models are extracted from a single table row."""
    _, items = _load_items()

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
    _, items = _load_items()
    model_ids = [item.model_id for item in items]

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


def test_extracts_href_backed_model_ids_and_skips_display_only_labels():
    """Verify Azure model links are converted to stable IDs and display-only rows are skipped."""
    _, items = _load_items()
    model_ids = {item.model_id for item in items}

    assert "Cohere-command-r" in model_ids
    assert "Cohere-command-r-plus" in model_ids
    assert "Command R" not in model_ids
    assert "Command R+" not in model_ids
    assert "Jamba Instruct" not in model_ids

    command_r = next(item for item in items if item.model_id == "Cohere-command-r")
    assert command_r.replacement_models == ["Cohere-command-r-08-2024"]
