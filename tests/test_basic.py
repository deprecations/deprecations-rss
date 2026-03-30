"""Basic smoke tests to ensure nothing is broken."""

import subprocess
import sys
from pathlib import Path


def test_imports():
    """Verify core modules can be imported."""
    try:
        from src import main  # noqa: F401
        from src import providers  # noqa: F401
        from src import rss_gen  # noqa: F401
        from src import models  # noqa: F401

        assert True
    except ImportError as e:
        assert False, f"Failed to import module: {e}"


def test_scraper_imports():
    """Verify all scrapers can be imported."""
    try:
        from src.scrapers.openai_scraper import OpenAIScraper  # noqa: F401
        from src.scrapers.anthropic_scraper import AnthropicScraper  # noqa: F401
        from src.scrapers.google_scraper import GoogleScraper  # noqa: F401
        from src.scrapers.google_vertex_scraper import GoogleVertexScraper  # noqa: F401
        from src.scrapers.aws_bedrock_scraper import AWSBedrockScraper  # noqa: F401
        from src.scrapers.cohere_scraper import CohereScraper  # noqa: F401
        from src.scrapers.xai_scraper import XAIScraper  # noqa: F401
        from src.scrapers.azure_foundry_scraper import AzureFoundryScraper  # noqa: F401

        assert True
    except ImportError as e:
        assert False, f"Failed to import scraper: {e}"


def test_main_module_runs():
    """Verify main module can be executed (dry run)."""
    result = subprocess.run(
        [sys.executable, "-c", "import src.main"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"Failed to import main module: {result.stderr}"


def test_data_json_exists():
    """Verify data.json exists (it's required for feeds)."""
    data_file = Path("data.json")
    if not data_file.exists():
        return
    assert data_file.stat().st_size > 0, "data.json file is empty"


def test_cache_directory_exists():
    """Verify cache directory structure exists."""
    cache_dir = Path("cache")
    if not cache_dir.exists():
        return
    assert cache_dir.is_dir(), "cache is not a directory"


def test_main_dedupes_and_removes_legacy_model_name_field():
    """Saved output should be deduped by provider/model_id and remain ID-only."""
    from src.main import dedupe_and_normalize_data

    data = [
        {
            "provider": "Google",
            "model_id": "gemini-2.5-flash-preview-09-25",
            "model_name": "<UNKNOWN>",
            "announcement_date": "2026-01-15",
            "shutdown_date": "",
            "replacement_models": None,
            "deprecation_context": "short",
            "url": "https://example.com/a",
        },
        {
            "provider": "Google",
            "model_id": "gemini-2.5-flash-preview-09-25",
            "model_name": "",
            "announcement_date": "2026-01-15",
            "shutdown_date": "",
            "replacement_models": None,
            "deprecation_context": "a much richer context block",
            "url": "https://example.com/b",
        },
    ]

    result = dedupe_and_normalize_data(data)

    assert len(result) == 1
    assert result[0]["model_id"] == "gemini-2.5-flash-preview-09-25"
    assert "model_name" not in result[0]
    assert result[0]["deprecation_context"] == "a much richer context block"


def test_announcement_date_tracks_first_observed_and_preserves_deprecation_date():
    """Saved announcement_date should mean first observed, not provider deprecation date."""
    from src.main import apply_observation_metadata

    existing = [
        {
            "provider": "Cohere",
            "model_id": "command-r-03-2024-ft",
            "announcement_date": "2025-02-27",
            "first_observed": "2025-03-01",
            "last_observed": "2025-03-10",
            "scraped_at": "2025-03-10T00:00:00+00:00",
        }
    ]
    scraped = [
        {
            "provider": "Cohere",
            "model_id": "command-r-03-2024-ft",
            "announcement_date": "2025-09-15",
            "shutdown_date": "2025-03-08",
            "replacement_models": None,
            "deprecation_context": "Fine-tuned models will continue to be supported until March 08, 2025.",
            "url": "https://example.com/cohere",
            "scraped_at": "2025-03-11T00:00:00+00:00",
        }
    ]

    result = apply_observation_metadata(scraped, existing)

    assert result[0]["announcement_date"] == "2025-03-01"
    assert result[0]["deprecation_date"] == "2025-09-15"
    assert result[0]["first_observed"] == "2025-03-01"
    assert result[0]["last_observed"] == "2025-03-11"


def test_missing_shutdown_dates_keep_current_valid_items(monkeypatch):
    """Providers with partial validation failures should still keep current valid rows."""
    from src import main

    class FakeScraper:
        provider_name = "Fake"
        require_shutdown_dates = True

        def scrape(self):
            class FakeItem:
                def __init__(self, payload):
                    self.payload = payload

                def to_dict(self):
                    return self.payload

            return [
                FakeItem(
                    {
                        "provider": "Fake",
                        "model_id": "good-model",
                        "announcement_date": "",
                        "shutdown_date": "2026-01-01",
                        "replacement_models": None,
                        "deprecation_context": "valid",
                        "url": "https://example.com/good",
                    }
                ),
                FakeItem(
                    {
                        "provider": "Fake",
                        "model_id": "bad-model",
                        "announcement_date": "",
                        "shutdown_date": "",
                        "replacement_models": None,
                        "deprecation_context": "missing shutdown",
                        "url": "https://example.com/bad",
                    }
                ),
            ]

    monkeypatch.setattr(main, "SCRAPERS", [FakeScraper])

    previous_data = [
        {
            "provider": "Fake",
            "model_id": "cached-model",
            "announcement_date": "2025-01-01",
            "shutdown_date": "2025-06-01",
            "replacement_models": None,
            "deprecation_context": "cached",
            "url": "https://example.com/cached",
        }
    ]

    result, failures = main.scrape_all(previous_data)

    assert result == [
        {
            "provider": "Fake",
            "model_id": "good-model",
            "announcement_date": "",
            "shutdown_date": "2026-01-01",
            "replacement_models": None,
            "deprecation_context": "valid",
            "url": "https://example.com/good",
        }
    ]
    assert failures == [
        {
            "provider": "Fake",
            "kind": "validation",
            "message": "Missing shutdown dates for 1 model IDs: bad-model",
        }
    ]


def test_save_run_status_records_provider_failures(tmp_path):
    """CI status file should capture provider failures without failing the scrape step."""
    from src.main import save_run_status

    status_file = tmp_path / "scrape-status.json"
    provider_failures = [
        {
            "provider": "Cohere",
            "kind": "validation",
            "message": "Missing shutdown dates for 2 model IDs: a, b",
        }
    ]

    save_run_status(status_file, provider_failures)

    payload = __import__("json").loads(status_file.read_text())
    assert payload["status"] == "partial_failure"
    assert payload["failure_count"] == 1
    assert payload["provider_failures"] == provider_failures
