"""Integration tests for AWS Bedrock scraper with fixture-based testing."""

from pathlib import Path
import re
import pytest
from src.scrapers.aws_bedrock_scraper import AWSBedrockScraper


@pytest.fixture
def fixture_html():
    """Load AWS Bedrock lifecycle HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "aws_bedrock_lifecycle.html"
    return fixture_path.read_text()


def test_scraper_initialization():
    """Should initialize with correct configuration."""
    scraper = AWSBedrockScraper()
    assert scraper.provider_name == "AWS Bedrock"
    assert (
        scraper.url
        == "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html"
    )
    assert scraper.requires_playwright is False


def test_extracts_legacy_models_with_dates(fixture_html):
    """Should extract legacy models with dates in ISO format."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    assert len(items) > 0, "Should find at least one deprecated model"

    # Find Stable Diffusion XL 1.0 model
    sd_xl_item = next(
        (item for item in items if "Stable Diffusion XL 1.0" in item.model_name), None
    )
    assert sd_xl_item is not None, "Should find Stable Diffusion XL 1.0"

    # Verify dates are in ISO format (not with region info)
    assert sd_xl_item.announcement_date == "2024-10-16", (
        f"Expected '2024-10-16', got '{sd_xl_item.announcement_date}'"
    )
    assert sd_xl_item.shutdown_date == "2025-05-20", (
        f"Expected '2025-05-20', got '{sd_xl_item.shutdown_date}'"
    )

    # Verify replacement models
    assert sd_xl_item.replacement_models is not None
    assert any("Stable Image Core" in model for model in sd_xl_item.replacement_models)


def test_extracts_eol_models_with_dates(fixture_html):
    """Should extract EOL models with dates in ISO format."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    # Find EOL models (past end-of-life date)
    eol_items = [item for item in items if "Stable Diffusion XL 0.8" in item.model_name]

    if eol_items:
        eol_item = eol_items[0]
        assert eol_item.announcement_date == "2024-02-02"
        assert eol_item.shutdown_date == "2024-04-30"
        assert eol_item.replacement_models is not None
        assert any("Stable Diffusion XL 1.x" in model for model in eol_item.replacement_models)


def test_all_dates_are_iso_format(fixture_html):
    """Should ensure all dates are in ISO format (YYYY-MM-DD) or empty."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    iso_date_pattern = r"^\d{4}-\d{2}-\d{2}$"

    for item in items:
        if item.announcement_date:
            assert re.match(iso_date_pattern, item.announcement_date), (
                f"announcement_date '{item.announcement_date}' for {item.model_name} is not in ISO format"
            )

        if item.shutdown_date:
            assert re.match(iso_date_pattern, item.shutdown_date), (
                f"shutdown_date '{item.shutdown_date}' for {item.model_name} is not in ISO format"
            )


def test_no_region_info_in_dates(fixture_html):
    """Should strip region information from dates."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        # Dates should not contain parentheses or region names
        if item.announcement_date:
            assert "(" not in item.announcement_date, (
                f"announcement_date contains region info: {item.announcement_date}"
            )
            assert "us-east" not in item.announcement_date, (
                f"announcement_date contains region: {item.announcement_date}"
            )

        if item.shutdown_date:
            assert "(" not in item.shutdown_date, (
                f"shutdown_date contains region info: {item.shutdown_date}"
            )
            assert "us-east" not in item.shutdown_date, (
                f"shutdown_date contains region: {item.shutdown_date}"
            )


def test_parse_date_handles_ordinal_dates():
    """Should parse dates with ordinal suffixes like '15th'."""
    scraper = AWSBedrockScraper()

    # Test various date formats with ordinals
    assert scraper.parse_date("July 15th, 2025") == "2025-07-15"
    assert scraper.parse_date("January 15th, 2026") == "2026-01-15"


def test_parse_date_strips_region_info():
    """Should strip region information before parsing."""
    scraper = AWSBedrockScraper()

    # Test with region info
    assert scraper.parse_date("May 20, 2025 (us-east-1 and us-west-2)") == "2025-05-20"
    assert (
        scraper.parse_date("October 16, 2024 (us-east-1 and us-west-2)") == "2024-10-16"
    )
    assert scraper.parse_date("July 15th, 2025 (all Regions)") == "2025-07-15"


def test_parse_date_returns_empty_for_invalid():
    """Should return empty string for unparseable dates."""
    scraper = AWSBedrockScraper()

    assert scraper.parse_date("NA") == ""
    assert scraper.parse_date("TBD") == ""
    assert scraper.parse_date("—") == ""
    assert scraper.parse_date("") == ""


def test_extracts_multiple_legacy_models(fixture_html):
    """Should extract all legacy models from the table."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    # Should have multiple deprecated models
    assert len(items) >= 2, "Should find at least 2 deprecated models"

    # All items should have AWS Bedrock as provider
    for item in items:
        assert item.provider == "AWS Bedrock"
        assert item.url == scraper.url


def test_deprecation_context_is_meaningful(fixture_html):
    """Should create meaningful deprecation context."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        assert item.deprecation_context, "Should have deprecation context"
        assert item.model_name in item.deprecation_context, (
            "Context should mention model name"
        )

        # Should mention dates if present
        if item.announcement_date:
            assert (
                "legacy" in item.deprecation_context.lower()
                or "end-of-life" in item.deprecation_context.lower()
            )
