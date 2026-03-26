"""Tests for xAI scraper to ensure it only extracts deprecated models."""

from pathlib import Path
from bs4 import BeautifulSoup
import pytest

from src.scrapers.xai_scraper import XAIScraper


@pytest.fixture
def scraper():
    """Create an XAIScraper instance."""
    return XAIScraper()


@pytest.fixture
def fixture_html():
    """Load the xAI models fixture HTML."""
    fixture_path = Path(__file__).parent / "fixtures" / "xai_models.html"
    with open(fixture_path, "r") as f:
        return f.read()


def test_scraper_initialization(scraper):
    """Test that scraper initializes with correct properties."""
    assert scraper.provider_name == "xAI"
    assert scraper.url == "https://docs.x.ai/developers/models"
    assert scraper.requires_playwright is False


def test_no_false_positives_from_active_models(scraper, fixture_html):
    """Test that active models are not extracted as deprecated."""
    items = scraper.extract_structured_deprecations(fixture_html)

    assert len(items) == 0, f"Expected 0 deprecated models, but got {len(items)}"


def test_no_false_positives_from_unstructured(scraper, fixture_html):
    """Test that unstructured extraction doesn't extract non-deprecated content."""
    items = scraper.extract_unstructured_deprecations(fixture_html)

    assert len(items) == 0, f"Expected 0 deprecated models, but got {len(items)}"


def test_has_deprecation_indicator_with_active_models(scraper, fixture_html):
    """Test that active model rows are not flagged as deprecated."""
    soup = BeautifulSoup(fixture_html, "html.parser")
    table = soup.find("table")
    rows = table.find_all("tr")

    deprecated_count = 0
    for row in rows[1:]:
        if scraper._has_deprecation_indicator(row):
            deprecated_count += 1

    assert deprecated_count == 0, (
        f"Expected 0 rows with deprecation indicators, got {deprecated_count}"
    )


def test_extract_from_models_table_no_false_positives(scraper, fixture_html):
    """Test that models table extraction doesn't produce false positives."""
    soup = BeautifulSoup(fixture_html, "html.parser")
    tables = soup.find_all("table")

    items = scraper._extract_from_models_table(tables[0])

    assert len(items) == 0, f"Expected 0 deprecated models from table, got {len(items)}"


def test_extract_with_deprecated_model_in_text():
    """Test extraction when a model is explicitly marked as deprecated in text."""
    html = """
    <html>
    <body>
        <p>The grok-legacy-v1 model has been deprecated and will be shut down on December 31, 2024.</p>
    </body>
    </html>
    """

    scraper = XAIScraper()
    items = scraper.extract_unstructured_deprecations(html)

    assert len(items) == 1
    assert items[0].model_id == "grok-legacy-v1"
    assert "deprecated" in items[0].deprecation_context.lower()


def test_extract_with_deprecated_model_in_table():
    """Test extraction when a model is marked deprecated in a table row."""
    html = """
    <html>
    <body>
        <table>
            <tr><th>Model</th><th>Status</th></tr>
            <tr><td>grok-old-model</td><td>deprecated</td></tr>
        </table>
    </body>
    </html>
    """

    scraper = XAIScraper()
    items = scraper.extract_structured_deprecations(html)

    assert len(items) == 1
    assert items[0].model_id == "grok-old-model"


def test_does_not_extract_non_grok_models():
    """Test that non-grok model IDs are not extracted."""
    html = """
    <html>
    <body>
        <p>The some-other-api will be deprecated by December 15, 2025.</p>
    </body>
    </html>
    """

    scraper = XAIScraper()
    items = scraper.extract_unstructured_deprecations(html)

    assert len(items) == 0, "Should not extract non-grok model IDs"


def test_does_not_extract_apis_as_models(scraper, fixture_html):
    """Test that APIs mentioned in deprecation text are not extracted as models."""
    soup = BeautifulSoup(fixture_html, "html.parser")
    text = soup.get_text()

    assert "Live Search API will be deprecated" in text

    items = scraper.extract_unstructured_deprecations(fixture_html)

    for item in items:
        assert "API" not in item.model_id, (
            f"Extracted API '{item.model_id}' as a model"
        )


def test_extract_with_multiple_deprecated_models():
    """Test extraction when multiple models are deprecated."""
    html = """
    <html>
    <body>
        <table>
            <tr><th>Model</th><th>Status</th></tr>
            <tr><td>grok-old-1</td><td>deprecated</td></tr>
            <tr><td>grok-current</td><td>active</td></tr>
            <tr><td>grok-old-2</td><td>legacy</td></tr>
        </table>
    </body>
    </html>
    """

    scraper = XAIScraper()
    items = scraper.extract_structured_deprecations(html)

    assert len(items) == 2
    model_ids = {item.model_id for item in items}
    assert "grok-old-1" in model_ids
    assert "grok-old-2" in model_ids
    assert "grok-current" not in model_ids


def test_deprecation_context_is_populated(scraper):
    """Test that deprecation context is captured when extracting models."""
    html = """
    <html>
    <body>
        <p>The grok-test-model is being deprecated due to performance improvements in newer versions.</p>
    </body>
    </html>
    """

    items = scraper.extract_unstructured_deprecations(html)

    assert len(items) == 1
    assert items[0].deprecation_context
    assert "performance improvements" in items[0].deprecation_context.lower()


def test_provider_name_is_set(scraper):
    """Test that all extracted items have correct provider name."""
    html = """
    <html>
    <body>
        <table>
            <tr><th>Model</th><th>Status</th></tr>
            <tr><td>grok-deprecated</td><td>deprecated</td></tr>
        </table>
    </body>
    </html>
    """

    items = scraper.extract_structured_deprecations(html)

    assert len(items) == 1
    assert items[0].provider == "xAI"


def test_url_is_set_in_items(scraper):
    """Test that all extracted items have the source URL set."""
    html = """
    <html>
    <body>
        <table>
            <tr><th>Model</th><th>Status</th></tr>
            <tr><td>grok-test</td><td>deprecated</td></tr>
        </table>
    </body>
    </html>
    """

    items = scraper.extract_structured_deprecations(html)

    assert len(items) == 1
    assert items[0].url == "https://docs.x.ai/developers/models"
