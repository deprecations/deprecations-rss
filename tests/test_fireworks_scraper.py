"""Tests for the Fireworks AI changelog scraper."""

from pathlib import Path

import pytest

from src.scrapers.fireworks_scraper import FireworksScraper


PREFIX = "accounts/fireworks/models/"


@pytest.fixture
def scraper():
    return FireworksScraper()


@pytest.fixture
def items(scraper):
    fixture_path = Path(__file__).parent / "fixtures" / "fireworks_changelog.md"
    content = fixture_path.read_text(encoding="utf-8")
    return {
        item.model_id: item for item in scraper.extract_structured_deprecations(content)
    }


def test_source_is_changelog_markdown(scraper):
    assert scraper.provider_name == "Fireworks AI"
    assert scraper.get_source_url() == "https://docs.fireworks.ai/updates/changelog.md"
    assert scraper.require_shutdown_dates is True


def test_every_row_has_dates_and_context(items):
    assert items
    for item in items.values():
        assert item.provider == "Fireworks AI"
        assert item.shutdown_date
        assert item.deprecation_date
        assert item.deprecation_context
        assert item.url == "https://docs.fireworks.ai/updates/changelog"


def test_upcoming_notice_uses_announced_shutdown_date(items):
    item = items[f"{PREFIX}gpt-oss-120b"]
    assert item.deprecation_date == "2026-10-19"
    assert item.shutdown_date == "2026-11-07"


def test_dedicated_deployment_advice_is_not_a_replacement(items):
    # "move to a dedicated deployment of GPT OSS 120B" names no other model link.
    assert items[f"{PREFIX}gpt-oss-120b"].replacement_models is None
    assert items[f"{PREFIX}nemotron-3-ultra-nvfp4"].replacement_models is None


def test_us_endpoint_only_retirements_produce_no_rows(items):
    # The global MiniMax M3 and GLM 5.3 Flash endpoints remain available.
    assert f"{PREFIX}minimax-m3" not in items
    assert f"{PREFIX}glm-5p3-flash" not in items


def test_fast_mode_retirement_does_not_retire_the_base_model(items):
    # 2026-08-27 retires Kimi K2.6 Turbo / Fast, which links to kimi-k2p6 and
    # migrates to kimi-k2p6 standard mode. kimi-k2p6 itself retires on 2026-09-25.
    kimi = items[f"{PREFIX}kimi-k2p6"]
    assert kimi.shutdown_date == "2026-09-25"
    assert kimi.deprecation_date == "2026-09-12"
    assert kimi.replacement_models == [f"{PREFIX}glm-5p3", f"{PREFIX}kimi-k3"]

    code = items[f"{PREFIX}kimi-k2p7-code"]
    assert code.shutdown_date == "2026-09-25"


def test_including_variants_give_one_row_for_the_base_model(items):
    glm_rows = [model_id for model_id in items if "glm-5p2" in model_id.lower()]
    assert glm_rows == [f"{PREFIX}glm-5p2"]
    assert items[f"{PREFIX}glm-5p2"].replacement_models == [f"{PREFIX}glm-5p3"]
    assert not any("GLM 5.2" in model_id for model_id in items)


def test_upcoming_and_in_effect_notices_merge(items):
    item = items[f"{PREFIX}deepseek-v4-pro-0813"]
    assert item.deprecation_date == "2026-09-12"
    assert item.shutdown_date == "2026-09-25"
    assert "now in effect" in item.deprecation_context
    assert item.replacement_models == [f"{PREFIX}deepseek-v4p1-flash"]


def test_effective_notice_uses_effective_date(items):
    item = items[f"{PREFIX}deepseek-v4-pro"]
    assert item.shutdown_date == "2026-08-27"
    assert item.replacement_models == [f"{PREFIX}deepseek-v4-pro-0813"]


def test_replacements_never_name_the_row_itself(items):
    for model_id, item in items.items():
        assert model_id not in (item.replacement_models or [])


def test_unlinked_models_use_display_name(items):
    llama = items["Llama 3.3 70B Instruct"]
    assert llama.shutdown_date == "2026-05-14"
    assert llama.replacement_models == [f"{PREFIX}gpt-oss-120b"]
    assert items["Inkling"].replacement_models is None


def test_prose_notice_without_date_uses_entry_date(items):
    item = items["MiniMax M2.5"]
    assert item.shutdown_date == "2026-06-17"
    assert item.replacement_models == [f"{PREFIX}minimax-m2p7"]


def test_bullets_win_over_prose_summary(items):
    assert f"{PREFIX}kimi-k2p5" in items
    assert "Kimi K2.5" not in items
    assert items[f"{PREFIX}qwen3p6-plus"].replacement_models == [
        f"{PREFIX}qwen3p7-plus"
    ]


def test_training_feature_and_new_model_entries_are_ignored(items):
    # Serverless Training removals keep the model on inference.
    assert "Qwen 3.5 9B" not in items
    assert "Qwen 3.6 27B" not in items
    # New-model bullets in a deprecation entry are not retirements.
    assert f"{PREFIX}deepseek-v4p1-flash-1017" not in items
    assert "DeepSeek V4.1 Flash 1017" not in items
    assert f"{PREFIX}muse-spark-open" not in items


def test_expected_row_count(items):
    assert len(items) == 26


def test_global_endpoint_remains_available_produces_no_row(scraper):
    # A clean linked subject still gives no row when the notice says the model
    # stays available elsewhere.
    content = """**2026-12-01**

Inference

# Upcoming Serverless deprecation: US endpoint for MiniMax M3

Several Serverless endpoints will be decommissioned on **December 15, 2026**.

* **[MiniMax M3](https://app.fireworks.ai/models/fireworks/minimax-m3)** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)** on the US endpoint. The global MiniMax M3 endpoint remains available.
"""
    assert scraper.extract_structured_deprecations(content) == []
