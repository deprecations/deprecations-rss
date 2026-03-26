"""Cache manager for fetched provider pages, including HTML and Markdown."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class CacheManager:
    """Manages cached provider content with TTL support."""

    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.html_dir = self.cache_dir / "html"
        self.markdown_dir = self.cache_dir / "markdown"
        self.manifest_path = self.cache_dir / "cache_manifest.json"
        self.ttl_hours = ttl_hours

        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        """Load the cache manifest or create an empty one."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_manifest(self):
        """Save the manifest to disk."""
        with open(self.manifest_path, "w", encoding="utf-8") as file:
            json.dump(self.manifest, file, indent=2)

    def _get_cache_key(self, provider: str, url: str) -> str:
        """Generate a cache key from provider and URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{provider}_{url_hash}"

    def _is_markdown_url(self, url: str) -> bool:
        """Return True when the source URL points to markdown content."""
        return url.lower().split("?", 1)[0].endswith(".md")

    def _get_cache_path(self, cache_key: str, url: str) -> Path:
        """Get the file path for a cache entry based on URL type."""
        if self._is_markdown_url(url):
            return self.markdown_dir / f"{cache_key}.md"
        return self.html_dir / f"{cache_key}.html"

    def _get_manifest_cache_path(self, cache_key: str, url: str) -> Path:
        """Resolve the cache path, preferring the manifest entry when present."""
        entry = self.manifest.get(cache_key)
        if entry and entry.get("file"):
            return self.cache_dir / entry["file"]
        return self._get_cache_path(cache_key, url)

    def is_cached(self, provider: str, url: str) -> bool:
        """Check if valid cached content exists."""
        cache_key = self._get_cache_key(provider, url)
        if cache_key not in self.manifest:
            return False

        entry = self.manifest[cache_key]
        cached_at = datetime.fromisoformat(entry["cached_at"])
        expires_at = cached_at + timedelta(hours=entry.get("ttl_hours", self.ttl_hours))
        if datetime.now(timezone.utc) > expires_at:
            return False

        return self._get_manifest_cache_path(cache_key, url).exists()

    def get_cached_html(self, provider: str, url: str) -> Optional[str]:
        """Get cached provider content if available and not expired."""
        if not self.is_cached(provider, url):
            return None

        cache_key = self._get_cache_key(provider, url)
        cache_path = self._get_manifest_cache_path(cache_key, url)

        try:
            with open(cache_path, "r", encoding="utf-8") as file:
                return file.read()
        except IOError:
            if cache_key in self.manifest:
                del self.manifest[cache_key]
                self._save_manifest()
            return None

    def save_html(self, provider: str, url: str, html: str):
        """Save provider content to cache."""
        cache_key = self._get_cache_key(provider, url)
        cache_path = self._get_cache_path(cache_key, url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, "w", encoding="utf-8") as file:
            file.write(html)

        self.manifest[cache_key] = {
            "provider": provider,
            "url": url,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "ttl_hours": self.ttl_hours,
            "file": str(cache_path.relative_to(self.cache_dir)),
        }
        self._save_manifest()

    def clear_expired(self):
        """Remove expired cache entries."""
        expired_keys = []

        for cache_key, entry in self.manifest.items():
            cached_at = datetime.fromisoformat(entry["cached_at"])
            expires_at = cached_at + timedelta(
                hours=entry.get("ttl_hours", self.ttl_hours)
            )
            if datetime.now(timezone.utc) > expires_at:
                expired_keys.append(cache_key)
                cache_path = self.cache_dir / entry.get("file", "")
                if cache_path.exists():
                    cache_path.unlink()

        for key in expired_keys:
            del self.manifest[key]

        if expired_keys:
            self._save_manifest()
            print(f"Cleared {len(expired_keys)} expired cache entries")

    def clear_all(self):
        """Clear all cache entries."""
        for cache_file in list(self.html_dir.glob("*.html")) + list(
            self.markdown_dir.glob("*.md")
        ):
            cache_file.unlink()

        self.manifest = {}
        self._save_manifest()
        print("Cleared all cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.manifest)
        valid_entries = sum(
            1
            for provider, url in [
                (entry["provider"], entry["url"]) for entry in self.manifest.values()
            ]
            if self.is_cached(provider, url)
        )

        total_size = 0
        for cache_key, entry in self.manifest.items():
            path = self._get_manifest_cache_path(cache_key, entry["url"])
            if path.exists():
                total_size += path.stat().st_size

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": total_entries - valid_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
        }
