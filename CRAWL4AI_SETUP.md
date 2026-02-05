# Crawl4AI Setup Guide

## Overview
The web crawling functionality has been switched from Firecrawler to Crawl4AI for better performance and more reliable crawling capabilities.

## Installation

### 1. Install Crawl4AI
```bash
cd /Users/manasithonte/Documents/AqeedAI/backend
pip install crawl4ai
```

### 2. Install Additional Dependencies
Crawl4AI may require additional dependencies:
```bash
pip install playwright
playwright install
```

### 3. Restart Backend
After installation, restart your backend server to load the new dependencies.

## Features

### Crawl4AI Configuration
- **BFS Deep Crawling Strategy**: Crawls up to 2 levels deep
- **Max Pages**: Limited to 50 pages per crawl
- **Score Threshold**: 0.3 minimum score for URLs to be crawled
- **Content Extraction**: Uses LXML scraping strategy for better content extraction
- **Domain Restriction**: Stays within the same domain (include_external=False)

### How It Works
1. **Crawl**: Crawl4AI crawls the specified website using BFS strategy
2. **Store**: Content is stored in Qdrant with embeddings
3. **Search**: Semantic search finds relevant content
4. **Answer**: RAG generates answers using the crawled content

### Fallback Mechanism
If Crawl4AI fails or is not available, the system automatically falls back to Firecrawler.

## Testing

### Test the New Crawling
1. Enable web search in the frontend
2. Enter a specific URL (e.g., `https://www.nvidia.com`)
3. Ask a question about the website
4. Check the logs for Crawl4AI activity

### Expected Logs
```
[RAG] Using Crawl4AI to crawl and index site: https://www.nvidia.com
[Crawl4AI] Starting crawl of https://www.nvidia.com with depth 2
[Crawl4AI] Crawled X pages in total
[Crawl4AI] Stored X pages in Qdrant collection 'crawl4ai_docs_testing'
```

## Benefits of Crawl4AI

1. **Better Content Extraction**: More reliable content extraction from complex websites
2. **Deep Crawling**: Can crawl multiple levels of a website
3. **Async Performance**: Better performance for large crawls
4. **Flexible Configuration**: Configurable crawling strategies and parameters
5. **Local Processing**: No external API dependencies

## Troubleshooting

### Import Errors
If you see import errors for Crawl4AI:
```bash
pip install crawl4ai --upgrade
```

### Playwright Issues
If you encounter Playwright-related errors:
```bash
playwright install chromium
```

### Memory Issues
For large websites, you may need to adjust the `max_pages` parameter in the configuration.

## Configuration Options

You can modify the crawling behavior by adjusting these parameters in `rag_service.py`:

```python
config = CrawlerRunConfig(
    deep_crawl_strategy=BFSDeepCrawlStrategy(
        max_depth=2,           # Crawl depth
        include_external=False, # Stay within domain
        max_pages=50,          # Maximum pages
        score_threshold=0.3    # URL relevance threshold
    ),
    scraping_strategy=LXMLWebScrapingStrategy(),
    verbose=True
)
```

## Next Steps

1. Install Crawl4AI and dependencies
2. Restart the backend
3. Test with a specific website URL
4. Monitor logs for successful crawling
5. Verify that content is properly stored in Qdrant
6. Test question answering with crawled content
