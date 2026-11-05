"""Tests for the Google AI scraper against an excerpt of the Markdoc source."""

from pathlib import Path

from src.scrapers.google_scraper import GoogleScraper


def load_items() -> dict:
    fixture = Path(__file__).parent / "fixtures" / "google_deprecations.md"
    items = GoogleScraper().extract_structured_deprecations(fixture.read_text())
    return {item.model_id: item for item in items}


def test_fetches_markdown_source():
    """ai.google.dev redirects to client-rendered AI Studio pages; fetch the .md source."""
    assert (
        GoogleScraper().get_source_url()
        == "https://aistudio.google.com/docs/deprecations.md"
    )


def test_extracts_only_rows_with_concrete_shutdown_dates():
    """Rows without a dated shutdown ("No shutdown date announced", "N/A") are skipped."""
    assert set(load_items()) == {
        "gemini-2.5-pro",
        "gemini-2.5-computer-use-preview-10-2025",
        "gemini-2.5-pro-preview-03-25",
        "gemini-2.5-pro-preview-05-06",
        "gemini-2.5-pro-preview-06-05",
    }


def test_extracts_shutdown_dates_and_replacements():
    """Replacements stop at the parenthesised note, which repeats the old model."""
    items = load_items()

    assert items["gemini-2.5-pro"].shutdown_date == "2026-12-01"
    assert items["gemini-2.5-pro"].replacement_models == ["gemini-3.8-flash"]
    assert items["gemini-2.5-pro-preview-05-06"].shutdown_date == "2025-12-02"


def test_preserves_section_context_and_anchor():
    """Context names the table section; the URL links to its Markdoc id."""
    items = load_items()

    pro = items["gemini-2.5-pro"]
    assert "Gemini deprecations table: Gemini 2.5 Pro models." in (
        pro.deprecation_context
    )
    assert pro.url == (
        "https://aistudio.google.com/docs/deprecations#gemini-2.5-pro-models"
    )

    preview = items["gemini-2.5-pro-preview-05-06"]
    assert "Gemini 2.5 Pro models: Deprecated models" in preview.deprecation_context
    assert preview.url.endswith("#gemini-2.5-pro-deprecated-models")
