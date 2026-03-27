"""Main script to scrape deprecations and update data.json."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .providers import SCRAPERS, TRACKED_PROVIDER_PAGES


def hash_item(item: dict) -> str:
    """Create a stable hash of scraped content to detect changes."""
    key_fields = {
        "provider": item.get("provider", ""),
        "model_id": item.get("model_id", item.get("title", "")),
        "announcement_date": item.get("announcement_date", ""),
        "shutdown_date": item.get("shutdown_date", ""),
        "deprecation_context": item.get("deprecation_context", item.get("content", "")),
        "url": item.get("url", ""),
        "replacement_models": item.get("replacement_models"),
    }
    content_str = json.dumps(key_fields, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()[:16]


def _filter_fallback_items(scraper_class, items: list[dict]) -> list[dict]:
    """Filter fallback items using the current provider validation policy."""
    if getattr(scraper_class, "require_shutdown_dates", False):
        return [item for item in items if item.get("shutdown_date")]
    return items


def _missing_shutdown_items(scraper, items: list[dict]) -> list[str]:
    """Return model IDs missing required shutdown dates for this scraper."""
    if not getattr(scraper, "require_shutdown_dates", False):
        return []
    return [item["model_id"] for item in items if not item.get("shutdown_date")]


def scrape_all(previous_data: list[dict]) -> tuple[list[dict], list[dict]]:
    """Scrape all providers and return results plus provider-level failures."""
    all_deprecations = []
    provider_failures = []

    for scraper_class in SCRAPERS:
        provider_name = scraper_class.provider_name
        scraper = scraper_class()
        try:
            deprecations = scraper.scrape()
            deprecation_dicts = [item.to_dict() for item in deprecations]
            missing_shutdown = _missing_shutdown_items(scraper, deprecation_dicts)
            if missing_shutdown:
                preview = ", ".join(missing_shutdown[:10])
                message = (
                    f"Missing shutdown dates for {len(missing_shutdown)} model IDs: {preview}"
                )
                provider_failures.append(
                    {
                        "provider": provider_name,
                        "kind": "validation",
                        "message": message,
                    }
                )
                print(f"✗ Failed to scrape {provider_name}: {message}")
                valid_items = [
                    item for item in deprecation_dicts if item.get("shutdown_date")
                ]
                if valid_items:
                    all_deprecations.extend(valid_items)
                    print(f"  → Using {len(valid_items)} currently valid scraped items")
                else:
                    previous_provider_data = [
                        item
                        for item in previous_data
                        if item.get("provider") == provider_name
                    ]
                    filtered_previous = _filter_fallback_items(
                        scraper_class, previous_provider_data
                    )
                    all_deprecations.extend(filtered_previous)
                    print(f"  → Using {len(filtered_previous)} cached items")
                continue

            all_deprecations.extend(deprecation_dicts)
            print(f"✓ Scraped {provider_name}: {len(deprecations)} deprecations")
        except Exception as exc:
            provider_failures.append(
                {
                    "provider": provider_name,
                    "kind": "exception",
                    "message": str(exc),
                }
            )
            print(f"✗ Failed to scrape {provider_name}: {exc}")
            previous_provider_data = [
                item for item in previous_data if item.get("provider") == provider_name
            ]
            filtered_previous = _filter_fallback_items(
                scraper_class, previous_provider_data
            )
            all_deprecations.extend(filtered_previous)
            print(f"  → Using {len(filtered_previous)} cached items")

    return all_deprecations, provider_failures


def read_existing_data() -> list[dict]:
    """Read existing data from data.json."""
    data_file = Path("data.json")
    if not data_file.exists():
        return []

    try:
        with open(data_file, encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, IOError):
        return []


def find_changed_items(
    scraped_data: list[dict], existing_data: list[dict]
) -> list[dict]:
    """Find items that are new or have changed content."""
    existing_hashes = {hash_item(item) for item in existing_data}
    changed_items = []
    for item in scraped_data:
        item_hash = hash_item(item)
        if item_hash not in existing_hashes:
            item["_hash"] = item_hash
            changed_items.append(item)
    return changed_items


def merge_data(
    scraped_data: list[dict], existing_data: list[dict], changed_items: list[dict]
) -> list[dict]:
    """Merge scraped data with existing data while preserving unchanged items."""
    existing_by_hash = {hash_item(item): item for item in existing_data}
    changed_by_hash = {
        item.get("_hash", hash_item(item)): item for item in changed_items
    }

    result = []
    for item in scraped_data:
        item_hash = hash_item(item)
        if item_hash in changed_by_hash:
            changed = changed_by_hash[item_hash].copy()
            changed.pop("_hash", None)
            result.append(changed)
        elif item_hash in existing_by_hash:
            result.append(existing_by_hash[item_hash])
        else:
            result.append(item)

    return result


def normalize_item_fields(item: dict) -> dict:
    """Normalize fields so saved output stays ID-only and stable."""
    normalized = item.copy()
    normalized["model_id"] = (normalized.get("model_id") or "").strip()
    normalized.pop("model_name", None)
    return normalized


def apply_observation_metadata(
    scraped_data: list[dict], existing_data: list[dict]
) -> list[dict]:
    """Preserve first/last observation dates and backfill missing announcement dates."""
    previous_by_key = {
        (item.get("provider", ""), item.get("model_id", "")): item
        for item in existing_data
        if item.get("provider") and item.get("model_id")
    }

    enriched = []
    today = datetime.now(timezone.utc).date().isoformat()

    for raw_item in scraped_data:
        item = normalize_item_fields(raw_item)
        key = (item.get("provider", ""), item.get("model_id", ""))
        previous = previous_by_key.get(key, {})

        observed_on = (item.get("scraped_at") or "")[:10] or today
        first_observed = previous.get("first_observed") or observed_on
        previous_last_observed = previous.get("last_observed") or ""
        last_observed = (
            max(previous_last_observed, observed_on)
            if previous_last_observed
            else observed_on
        )

        item["first_observed"] = first_observed
        item["last_observed"] = last_observed

        if not item.get("announcement_date"):
            item["announcement_date"] = first_observed

        enriched.append(item)

    return enriched


def _item_quality(item: dict) -> tuple:
    """Score items so deduplication keeps the richer record."""
    return (
        int(bool(item.get("announcement_date"))),
        int(bool(item.get("shutdown_date"))),
        int(bool(item.get("replacement_models"))),
        len(item.get("deprecation_context", "") or ""),
    )


def dedupe_and_normalize_data(data: list[dict]) -> list[dict]:
    """Deduplicate by provider/model_id and normalize saved fields."""
    deduped: dict[tuple[str, str], dict] = {}

    for raw_item in data:
        item = normalize_item_fields(raw_item)
        key = (item.get("provider", ""), item.get("model_id", ""))
        existing = deduped.get(key)
        if existing is None or _item_quality(item) > _item_quality(existing):
            deduped[key] = item

    return list(deduped.values())


def save_data(data: list[dict]):
    """Save data to data.json."""
    normalized_data = dedupe_and_normalize_data(data)
    output_file = Path("data.json")
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(normalized_data, file, indent=2)
    print(f"\n✓ Saved {len(normalized_data)} deprecation notices to data.json")


def save_provider_pages():
    """Save tracked provider page metadata for the landing page."""
    output_dir = Path("docs/v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "providers.json"
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(TRACKED_PROVIDER_PAGES, file, indent=2)
    print(f"Provider metadata saved to {output_file}")


def save_run_status(status_file: str | os.PathLike[str], provider_failures: list[dict]):
    """Save provider-level scrape status for CI to evaluate after commit/push."""
    output_file = Path(status_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "partial_failure" if provider_failures else "success",
        "failure_count": len(provider_failures),
        "provider_failures": provider_failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    print(f"Run status saved to {output_file}")


if __name__ == "__main__":
    print("Scraping...")

    status_file = os.environ.get("SCRAPE_STATUS_FILE", "")
    existing_data = read_existing_data()
    scraped_data, provider_failures = scrape_all(existing_data)
    scraped_data = apply_observation_metadata(scraped_data, existing_data)
    print(f"\nTotal scraped: {len(scraped_data)} deprecations")

    changed_items = find_changed_items(scraped_data, existing_data)
    if not changed_items:
        print("✓ No content changes detected")

    final_data = merge_data(scraped_data, existing_data, changed_items)
    final_data = apply_observation_metadata(final_data, existing_data)
    normalized_data = dedupe_and_normalize_data(final_data)
    save_data(normalized_data)

    print("\nGenerating feeds...")

    from .rss_gen import create_rss_feed, save_rss_feed

    feed = create_rss_feed(normalized_data)
    save_rss_feed(feed)

    from .json_feed_gen import create_json_feed, save_json_feed, save_raw_api

    json_feed = create_json_feed(normalized_data)
    save_json_feed(json_feed)
    save_raw_api(normalized_data)
    save_provider_pages()

    if status_file:
        save_run_status(status_file, provider_failures)

    if provider_failures:
        print(f"! Recorded {len(provider_failures)} provider-level scrape failures")

    print("✓ All feeds generated successfully")
