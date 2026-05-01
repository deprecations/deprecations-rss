"""Tests for Google AI scraper with fixture-based verification."""

from pathlib import Path

from src.scrapers.google_scraper import GoogleScraper


def load_fixture() -> str:
    fixture_path = Path(__file__).parent / "fixtures" / "google_deprecations.html"
    return fixture_path.read_text()


def test_extracts_only_rows_with_concrete_shutdown_dates():
    """Rows without dated shutdowns are lifecycle notes, not feed items."""
    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(load_fixture())
    model_ids = {item.model_id for item in items}

    assert model_ids == {
        "gemini-2.5-pro",
        "gemini-2.5-pro-preview-05-06",
        "imagen-4.0-generate-001",
    }
    assert "gemini-3.1-pro-preview" not in model_ids
    assert "veo-3.0-generate-001" not in model_ids


def test_extracts_shutdown_dates_and_replacements():
    """Google deprecation table fields should map cleanly to output fields."""
    scraper = GoogleScraper()
    items = {
        item.model_id: item
        for item in scraper.extract_structured_deprecations(load_fixture())
    }

    assert items["gemini-2.5-pro"].shutdown_date == "2026-06-17"
    assert items["gemini-2.5-pro"].replacement_models == ["gemini-3.1-pro-preview"]
    assert items["imagen-4.0-generate-001"].replacement_models == [
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image",
    ]


def test_preserves_table_section_context_and_url():
    """Context should identify the source table without changelog noise."""
    scraper = GoogleScraper()
    items = {
        item.model_id: item
        for item in scraper.extract_structured_deprecations(load_fixture())
    }

    pro_item = items["gemini-2.5-pro"]
    assert "Gemini deprecations table: Gemini 2.5 Pro" in pro_item.deprecation_context
    assert pro_item.url.endswith("#gemini-2-5-pro")


def test_model_ids_are_not_concatenated():
    """Each table row should create a clean single model ID."""
    scraper = GoogleScraper()
    items = scraper.extract_structured_deprecations(load_fixture())

    for item in items:
        assert len(item.model_id) < 100
        assert item.model_id.count("gemini") <= 1
        assert item.model_id.count("imagen") <= 1
