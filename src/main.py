"""Main script to scrape deprecations and update data.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .providers import SCRAPERS


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


def scrape_all() -> list[dict]:
    """Scrape all providers and return results."""
    all_deprecations = []
    previous_data = read_existing_data()

    for scraper_class in SCRAPERS:
        provider_name = scraper_class.provider_name
        try:
            scraper = scraper_class()
            deprecations = scraper.scrape()
            deprecation_dicts = [item.to_dict() for item in deprecations]
            all_deprecations.extend(deprecation_dicts)
            print(f"✓ Scraped {provider_name}: {len(deprecations)} deprecations")
        except Exception as exc:
            print(f"✗ Failed to scrape {provider_name}: {exc}")
            previous_provider_data = [
                item for item in previous_data if item.get("provider") == provider_name
            ]
            all_deprecations.extend(previous_provider_data)
            print(f"  → Using {len(previous_provider_data)} cached items")

    return all_deprecations


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
    """Normalize fields so saved output stays recognizable and stable."""
    normalized = item.copy()
    model_id = (normalized.get("model_id") or "").strip()
    model_name = (normalized.get("model_name") or "").strip()

    if model_id:
        normalized["model_id"] = model_id
    if not model_name or model_name == "<UNKNOWN>":
        normalized["model_name"] = model_id
    else:
        normalized["model_name"] = model_name

    return normalized


def _item_quality(item: dict) -> tuple:
    """Score items so deduplication keeps the richer record."""
    return (
        int(bool(item.get("announcement_date"))),
        int(bool(item.get("shutdown_date"))),
        int(bool(item.get("replacement_models"))),
        len(item.get("deprecation_context", "") or ""),
        len(item.get("model_name", "") or ""),
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


if __name__ == "__main__":
    print("Scraping...")

    scraped_data = scrape_all()
    print(f"\nTotal scraped: {len(scraped_data)} deprecations")

    existing_data = read_existing_data()
    changed_items = find_changed_items(scraped_data, existing_data)
    if not changed_items:
        print("✓ No content changes detected")

    final_data = merge_data(scraped_data, existing_data, changed_items)
    save_data(final_data)

    print("\nGenerating feeds...")

    from .rss_gen import create_rss_feed, save_rss_feed

    feed = create_rss_feed(final_data)
    save_rss_feed(feed)

    from .json_feed_gen import create_json_feed, save_json_feed, save_raw_api

    json_feed = create_json_feed(final_data)
    save_json_feed(json_feed)
    save_raw_api(final_data)

    print("✓ All feeds generated successfully")
