"""Fireworks AI serverless model deprecations scraper.

Fireworks has no dedicated deprecations page. It announces serverless model
retirements as entries in its changelog, which is also published as markdown.
Each entry looks like::

    **2026-09-12**

    Inference

    # Upcoming Serverless deprecation: older DeepSeek, GLM, Muse, and Kimi models

    Several older Serverless models will be decommissioned on **September 25, 2026** ...

    * **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** — migrate to ...

A row means "this model ID stops working on serverless", so the scraper only
emits a row when a notice retires the whole model. Bullets that retire one
variant or endpoint of a model that stays available (a Fast/Turbo mode, a US
endpoint) produce no row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


ENTRY_DATE_RE = re.compile(r"^\*\*(\d{4}-\d{2}-\d{2})\*\*\s*$")
MODEL_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(https://app\.fireworks\.ai/models/fireworks/([a-z0-9][a-z0-9._-]*)\)"
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
LONG_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s*\d{4}\b"
)
# "* <subject> — <action>", where the action tells users where to go next.
MIGRATION_BULLET_RE = re.compile(
    r"^\*\s+(?P<subject>.+?)\s+[—–]\s+(?P<action>(?:migrate|move|switch|use)\b.*)$",
    re.IGNORECASE,
)
# The subject of a whole-model bullet is exactly one bold model link.
LINKED_SUBJECT_RE = re.compile(
    r"^\*\*\[(?P<name>[^\]]+)\]\(https://app\.fireworks\.ai/models/fireworks/"
    r"(?P<slug>[a-z0-9][a-z0-9._-]*)\)\*\*$"
)
# Prose notices such as "**MiniMax M2.5** is deprecated from serverless."
PROSE_SUBJECTS_RE = re.compile(
    r"^(?P<subjects>\*\*[^*]+\*\*(?:(?:,\s*|,?\s+and\s+)\*\*[^*]+\*\*)*)"
    r"\s+(?:is|are)\s+(?:deprecated|decommissioned|retired)\b",
    re.IGNORECASE,
)
PARTIAL_RETIREMENT_RE = re.compile(
    r"\bendpoints?\s+only\b|\bremains?\s+available\b", re.IGNORECASE
)


@dataclass
class ChangelogEntry:
    """One dated entry of the Fireworks changelog."""

    date: str
    title: str
    body: str


class FireworksScraper(EnhancedBaseScraper):
    """Scraper for Fireworks AI serverless model deprecations."""

    provider_name = "Fireworks AI"
    url = "https://docs.fireworks.ai/updates/changelog"
    markdown_url = "https://docs.fireworks.ai/updates/changelog.md"
    model_id_prefix = "accounts/fireworks/models/"
    requires_playwright = False
    require_shutdown_dates = True

    def get_source_url(self) -> str:
        """Prefer the changelog's markdown source for deterministic parsing."""
        return self.markdown_url

    def scrape(self) -> List[DeprecationItem]:
        """Fetch the changelog markdown and return serverless model retirements."""
        content = self.fetch_html(self.get_source_url())
        return self.extract_structured_deprecations(content)

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract one row per retired model from serverless deprecation entries."""
        items: list[DeprecationItem] = []
        for entry in self._split_entries(html):
            if not self._is_serverless_deprecation(entry.title):
                continue
            items.extend(self._extract_entry_items(entry))
        return self._dedupe_items(items)

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """All Fireworks rows come from dated changelog entries."""
        return []

    def _split_entries(self, content: str) -> list[ChangelogEntry]:
        """Split the changelog into dated entries with a title and a body."""
        entries: list[ChangelogEntry] = []
        current_date = ""
        current_lines: list[str] = []

        def flush() -> None:
            if not current_date:
                return
            title = ""
            body_lines: list[str] = []
            for line in current_lines:
                if not title and line.startswith("# "):
                    title = line[2:].strip()
                    continue
                if title:
                    body_lines.append(line)
            if title:
                entries.append(
                    ChangelogEntry(
                        date=current_date,
                        title=title,
                        body="\n".join(body_lines).strip(),
                    )
                )

        for line in content.splitlines():
            match = ENTRY_DATE_RE.match(line.strip())
            if match:
                flush()
                current_date = match.group(1)
                current_lines = []
                continue
            current_lines.append(line.rstrip())
        flush()
        return entries

    def _is_serverless_deprecation(self, title: str) -> bool:
        """Keep serverless inference retirements, not training or feature notices."""
        lowered = title.lower()
        if "serverless" not in lowered or "training" in lowered:
            return False
        return bool(re.search(r"deprecat|decommission|retire|removed|sunset", lowered))

    def _extract_entry_items(self, entry: ChangelogEntry) -> list[DeprecationItem]:
        """Turn one serverless deprecation entry into model rows."""
        lines = entry.body.splitlines()
        intro = self._intro(lines)
        shutdown_date = self._shutdown_date(intro, entry.date)

        bullets = [
            match
            for line in lines
            if (match := MIGRATION_BULLET_RE.match(line.strip())) is not None
        ]

        items: list[DeprecationItem] = []
        if bullets:
            for match in bullets:
                item = self._item_from_bullet(entry, intro, shutdown_date, match)
                if item is not None:
                    items.append(item)
            return items

        # Short notices name the retired models in prose, with no bullet list.
        for paragraph in self._paragraphs(lines):
            prose = PROSE_SUBJECTS_RE.match(paragraph)
            if not prose:
                continue
            if PARTIAL_RETIREMENT_RE.search(paragraph):
                continue
            for subject in re.findall(r"\*\*[^*]+\*\*", prose.group("subjects")):
                model_id = self._subject_model_id(subject)
                if not model_id:
                    continue
                replacements = self._replacements(paragraph, model_id)
                items.append(
                    self._build_item(
                        entry,
                        model_id,
                        shutdown_date,
                        replacements,
                        self._clean_markdown(paragraph),
                    )
                )
        return items

    def _item_from_bullet(
        self,
        entry: ChangelogEntry,
        intro: str,
        shutdown_date: str,
        match: re.Match[str],
    ) -> DeprecationItem | None:
        """Build a row from a migration bullet, or None when it is not a whole-model retirement."""
        bullet = match.group(0)
        if PARTIAL_RETIREMENT_RE.search(bullet):
            return None

        # "**[GLM 5.2](...)**, including **GLM 5.2 Fast** ..." retires GLM 5.2;
        # the listed variants go with it and are not separate model IDs.
        subject = re.split(r",?\s+including\s+", match.group("subject"), maxsplit=1)[0]
        model_id = self._subject_model_id(subject.strip())
        if not model_id:
            return None

        replacement_links = self._linked_model_ids(match.group("action"))
        if model_id in replacement_links:
            # The replacement is the same model (for example a Fast mode moving to
            # standard mode), so the model ID itself keeps working.
            return None

        replacements = self._replacements(match.group("action"), model_id)
        context = self._clean_markdown(f"{intro}\n\n{bullet.lstrip('* ').strip()}")
        return self._build_item(entry, model_id, shutdown_date, replacements, context)

    def _subject_model_id(self, subject: str) -> str:
        """Return the model ID for a bold linked subject, or "" otherwise.

        Subjects without a model link (for example "**Llama 3.3 70B Instruct**")
        are skipped: the display name is not a model ID, and guessing a slug is
        often wrong. Qualified subjects ("... (US endpoint only)") are skipped too.
        """
        linked = LINKED_SUBJECT_RE.match(subject)
        if linked:
            return f"{self.model_id_prefix}{linked.group('slug')}"
        return ""

    def _linked_model_ids(self, text: str) -> list[str]:
        """Return the full model IDs of every Fireworks model link in the text."""
        model_ids: list[str] = []
        for _name, slug in MODEL_LINK_RE.findall(text):
            model_id = f"{self.model_id_prefix}{slug}"
            if model_id not in model_ids:
                model_ids.append(model_id)
        return model_ids

    def _replacements(self, text: str, model_id: str) -> list[str] | None:
        """Replacements come from model links only and never name the row's own model."""
        replacements = [
            linked for linked in self._linked_model_ids(text) if linked != model_id
        ]
        return replacements or None

    def _intro(self, lines: list[str]) -> str:
        """Return the first paragraph of an entry body."""
        paragraphs = self._paragraphs(lines)
        return paragraphs[0] if paragraphs else ""

    def _paragraphs(self, lines: list[str]) -> list[str]:
        """Group non-heading, non-bullet lines into paragraphs."""
        paragraphs: list[str] = []
        current: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "* ", "- ", ">")):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                continue
            current.append(stripped)
        if current:
            paragraphs.append(" ".join(current))
        return paragraphs

    def _shutdown_date(self, intro: str, entry_date: str) -> str:
        """Use the date named in the notice, or the entry date for immediate notices."""
        match = LONG_DATE_RE.search(intro.replace("**", ""))
        if match:
            parsed = self.parse_date(match.group(0))
            if parsed:
                return parsed
        return entry_date

    def _clean_markdown(self, text: str) -> str:
        """Strip links and bold markers so the context reads as plain text."""
        cleaned = MARKDOWN_LINK_RE.sub(r"\1", text)
        cleaned = cleaned.replace("**", "")
        return re.sub(r"[ \t]+", " ", cleaned).strip()

    def _build_item(
        self,
        entry: ChangelogEntry,
        model_id: str,
        shutdown_date: str,
        replacements: list[str] | None,
        context: str,
    ) -> DeprecationItem:
        return DeprecationItem(
            provider=self.provider_name,
            model_id=model_id,
            announcement_date=entry.date,
            shutdown_date=shutdown_date,
            deprecation_date=entry.date,
            replacement_models=replacements,
            deprecation_context=f"{entry.title}\n\n{context}".strip(),
            url=self.url,
        )

    def _dedupe_items(self, items: list[DeprecationItem]) -> list[DeprecationItem]:
        """Keep one row per model.

        An "Upcoming" notice and its later "now in effect" notice name the same
        models. The newest notice carries the current shutdown date and
        replacements; the oldest notice's date is when Fireworks first announced it.
        """
        by_model: dict[str, DeprecationItem] = {}
        for item in items:
            existing = by_model.get(item.model_id)
            if existing is None:
                by_model[item.model_id] = item
                continue
            newest, oldest = (
                (item, existing)
                if item.deprecation_date >= existing.deprecation_date
                else (existing, item)
            )
            by_model[item.model_id] = DeprecationItem(
                provider=newest.provider,
                model_id=newest.model_id,
                announcement_date=oldest.announcement_date,
                shutdown_date=newest.shutdown_date,
                deprecation_date=oldest.deprecation_date,
                replacement_models=newest.replacement_models,
                deprecation_context=newest.deprecation_context,
                url=newest.url,
            )
        return list(by_model.values())
