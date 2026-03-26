"""RSS feed generator with structured data in description."""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom


def load_data():
    """Load data from data.json."""
    data_file = Path("data.json")
    if not data_file.exists():
        return []

    with open(data_file) as f:
        return json.load(f)


def create_rss_feed(data):
    """Create RSS feed with structured data in description field."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "AI Model Deprecations"
    ET.SubElement(channel, "link").text = "https://deprecations.info/"
    ET.SubElement(
        channel, "description"
    ).text = "RSS feed tracking deprecations across major AI providers"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    for item_data in data:
        item = ET.SubElement(channel, "item")

        model_id = item_data.get("model_id", "")
        title = (
            f"{item_data['provider']}: {model_id}"
            if model_id
            else f"{item_data['provider']} Deprecation"
        )

        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = item_data["url"]

        description_parts = []
        description_parts.append(f"Provider: {item_data.get('provider', 'Unknown')}")

        if model_id:
            description_parts.append(f"Model ID: {model_id}")

        if item_data.get("shutdown_date"):
            description_parts.append(f"Shutdown Date: {item_data['shutdown_date']}")
        elif item_data.get("announcement_date"):
            description_parts.append(
                f"Announcement Date: {item_data['announcement_date']}"
            )

        if item_data.get("suggested_replacement") and not item_data[
            "suggested_replacement"
        ].startswith("<"):
            description_parts.append(
                f"Replacement: {item_data['suggested_replacement']}"
            )

        if item_data.get("deprecation_reason") and not item_data[
            "deprecation_reason"
        ].startswith("<"):
            description_parts.append(f"Reason: {item_data['deprecation_reason']}")

        if "first_observed" in item_data:
            description_parts.append(f"First Observed: {item_data['first_observed']}")

        if "last_observed" in item_data:
            description_parts.append(f"Last Observed: {item_data['last_observed']}")

        description_parts.append("")

        if "summary" in item_data:
            description_parts.append(item_data["summary"])
        elif item_data.get("deprecation_context"):
            context = item_data["deprecation_context"][:500]
            if len(item_data["deprecation_context"]) > 500:
                context += "..."
            description_parts.append(context)
        else:
            original_content = item_data.get("raw_content") or item_data.get(
                "content", ""
            )
            if original_content:
                description_parts.append(original_content)

        ET.SubElement(item, "description").text = "\n".join(description_parts)

        if "scraped_at" in item_data:
            ET.SubElement(item, "pubDate").text = datetime.fromisoformat(
                item_data["scraped_at"]
            ).strftime("%a, %d %b %Y %H:%M:%S GMT")
        else:
            ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

        guid_parts = [item_data["provider"]]
        if model_id:
            guid_parts.append(model_id)
        elif "title" in item_data:
            guid_parts.append(item_data["title"])
        if item_data.get("shutdown_date"):
            guid_parts.append(item_data["shutdown_date"])

        content_hash = hashlib.sha256(
            str(item_data.get("content", "")).encode()
        ).hexdigest()[:8]
        guid_parts.append(content_hash)

        guid = (
            "-".join(str(part) for part in guid_parts)
            .replace(" ", "_")
            .replace(":", "")[:100]
        )
        ET.SubElement(item, "guid", isPermaLink="false").text = guid

    xml_str = ET.tostring(rss, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")


def save_rss_feed(feed_content):
    """Save RSS feed to docs/v1/feed.xml."""
    feed_dir = Path("docs/v1")
    feed_dir.mkdir(parents=True, exist_ok=True)

    feed_file = feed_dir / "feed.xml"
    with open(feed_file, "w") as f:
        f.write(feed_content)

    print(f"RSS feed saved to {feed_file}")


if __name__ == "__main__":
    data = load_data()
    if data:
        feed = create_rss_feed(data)
        save_rss_feed(feed)
        print(f"Generated RSS feed with {len(data)} items")
    else:
        print("No data found in data.json")
