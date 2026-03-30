"""Tests for markdown-first provider scrapers."""

from src.scrapers.anthropic_scraper import AnthropicScraper
from src.scrapers.cohere_scraper import CohereScraper
from src.scrapers.google_vertex_scraper import GoogleVertexScraper
from src.scrapers.openai_scraper import OpenAIScraper
from src.scrapers.xai_scraper import XAIScraper


def test_openai_extracts_from_markdown_table():
    """OpenAI markdown tables should yield concrete model IDs, not section titles."""
    markdown = """
# Deprecations

## Deprecation history

### 2025-11-18: chatgpt-4o-latest snapshot

On November 18th, 2025, we notified developers using `chatgpt-4o-latest` model snapshot of its deprecation.

| Shutdown date | Model / system | Recommended replacement |
| ------------- | -------------- | ----------------------- |
| 2026-02-17    | `chatgpt-4o-latest` | `gpt-5.1-chat-latest` |
"""

    items = OpenAIScraper().extract_structured_deprecations(markdown)

    assert len(items) == 1
    assert items[0].model_id == "chatgpt-4o-latest"
    assert items[0].shutdown_date == "2026-02-17"
    assert items[0].replacement_models == ["gpt-5.1-chat-latest"]


def test_openai_extracts_aliases_and_strips_replacement_footnotes():
    """OpenAI rows with aliases should emit all model IDs and clean replacement IDs."""
    markdown = """
# Deprecations

## Deprecation history

### 2025-09-26: GPT-4 preview models

| Shutdown date | Model / system | Recommended replacement |
| ------------- | -------------- | ----------------------- |
| 2026-03-26 | `gpt-4-0125-preview` (including `gpt-4-turbo-preview` and `gpt-4-turbo-preview-completions`, which point to this snapshot) | `gpt-5` or `gpt-4.1*` |
"""

    items = OpenAIScraper().extract_structured_deprecations(markdown)
    model_ids = {item.model_id for item in items}

    assert model_ids == {
        "gpt-4-0125-preview",
        "gpt-4-turbo-preview",
        "gpt-4-turbo-preview-completions",
    }
    for item in items:
        assert item.replacement_models == ["gpt-5", "gpt-4.1"]


def test_anthropic_extracts_from_markdown_history():
    """Anthropic markdown history tables should produce correct dates and replacements."""
    markdown = """
# Model deprecations

## Model status

| API Model Name | Current State | Deprecated | Tentative Retirement Date |
| --- | --- | --- | --- |
| `claude-3-7-sonnet-20250219` | Deprecated | October 28, 2025 | February 19, 2026 |

## Deprecation history

### 2025-10-28: Claude Sonnet 3.7 model

On October 28, 2025, Anthropic notified developers using Claude Sonnet 3.7 model of its upcoming retirement on the Claude API.

| Retirement Date | Deprecated Model | Recommended Replacement |
| --- | --- | --- |
| February 19, 2026 | `claude-3-7-sonnet-20250219` | `claude-opus-4-6` |
"""

    items = AnthropicScraper().extract_structured_deprecations(markdown)

    assert len(items) == 1
    assert items[0].model_id == "claude-3-7-sonnet-20250219"
    assert items[0].announcement_date == "2025-10-28"
    assert items[0].shutdown_date == "2026-02-19"
    assert items[0].replacement_models == ["claude-opus-4-6"]


def test_cohere_extracts_concrete_models_without_llm():
    """Cohere markdown should be parsed deterministically without LLM assistance."""
    markdown = """
# Deprecations

### 2026-04-04: Embed v2.0, Aya Expanse 8B

Effective April 4th, 2026, the following models will be retired:

* `embed-english-v2.0`
* `c4ai-aya-expanse-8b`

We encourage you to migrate to our latest models:

* Embedding tasks alternatives:
  * `embed-english-v3.0`
  * `embed-v4.0`
* Chat tasks alternatives:
  * `command-a-03-2025`

### 2024-12-02: Rerank v2.0

| Shutdown Date | Deprecated Model | Deprecated Model Price | Recommended Replacement |
| --- | --- | --- | --- |
| 2025-04-30 | `rerank-english-v2.0` | $1.00 / 1K searches | `rerank-v3.5` |
"""

    items = CohereScraper().extract_structured_deprecations(markdown)
    model_ids = {item.model_id for item in items}

    assert "embed-english-v2.0" in model_ids
    assert "c4ai-aya-expanse-8b" in model_ids
    assert "rerank-english-v2.0" in model_ids
    assert "classify-default-embed" not in model_ids


def test_cohere_command_section_uses_header_date_as_deprecation_date_source():
    """Cohere header dates should be captured from the section heading."""
    markdown = """
# Deprecations

### 2025-09-15: Command model deprecations

Effective September 15, 2025, the following deprecations will roll out.

Deprecated Models:

* `command-r-03-2024` (and the alias `command-r`)
* `command-light`
* `summarize`

For command model replacements, we recommend you use `command-r-08-2024`, `command-r-plus-08-2024`, or `command-a-03-2025` instead.
"""

    items = CohereScraper().extract_structured_deprecations(markdown)
    model_ids = {item.model_id for item in items}

    assert model_ids == {"command-r-03-2024", "command-r", "command-light"}
    for item in items:
        assert item.announcement_date == "2025-09-15"
        assert item.deprecation_date == "2025-09-15"
        assert item.shutdown_date == ""
        assert item.replacement_models == [
            "command-r-08-2024",
            "command-r-plus-08-2024",
            "command-a-03-2025",
        ]


def test_cohere_effective_shutdown_section_uses_header_date():
    """Cohere effective retirement dates should come from the header date."""
    markdown = """
# Deprecations

### 2026-04-04: Embed v2.0, Aya Expanse 8B

Effective April 4th, 2026, the following models will be retired:

* `embed-english-v2.0`

We encourage you to migrate to our latest models:

* Embedding tasks alternatives:
  * `embed-v4.0`
"""

    items = CohereScraper().extract_structured_deprecations(markdown)

    assert len(items) == 1
    assert items[0].model_id == "embed-english-v2.0"
    assert items[0].announcement_date == "2026-04-04"
    assert items[0].shutdown_date == "2026-04-04"


def test_google_vertex_partner_page_extracts_deprecated_partner_model():
    """Partner-model sections should yield model IDs and both lifecycle dates."""
    html = """
    <html>
      <body>
        <article>
          <h2 id="claude-3-haiku">Anthropic's Claude 3 Haiku</h2>
          <p>Anthropic's Claude 3 Haiku is deprecated as of February 23, 2026 and will be shut down on August 23, 2026.</p>
          <table>
            <tr><th>Model ID</th><td>claude-3-haiku</td></tr>
          </table>
          <h2 id="next">Claude 3.5 Sonnet</h2>
          <p>Claude 3.5 Sonnet remains GA.</p>
        </article>
      </body>
    </html>
    """

    items = GoogleVertexScraper().extract_structured_deprecations(html)

    assert len(items) == 1
    assert items[0].model_id == "claude-3-haiku"
    assert items[0].announcement_date == "2026-02-23"
    assert items[0].shutdown_date == "2026-08-23"


def test_xai_markdown_returns_no_items_without_explicit_model_tags():
    """xAI migration markdown should not invent deprecations from generic policy text."""
    markdown = """
# Migrating to New Models

You will see `deprecated` tag by the deprecated model IDs on xAI Console models page.
We may transition a `deprecated` model to `obsolete` and discontinue serving the model.
"""

    scraper = XAIScraper()
    assert scraper.extract_structured_deprecations(markdown) == []
    assert scraper.extract_unstructured_deprecations(markdown) == []
