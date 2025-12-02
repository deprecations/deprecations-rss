"""Main script to scrape deprecations and update data.json."""

import hashlib
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from .providers import SCRAPERS
from .llm_analyzer import LLMAnalyzer

# Load environment variables
load_dotenv(os.path.expanduser("~/.env"))


def hash_item(item: dict) -> str:
    """Create a stable hash of scraped content to detect changes."""
    # For new model structure, use content_hash if available
    if "content_hash" in item and item["content_hash"]:
        return item["content_hash"]

    # Otherwise hash the key fields that indicate actual content changes
    key_fields = {
        "provider": item.get("provider", ""),
        "model_id": item.get("model_id", item.get("title", "")),
        "shutdown_date": item.get("shutdown_date", ""),
        "deprecation_context": item.get("deprecation_context", item.get("content", "")),
        "url": item.get("url", ""),
        # Include replacement data in hash to detect format changes
        "replacement_models": item.get("replacement_models"),
        "replacement_model": item.get("replacement_model"),  # For backward compatibility
    }
    content_str = json.dumps(key_fields, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()[:16]


def scrape_all():
    """Scrape all providers and return results."""
    all_deprecations = []
    previous_data = read_existing_data()

    for scraper_class in SCRAPERS:
        provider_name = scraper_class.provider_name
        try:
            scraper = scraper_class()
            deprecations = scraper.scrape()

            # Convert DeprecationItem objects to dicts
            deprecation_dicts = [item.to_dict() for item in deprecations]
            all_deprecations.extend(deprecation_dicts)

            print(f"✓ Scraped {provider_name}: {len(deprecations)} deprecations")
        except Exception as e:
            print(f"✗ Failed to scrape {provider_name}: {e}")
            # Backfill with previous data for this provider
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
        with open(data_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def find_changed_items(
    scraped_data: list[dict], existing_data: list[dict]
) -> list[dict]:
    """Find items that are new or have changed content."""
    # Create a set of hashes from existing data
    existing_hashes = {hash_item(item) for item in existing_data}

    # Find items with hashes not in existing data
    changed_items = []
    for item in scraped_data:
        item_hash = hash_item(item)
        if item_hash not in existing_hashes:
            # Add hash to item for later reference
            item["_hash"] = item_hash
            changed_items.append(item)

    return changed_items


def merge_data(
    scraped_data: list[dict], existing_data: list[dict], enhanced_items: list[dict]
) -> list[dict]:
    """
    Merge scraped data with existing data, using enhanced versions where available.

    Strategy:
    1. Create lookup maps for existing and enhanced items by hash
    2. For each scraped item:
       - Use enhanced version if available (new/changed item that was analyzed)
       - Otherwise use existing version if unchanged
       - Otherwise use scraped version (shouldn't happen but safety fallback)
    """
    # Create lookup maps
    existing_by_hash = {hash_item(item): item for item in existing_data}
    enhanced_by_hash = {
        item.get("_hash", hash_item(item)): item for item in enhanced_items
    }

    result = []
    for item in scraped_data:
        item_hash = hash_item(item)

        # Priority: enhanced > existing > scraped
        if item_hash in enhanced_by_hash:
            # New or changed item that was enhanced
            enhanced = enhanced_by_hash[item_hash].copy()
            enhanced.pop("_hash", None)  # Remove temporary hash field
            result.append(enhanced)
        elif item_hash in existing_by_hash:
            # Unchanged item, keep existing (might have previous LLM enhancements)
            result.append(existing_by_hash[item_hash])
        else:
            # Fallback to scraped (shouldn't normally happen)
            result.append(item)

    return result


def enhance_with_llm(
    changed_items: list[dict], existing_data: list[dict]
) -> list[dict]:
    """Enhance changed items with LLM analysis - only for unstructured content."""
    if not changed_items:
        print("✓ No content changes detected")
        return []

    # Filter items that need LLM enhancement (those without structured data)
    items_needing_llm = [
        item
        for item in changed_items
        if not item.get("model_id") or not item.get("shutdown_date")
    ]

    if not items_needing_llm:
        print("✓ All items have structured data, no LLM analysis needed")
        return changed_items

    print(
        f"Analyzing {len(items_needing_llm)} items with LLM (out of {len(changed_items)} total)..."
    )

    try:
        analyzer = LLMAnalyzer()
        enhanced = analyzer.analyze_batch(items_needing_llm, existing_data)

        # Merge enhanced items back
        enhanced_by_hash = {
            item.get("_hash", hash_item(item)): item for item in enhanced
        }

        result = []
        for item in changed_items:
            item_hash = item.get("_hash", hash_item(item))
            if item_hash in enhanced_by_hash:
                result.append(enhanced_by_hash[item_hash])
            else:
                result.append(item)

        print(f"✓ Enhanced {len(enhanced)} items with LLM")
        return result
    except Exception as e:
        print(f"✗ LLM analysis failed: {e}")
        return changed_items  # Return original items if LLM fails


def save_data(data: list[dict]):
    """Save data to data.json."""
    output_file = Path("data.json")
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n✓ Saved {len(data)} deprecation notices to data.json")


if __name__ == "__main__":
    print("Scraping...")

    # Step 1: Scrape all providers
    scraped_data = scrape_all()
    print(f"\nTotal scraped: {len(scraped_data)} deprecations")

    # Step 2: Load existing data and find changes
    existing_data = read_existing_data()
    changed_items = find_changed_items(scraped_data, existing_data)

    # Step 3: Enhance changed items with LLM
    enhanced_items = enhance_with_llm(changed_items, existing_data)

    # Step 4: Merge all data (enhanced new + existing unchanged)
    final_data = merge_data(scraped_data, existing_data, enhanced_items)

    # Step 5: Save the final result
    save_data(final_data)

    # Step 6: Generate all feed formats
    print("\nGenerating feeds...")

    # Generate RSS feed
    from .rss_gen import create_rss_feed, save_rss_feed

    feed = create_rss_feed(final_data)
    save_rss_feed(feed)

    # Generate JSON feed and API endpoint
    from .json_feed_gen import create_json_feed, save_json_feed, save_raw_api

    json_feed = create_json_feed(final_data)
    save_json_feed(json_feed)
    save_raw_api(final_data)

    print("✓ All feeds generated successfully")
