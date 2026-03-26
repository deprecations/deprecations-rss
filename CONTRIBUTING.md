# Contributing to Deprecations RSS

## Found a Bug?

If a provider changed their page format or you found any other issue:
1. Open an issue with details
2. Include the provider name and error message
3. PRs welcome!

## Adding a New Provider

1. Create a new scraper class in `providers.py` extending `BaseScraper`
2. Add it to the `SCRAPERS` list
3. Test with `uv run python main.py`

## Development Setup

```bash
# Install dependencies
uv sync

# Run the scraper
uv run python main.py
```

## Testing

The scraper should complete in under 60 seconds and produce valid JSON in `data.json`.