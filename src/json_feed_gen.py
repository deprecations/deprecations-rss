"""JSON Feed generator for programmatic access to deprecation data."""

import json
from datetime import datetime, timezone
from pathlib import Path


def load_data():
    """Load data from data.json."""
    data_file = Path("data.json")
    if not data_file.exists():
        return []

    with open(data_file) as f:
        return json.load(f)


def create_json_feed(data):
    """Create JSON Feed format for deprecation data."""
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "AI Model Deprecations",
        "home_page_url": "https://deprecations.info/",
        "feed_url": "https://deprecations.info/v1/feed.json",
        "description": "Tracking deprecations and sunsets for AI/ML models across major providers",
        "icon": "https://deprecations.info/favicon.ico",
        "authors": [{"name": "deprecations.info"}],
        "language": "en-US",
        "items": [],
    }

    # Add items for each deprecation notice
    for item_data in data:
        # Create unique ID
        item_id = f"{item_data['provider']}-{item_data.get('model_name', item_data.get('title', ''))}"
        item_id = item_id.replace(" ", "-").replace(":", "").lower()[:100]

        # Build the item
        item = {
            "id": item_id,
            "url": item_data["url"],
            "title": item_data.get("title", f"{item_data['provider']} Deprecation"),
            "content_text": item_data.get("content", ""),
            "date_published": item_data.get(
                "scraped_at", datetime.now(timezone.utc).isoformat()
            ),
        }

        # Add custom deprecation extension with all structured data
        deprecation_data = {
            "provider": item_data.get("provider", "Unknown"),
        }

        # Add all relevant fields if they exist - handle both old and new formats
        if "model_id" in item_data:
            deprecation_data["model_id"] = item_data["model_id"]

        if "model_name" in item_data:
            deprecation_data["model_name"] = item_data["model_name"]
        elif "title" in item_data and ": " in item_data["title"]:
            # Try to extract model name from title (legacy format)
            potential_model = item_data["title"].split(": ", 1)[1]
            if potential_model and "deprecation" not in potential_model.lower():
                deprecation_data["model_name"] = potential_model

        if "shutdown_date" in item_data:
            deprecation_data["shutdown_date"] = item_data["shutdown_date"]

        if "announcement_date" in item_data:
            deprecation_data["announcement_date"] = item_data["announcement_date"]

        # Handle replacement_models
        if "replacement_models" in item_data:
            deprecation_data["replacement_models"] = item_data["replacement_models"]
        elif "suggested_replacement" in item_data:
            deprecation_data["suggested_replacement"] = item_data[
                "suggested_replacement"
            ]

        if "deprecation_reason" in item_data:
            deprecation_data["deprecation_reason"] = item_data["deprecation_reason"]

        if "first_observed" in item_data:
            deprecation_data["first_observed"] = item_data["first_observed"]

        if "last_observed" in item_data:
            deprecation_data["last_observed"] = item_data["last_observed"]

        if "summary" in item_data:
            deprecation_data["summary"] = item_data["summary"]
            # Also use summary as the main content_text if available
            item["content_text"] = item_data["summary"]

        # Add the deprecation data as a custom extension
        item["_deprecation"] = deprecation_data

        # Add tags for filtering
        tags = [item_data.get("provider", "Unknown")]
        if "shutdown_date" in deprecation_data:
            # Add year as a tag for filtering
            try:
                year = deprecation_data["shutdown_date"][:4]
                tags.append(f"shutdown-{year}")
            except Exception:
                pass
        item["tags"] = tags

        feed["items"].append(item)

    return feed


def save_json_feed(feed):
    """Save JSON feed to docs/v1/feed.json."""
    # Create v1 directory
    v1_dir = Path("docs/v1")
    v1_dir.mkdir(parents=True, exist_ok=True)

    # Save to v1 directory
    feed_file = v1_dir / "feed.json"
    with open(feed_file, "w") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)

    print(f"JSON feed saved to {feed_file}")


def save_raw_api(data):
    """Save raw data to docs/v1/deprecations.json."""
    # Create v1 directory
    v1_dir = Path("docs/v1")
    v1_dir.mkdir(parents=True, exist_ok=True)

    # Save raw data
    api_file = v1_dir / "deprecations.json"
    with open(api_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Raw API data saved to {api_file}")


if __name__ == "__main__":
    data = load_data()
    if data:
        # Generate JSON Feed
        feed = create_json_feed(data)
        save_json_feed(feed)
        print(f"Generated JSON feed with {len(data)} items")

        # Save raw API endpoint
        save_raw_api(data)
        print(f"Generated raw API endpoint with {len(data)} items")
    else:
        print("No data found in data.json")
