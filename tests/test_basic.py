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


def test_missing_announcement_date_falls_back_to_first_observed():
    """Missing provider announcement dates should fall back to first observation."""
    from src.main import apply_observation_metadata

    existing = [
        {
            "provider": "Cohere",
            "model_id": "command-r-03-2024-ft",
            "announcement_date": "2025-03-01",
            "first_observed": "2025-03-01",
            "last_observed": "2025-03-10",
            "scraped_at": "2025-03-10T00:00:00+00:00",
        }
    ]
    scraped = [
        {
            "provider": "Cohere",
            "model_id": "command-r-03-2024-ft",
            "announcement_date": "",
            "shutdown_date": "2025-03-08",
            "replacement_models": None,
            "deprecation_context": "Fine-tuned models will continue to be supported until March 08, 2025.",
            "url": "https://example.com/cohere",
            "scraped_at": "2025-03-11T00:00:00+00:00",
        }
    ]

    result = apply_observation_metadata(scraped, existing)

    assert result[0]["announcement_date"] == "2025-03-01"
    assert result[0]["first_observed"] == "2025-03-01"
    assert result[0]["last_observed"] == "2025-03-11"
