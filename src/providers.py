"""Simple deprecation scrapers for AI providers - now with individual deprecation parsing."""

# Import the new enhanced scrapers
from .scrapers.openai_scraper import OpenAIScraper
from .scrapers.anthropic_scraper import AnthropicScraper
from .scrapers.google_scraper import GoogleScraper
from .scrapers.google_vertex_scraper import GoogleVertexScraper
from .scrapers.aws_bedrock_scraper import AWSBedrockScraper
from .scrapers.cohere_scraper import CohereScraper
from .scrapers.xai_scraper import XAIScraper
from .scrapers.azure_foundry_scraper import AzureFoundryScraper

# List of all scrapers - using the new enhanced versions
SCRAPERS = [
    OpenAIScraper,
    AnthropicScraper,
    GoogleScraper,
    GoogleVertexScraper,
    AWSBedrockScraper,
    CohereScraper,
    XAIScraper,
    AzureFoundryScraper,
]
