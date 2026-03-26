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


def test_extracts_true_model_ids_from_active_lookup(fixture_html):
    """Should emit true AWS Bedrock model IDs, not display labels."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    assert len(items) > 0, "Should find at least one deprecated model"

    sonnet_item = next(
        (
            item
            for item in items
            if item.model_id == "anthropic.claude-3-7-sonnet-20250219-v1:0"
        ),
        None,
    )
    assert sonnet_item is not None, "Should resolve Claude 3.7 Sonnet to its Bedrock model ID"
    assert sonnet_item.announcement_date == "2025-10-28"
    assert sonnet_item.shutdown_date == "2026-04-28"
    assert sonnet_item.replacement_models == [
        "anthropic.claude-sonnet-4-5-20250929-v1:0"
    ]
    assert "Claude 3.7 Sonnet" in sonnet_item.deprecation_context


def test_extracts_replacement_model_ids(fixture_html):
    """Should prefer the recommended model ID column for replacements."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    sonnet_v1 = next(
        (
            item
            for item in items
            if item.model_id == "anthropic.claude-3-5-sonnet-20240620-v1:0"
        ),
        None,
    )
    assert sonnet_v1 is not None
    assert sonnet_v1.replacement_models == [
        "anthropic.claude-sonnet-4-5-20250929-v1:0"
    ]


def test_all_dates_are_iso_format(fixture_html):
    """Should ensure all dates are in ISO format (YYYY-MM-DD) or empty."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    iso_date_pattern = r"^\d{4}-\d{2}-\d{2}$"

    for item in items:
        if item.announcement_date:
            assert re.match(iso_date_pattern, item.announcement_date), (
                f"announcement_date '{item.announcement_date}' for {item.model_id} is not in ISO format"
            )

        if item.shutdown_date:
            assert re.match(iso_date_pattern, item.shutdown_date), (
                f"shutdown_date '{item.shutdown_date}' for {item.model_id} is not in ISO format"
            )


def test_no_region_info_in_dates(fixture_html):
    """Should strip region information from dates."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
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

    assert scraper.parse_date("July 15th, 2025") == "2025-07-15"
    assert scraper.parse_date("January 15th, 2026") == "2026-01-15"


def test_parse_date_strips_region_info():
    """Should strip region information before parsing."""
    scraper = AWSBedrockScraper()

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


def test_extracts_only_rows_with_true_model_ids(fixture_html):
    """Should skip AWS lifecycle rows that do not expose or resolve a true model ID."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    assert {item.model_id for item in items} == {
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "anthropic.claude-3-7-sonnet-20250219-v1:0",
    }

    for item in items:
        assert item.provider == "AWS Bedrock"
        assert item.url == scraper.url


def test_does_not_extract_dates_as_model_ids(fixture_html):
    """Continuation rows should not turn regional dates into fake model IDs."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    date_like_prefixes = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    bad_items = [
        item.model_id
        for item in items
        if any(item.model_id.startswith(prefix) for prefix in date_like_prefixes)
    ]

    assert bad_items == [], f"Found date strings being used as model IDs: {bad_items}"


def test_merges_regional_schedule_rows_into_real_model_context():
    """Regional continuation rows should be merged back into the owning model ID."""
    scraper = AWSBedrockScraper()
    html = """
    <html>
      <body>
        <main>
          <h2>Active versions</h2>
          <table>
            <tr>
              <th>Provider</th>
              <th>Model name</th>
              <th>Model ID</th>
            </tr>
            <tr>
              <td>Anthropic</td>
              <td>Claude 3.5 Sonnet v1</td>
              <td>anthropic.claude-3-5-sonnet-20240620-v1:0</td>
            </tr>
          </table>
          <h2>Legacy versions</h2>
          <table>
            <tr>
              <th>Model version</th>
              <th>Legacy date</th>
              <th>Public extended access date</th>
              <th>EOL date</th>
              <th>Recommended model version replacement</th>
              <th>Recommended model ID</th>
            </tr>
            <tr>
              <td rowspan="3">Claude 3.5 Sonnet v1</td>
              <td>August 25, 2025 (us-east-1)</td>
              <td>December 1, 2025</td>
              <td>Mar 1, 2026 (us-east-1)</td>
              <td rowspan="3">Claude Sonnet 4.5</td>
              <td rowspan="3">anthropic.claude-sonnet-4-5-20250929-v1:0</td>
            </tr>
            <tr>
              <td>August 25, 2025 (eu-central-2)</td>
              <td>December 1, 2025</td>
              <td>June 1, 2026 (eu-central-2)</td>
            </tr>
            <tr>
              <td>January 30, 2026 (us-gov-east-1)</td>
              <td>April 30, 2026</td>
              <td>July 30, 2026 (us-gov-east-1)</td>
            </tr>
          </table>
        </main>
      </body>
    </html>
    """

    items = scraper.extract_structured_deprecations(html)

    assert len(items) == 1
    sonnet_v1 = items[0]
    assert sonnet_v1.model_id == "anthropic.claude-3-5-sonnet-20240620-v1:0"
    assert "Additional regional schedule" in sonnet_v1.deprecation_context
    assert "2026-07-30" in sonnet_v1.deprecation_context


def test_deprecation_context_is_meaningful(fixture_html):
    """Should create meaningful deprecation context."""
    scraper = AWSBedrockScraper()
    items = scraper.extract_structured_deprecations(fixture_html)

    for item in items:
        assert item.deprecation_context, "Should have deprecation context"
        assert item.model_id in item.deprecation_context, (
            "Context should mention model ID"
        )

        if item.announcement_date:
            assert (
                "legacy" in item.deprecation_context.lower()
                or "end-of-life" in item.deprecation_context.lower()
            )
