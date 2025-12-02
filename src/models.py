"""Data models for deprecation items."""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone
import hashlib


@dataclass
class DeprecationItem:
    """Represents a single model deprecation notice."""

    provider: str
    model_id: str  # Exact API model name (e.g., "gpt-4-32k-0613")
    model_name: str  # Display name for the model
    announcement_date: str  # ISO date when announced
    shutdown_date: str  # ISO date when model stops working
    replacement_models: Optional[list[str]] = (
        None  # Recommended replacements (can be null)
    )
    deprecation_context: str = ""  # Full announcement text/context
    url: str = ""  # Full URL with anchor (e.g., /docs/deprecations#2025-04-28)
    content_hash: str = ""  # Hash of raw content (for LLM deduplication)
    scraped_at: str = ""  # ISO timestamp

    def __post_init__(self):
        """Set defaults after initialization."""
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()

        if not self.content_hash:
            # Hash based on unique fields for this deprecation
            unique_content = f"{self.provider}|{self.model_id}|{self.shutdown_date}|{self.announcement_date}"
            self.content_hash = self._compute_hash(unique_content)

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute a hash for content deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "announcement_date": self.announcement_date,
            "shutdown_date": self.shutdown_date,
            "replacement_models": self.replacement_models,
            "deprecation_context": self.deprecation_context,
            "url": self.url,
            "content_hash": self.content_hash,
            "scraped_at": self.scraped_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeprecationItem":
        """Create instance from dictionary."""
        # Handle backward compatibility: convert old replacement_model string to list
        replacement_models = data.get("replacement_models")
        if replacement_models is None and "replacement_model" in data:
            old_value = data.get("replacement_model")
            if old_value:
                # Split on "or" to handle cases like "gpt-image-1orgpt-image-1-mini"
                # This handles the concatenated format from the old data
                if "or" in old_value and " " not in old_value.split("or")[0] and " " not in old_value.split("or")[-1]:
                    # Looks like concatenated format: "model1ormodel2"
                    replacement_models = [m for m in old_value.split("or") if m]
                else:
                    # Single model or already properly formatted
                    replacement_models = [old_value]
            else:
                replacement_models = None

        return cls(
            provider=data.get("provider", ""),
            model_id=data.get("model_id", ""),
            model_name=data.get("model_name", ""),
            announcement_date=data.get("announcement_date", ""),
            shutdown_date=data.get("shutdown_date", ""),
            replacement_models=replacement_models,
            deprecation_context=data.get("deprecation_context", ""),
            url=data.get("url", ""),
            content_hash=data.get("content_hash", ""),
            scraped_at=data.get("scraped_at", ""),
        )

    def matches_previous(self, other: "DeprecationItem") -> bool:
        """Check if this item matches a previous version (same model, same content)."""
        return (
            self.provider == other.provider
            and self.model_id == other.model_id
            and self.content_hash == other.content_hash
        )
