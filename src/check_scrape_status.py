"""Fail the scrape workflow after generated data has been committed if needed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """Check provider-level scrape failures recorded by src.main."""
    if os.environ.get("SCRAPE_OUTCOME") != "success":
        sys.exit("Scrape step failed")

    status_file = Path(os.environ.get("SCRAPE_STATUS_FILE", ".scrape-status.json"))
    failures = json.loads(status_file.read_text()).get("provider_failures", [])
    if not failures:
        print("No provider failures recorded")
        return 0

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        lines = ["## Provider scrape failures", ""]
        for failure in failures:
            lines.append(
                f"- **{failure.get('provider', 'Unknown')}**: {failure.get('message', '')}"
            )
        Path(summary_file).write_text("\n".join(lines) + "\n", encoding="utf-8")

    sys.exit(f"{len(failures)} provider scrape failure(s) recorded")


if __name__ == "__main__":
    raise SystemExit(main())
