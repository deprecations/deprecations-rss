"""Provider registry and source page metadata."""

from .scrapers.openai_scraper import OpenAIScraper
from .scrapers.anthropic_scraper import AnthropicScraper
from .scrapers.google_scraper import GoogleScraper
from .scrapers.google_vertex_scraper import GoogleVertexScraper
from .scrapers.aws_bedrock_scraper import AWSBedrockScraper
from .scrapers.cohere_scraper import CohereScraper
from .scrapers.xai_scraper import XAIScraper
from .scrapers.azure_foundry_scraper import AzureFoundryScraper

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

TRACKED_PROVIDER_PAGES = [
    {"provider": OpenAIScraper.provider_name, "label": "OpenAI Deprecations", "url": OpenAIScraper.url},
    {
        "provider": AnthropicScraper.provider_name,
        "label": "Anthropic Model Deprecations",
        "url": AnthropicScraper.url,
    },
    {"provider": GoogleScraper.provider_name, "label": "Google AI/Gemini Deprecations", "url": GoogleScraper.url},
    {
        "provider": GoogleVertexScraper.provider_name,
        "label": "Google Vertex AI Deprecations",
        "url": GoogleVertexScraper.url,
    },
    {
        "provider": AWSBedrockScraper.provider_name,
        "label": "AWS Bedrock Model Lifecycle",
        "url": AWSBedrockScraper.url,
    },
    {"provider": CohereScraper.provider_name, "label": "Cohere Deprecations", "url": CohereScraper.url},
    {"provider": XAIScraper.provider_name, "label": "xAI Models", "url": XAIScraper.url},
    {"provider": AzureFoundryScraper.provider_name, "label": "Azure AI Foundry Retirements", "url": AzureFoundryScraper.url},
]
