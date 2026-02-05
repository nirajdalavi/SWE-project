# services/rag_service.py
import os
import json
import hashlib
import requests
import re
import concurrent.futures
import time
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
import logging
import collections  # Import collections for defaultdict
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

from services.helper_service import extract_criteria_from_jsonl

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENROUTER_MODEL = "qwen/qwq-32b"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
model = SentenceTransformer("all-MiniLM-L6-v2")

def call_openrouter(prompt: str, model_name: str = OPENROUTER_MODEL, temperature: float = 0.0) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Strictly output only the JSON object. "
                    "Do not include any extra commentary, no introduction, no explanation, no closing statement. "
                    "Your reply MUST start with '{' and end with '}'."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    try:
        logger.info(f"[OpenRouter] Sending request to model: {model_name}, prompt length: {len(prompt)}")
        start_request_time = time.time()
        resp = requests.post(url, headers=headers, json=data, timeout=600)
        resp.raise_for_status()
        reply_text = resp.json()["choices"][0]["message"]["content"]
        logger.info(f"[OpenRouter] Response received in {time.time() - start_request_time:.2f}s.")
        openrouter_elapsed = time.time() - start_request_time
        match = re.search(r'\{.*\}', reply_text, re.DOTALL)
        if match:
            return match.group(0), openrouter_elapsed
        return reply_text, openrouter_elapsed
    except requests.exceptions.Timeout:
        logger.error(f"[OpenRouter] Request to {model_name} timed out after 600 seconds.")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"[OpenRouter] Request to {model_name} failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"[OpenRouter] Response status: {e.response.status_code}, content: {e.response.text}")
        raise

def call_chatgpt(prompt: str, model_name: str = "gpt-4o", temperature: float = 0.0) -> str:
    """Makes a call to the ChatGPT API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    try:
        logger.info(f"[ChatGPT] Sending request to model: {model_name}, prompt length: {len(prompt)}")
        start_request_time = time.time()
        resp = requests.post(url, headers=headers, json=data, timeout=600)
        resp.raise_for_status()
        reply_text = resp.json()["choices"][0]["message"]["content"]
        logger.info(f"[ChatGPT] Response received in {time.time() - start_request_time:.2f}s.")
        chatgpt_elapsed = time.time() - start_request_time
        return reply_text, chatgpt_elapsed
    except requests.exceptions.Timeout:
        logger.error(f"[ChatGPT] Request to {model_name} timed out after 600 seconds.")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"[ChatGPT] Request to {model_name} failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"[ChatGPT] Response status: {e.response.status_code}, content: {e.response.text}")
        raise


# from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import os
import re

# --- URL normalization and Qdrant collection helper ---
def ensure_url_has_scheme(url: str) -> str:
    if url and not url.startswith(("http://", "https://")):
        return "https://" + url.lstrip("/")
    return url

def resolve_brand_to_url(brand_input: str) -> str:
    """
    Convert brand names to their official website URLs.
    If input is already a URL, return as is.
    """
    # If it's already a URL, return normalized
    if brand_input.startswith(("http://", "https://", "www.")):
        return ensure_url_has_scheme(brand_input)
    
    # Brand name to URL mapping
    brand_urls = {
        "apple": "https://www.apple.com",
        "microsoft": "https://www.microsoft.com",
        "google": "https://www.google.com",
        "amazon": "https://www.amazon.com",
        "meta": "https://www.meta.com",
        "facebook": "https://www.facebook.com",
        "netflix": "https://www.netflix.com",
        "spotify": "https://www.spotify.com",
        "nvidia": "https://www.nvidia.com",
        "intel": "https://www.intel.com",
        "amd": "https://www.amd.com",
        "tesla": "https://www.tesla.com",
        "openai": "https://www.openai.com",
        "anthropic": "https://www.anthropic.com",
        "github": "https://www.github.com",
        "stackoverflow": "https://www.stackoverflow.com",
        "reddit": "https://www.reddit.com",
        "youtube": "https://www.youtube.com",
        "twitter": "https://www.twitter.com",
        "x": "https://www.x.com",
        "linkedin": "https://www.linkedin.com",
        "instagram": "https://www.instagram.com",
        "tiktok": "https://www.tiktok.com",
        "discord": "https://www.discord.com",
        "slack": "https://www.slack.com",
        "zoom": "https://www.zoom.us",
        "salesforce": "https://www.salesforce.com",
        "oracle": "https://www.oracle.com",
        "ibm": "https://www.ibm.com",
        "adobe": "https://www.adobe.com",
        "dropbox": "https://www.dropbox.com",
        "airbnb": "https://www.airbnb.com",
        "uber": "https://www.uber.com",
        "lyft": "https://www.lyft.com",
        "paypal": "https://www.paypal.com",
        "stripe": "https://www.stripe.com",
        "shopify": "https://www.shopify.com",
        "wordpress": "https://www.wordpress.com",
        "squarespace": "https://www.squarespace.com",
        "wix": "https://www.wix.com"
    }
    
    # Normalize input (lowercase, strip spaces)
    normalized_input = brand_input.lower().strip()
    
    # Check for exact match
    if normalized_input in brand_urls:
        return brand_urls[normalized_input]
    
    # Check for partial matches (e.g., "apple.com" -> "apple")
    for brand, url in brand_urls.items():
        if brand in normalized_input or normalized_input in brand:
            return url
    
    # If no match found, treat as domain and add https://
    return ensure_url_has_scheme(brand_input)

def ensure_qdrant_collection(name: str):
    try:
        client.get_collection(collection_name=name)
    except Exception:
        logger.info(f"[Qdrant] Creating collection {name}")
        client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(size=model.get_sentence_embedding_dimension(), distance=Distance.COSINE)
        )



# --- Qdrant Upsert Helper for Crawled Pages ---
def upsert_crawled_pages_to_qdrant(pages: list[dict], collection_name: str, batch_size: int = 50):
    """
    Upserts crawled page documents into a Qdrant collection for embedding search.

    Args:
        pages (list[dict]): List of page documents with keys: url, title, content, metadata.
        collection_name (str): The Qdrant collection name.
        batch_size (int): Number of points to upsert per batch.

    Returns:
        int: Total number of points upserted.
    """
    if not pages:
        logger.warning("[Qdrant] No pages to upsert.")
        return 0

    # Ensure collection exists
    ensure_qdrant_collection(collection_name)

    total_upserts = 0
    batch = []

    for i, page in enumerate(pages, start=1):
        content = page.get("content", "")
        if not content:
            continue
        embedding = model.encode(content).tolist()
        point = PointStruct(
            id=hashlib.md5((ensure_url_has_scheme(page.get("url", "")) + content[:200]).encode()).hexdigest(),
            vector=embedding,
            payload={
                "text": content,
                "url": ensure_url_has_scheme(page.get("url", "")),
                "title": page.get("title", ""),
                "metadata": page.get("metadata", {})
            }
        )
        batch.append(point)

        if len(batch) >= batch_size:
            client.upsert(collection_name=collection_name, points=batch)
            total_upserts += len(batch)
            batch = []

    if batch:
        client.upsert(collection_name=collection_name, points=batch)
        total_upserts += len(batch)

    logger.info(f"[Qdrant] Upserted {total_upserts} pages into collection '{collection_name}'.")
    return total_upserts

def extract_relevant_sections(content: str, query: str, max_sections: int = 3):
    """Extract relevant sections from content based on the query."""
    if not content or not query:
        return []
    
    # Split content into sections (paragraphs, headings, etc.)
    sections = []
    
    # Split by double newlines (paragraphs)
    paragraphs = content.split('\n\n')
    
    # Also split by headings (lines starting with #)
    for paragraph in paragraphs:
        if paragraph.strip():
            # Check if this section is relevant to the query
            relevance_score = calculate_relevance(paragraph, query)
            if relevance_score > 0.3:  # Threshold for relevance
                sections.append({
                    "text": paragraph.strip()[:500] + "..." if len(paragraph.strip()) > 500 else paragraph.strip(),
                    "relevance_score": relevance_score,
                    "section_type": "paragraph"
                })
    
    # Sort by relevance and return top sections
    sections.sort(key=lambda x: x['relevance_score'], reverse=True)
    return sections[:max_sections]

def calculate_relevance(text: str, query: str):
    """Calculate relevance score between text and query."""
    if not text or not query:
        return 0
    
    text_lower = text.lower()
    query_lower = query.lower()
    
    # Split query into words
    query_words = query_lower.split()
    
    # Count word matches
    matches = 0
    for word in query_words:
        if word in text_lower:
            matches += 1
    
    # Calculate relevance score
    if len(query_words) == 0:
        return 0
    
    return matches / len(query_words)



        

def scrape_website_fallback(url: str, query: str):
    """Fallback scraping method using BeautifulSoup."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Get title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else url
        
        # Limit text length to avoid token limits
        if len(text) > 3000:
            text = text[:3000] + "..."
        
        return {
            "title": title_text,
            "snippet": text,
            "link": url
        }
    except Exception as e:
        logger.error(f"[WebsiteScraping] Failed to scrape {url}: {e}")
        return {
            "title": f"Error scraping {url}",
            "snippet": f"Failed to scrape website: {str(e)}",
            "link": url
        }


def qa_prompt_template(context: str, query: str, response_size: str, response_type: str, file_names: list[str] = None) -> str:
    response_instructions = {
        "short": "Respond in 1-2 sentences.",
        "medium": "Respond in 3-5 sentences.",
        "long": "Respond in detailed paragraphs."
    }
    formatting = {
        "sentence": "Respond in a natural, continuous paragraph format.",
        "points": "Respond as bullet points. Each point must start on a new line using HTML <br> tag and NOT \n(newline tags)."
    }

    query_instruction = f"""
IF the query is just ONE-TWO WORDS, consider it as a criteria and judge all contracts based on this criteria. Strictly mention all the contracts and tell about the query in this format example.
contract document 1 : information of {query} in that context
contract document 2 : information of {query}  in that context
Be concise and accurate. Do not explain your reasoning. One sentence per contract.
### Contract Documents:
{'<br>'.join(file_names) if file_names else 'Not specified'}
print(f"[DEBUG] File names in prompt: {file_names}")

""" if len(query.strip()) <= 18 else ""

    return f"""
You are a helpful assistant specialized in contract analysis. Use the provided context to answer the following question strictly based on the information provided. Do not hallucinate or invent any facts. If the answer is not available, respond with "Information not available".

Your response must be in strict JSON format. The answer should be provided under a single top-level key named "answer". For example: {{"answer": "Your answer goes here."}} If the answer is a list of items, provide it as a JSON array under the "answer" key.

{response_instructions.get(response_size, '')}
{formatting.get(response_type, '')}

### Context:
{context}

### Question:
{query}
{query_instruction}



### Answer:
"""


def answer_question_with_rag(query: str, collection_name: str, response_size: str = "short", response_type: str = "sentence", top_k=3, compare_chatgpt: bool = False, share_data_with_chatgpt: bool = False, use_web: bool = False, specific_url: str = ""):
    start_func_time = time.time()
    vector = model.encode(query).tolist()

    if use_web:
        if specific_url and specific_url.strip():
            logger.info(f"[RAG] Using Crawl4AI to crawl and index site: {specific_url}")
            
            # Use Crawl4AI for web crawling
            if CRAWL4AI_AVAILABLE:
                try:
                    # Use workspace name directly for web crawling collection
                    workspace_name = collection_name.replace("contract_docs_", "")
                    collection_name_web = workspace_name
                    
                    # Resolve brand name to URL if needed
                    resolved_url = resolve_brand_to_url(specific_url)
                    logger.info(f"[RAG] Resolved '{specific_url}' to '{resolved_url}'")
                    
                    # Check if collection already has content
                    collection_exists = False
                    existing_chunks_count = 0
                    try:
                        # Check if collection exists and has content
                        collection_info = client.get_collection(collection_name_web)
                        if collection_info.points_count > 0:
                            collection_exists = True
                            existing_chunks_count = collection_info.points_count
                            logger.info(f"[RAG] Found existing collection '{collection_name_web}' with {existing_chunks_count} chunks")
                    except Exception:
                        logger.info(f"[RAG] Collection '{collection_name_web}' doesn't exist or is empty")
                    
                    # Use existing collection if available, otherwise crawl
                    if collection_exists:
                        logger.info(f"[RAG] Using existing crawled content from collection '{collection_name_web}'")
                        # Perform semantic search on existing content
                        query_vector = model.encode(query).tolist()
                        hits = client.search(collection_name=collection_name_web, query_vector=query_vector, limit=top_k)
                        context = "\n---\n".join([hit.payload["text"] for hit in hits])
                        
                        # Create sources from existing content
                        sources = []
                        crawled_pages = {}  # Track unique pages
                        
                        for hit in hits:
                            page_url = hit.payload["url"]
                            page_title = hit.payload.get("title", page_url)
                            chunk_index = hit.payload.get("chunk_index", 0)
                            total_chunks = hit.payload.get("total_chunks", 1)
                            
                            # Normalize URL to avoid duplicates
                            from urllib.parse import urlparse, urlunparse
                            parsed_url = urlparse(page_url)
                            normalized_url = urlunparse((
                                parsed_url.scheme,
                                parsed_url.netloc,
                                parsed_url.path.rstrip('/') or '/',
                                parsed_url.params,
                                parsed_url.query,
                                parsed_url.fragment
                            ))
                            
                            # Track unique pages
                            if normalized_url not in crawled_pages:
                                crawled_pages[normalized_url] = {
                                    "title": page_title if page_title != "No title" else f"Page from {parsed_url.netloc}",
                                    "url": page_url,
                                    "chunks_found": 0,
                                    "total_chunks": total_chunks
                                }
                            crawled_pages[normalized_url]["chunks_found"] += 1
                        
                        # Convert to sources format
                        for page_url, page_info in crawled_pages.items():
                            source = {
                                "title": page_info["title"],
                                "file": page_info["url"],
                                "page": 1,
                                "link": page_info["url"],
                                "description": f"Content from {page_info['chunks_found']}/{page_info['total_chunks']} chunks of this page",
                                "source_type": "web_crawled_chunked",
                                "chunks_found": page_info["chunks_found"],
                                "total_chunks": page_info["total_chunks"]
                            }
                            sources.append(source)
                            logger.info(f"[RAG] Created source for existing crawled page: {page_info['url']}")
                        
                        # Build RAG prompt with existing content
                        prompt = f"""
                        You are a helpful assistant. Use the following context to answer.

                        ### Context
                        {context}

                        ### Question
                        {query}

                        ### Answer
                        """
                        answer, _ = call_openrouter(prompt)
                        
                    else:
                        # Use Crawl4AI to crawl the site (first time or empty collection)
                        logger.info(f"[RAG] Crawling website for the first time")
                        crawl_result = crawl4ai_sync(
                            url=resolved_url, 
                            query=query, 
                            collection_name=collection_name_web, 
                            depth=2,
                            max_pages=50,  # Reduced from 50 to prevent timeout
                            top_k=top_k
                        )
                        
                        # Extract context and sources from Crawl4AI result
                        context = crawl_result.get("answer", "")
                        sources = crawl_result.get("sources", [])
                        answer = context
                        logger.info(f"[RAG] Retrieved {len(sources)} detailed sources from new crawl")
                    
                    # Set up documents and file_names for consistent processing
                    documents = [(hit.payload["text"], hit.payload.get("url",""), 1) for hit in hits] if 'hits' in locals() else []
                    file_names = [hit.payload.get("url","") for hit in hits] if 'hits' in locals() else []
                    
                except Exception as e:
                    logger.error(f"[RAG] Crawl4AI failed: {e}. Using simple requests fallback.")
                    # Fallback to simple requests + BeautifulSoup
                    try:
                        import requests
                        from bs4 import BeautifulSoup
                        
                        response = requests.get(resolved_url, timeout=10, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        })
                        response.raise_for_status()
                        
                        soup = BeautifulSoup(response.content, 'html.parser')
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        text = soup.get_text()
                        # Clean up text
                        lines = (line.strip() for line in text.splitlines())
                        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                        text = ' '.join(chunk for chunk in chunks if chunk)
                        
                        # Limit text length
                        if len(text) > 4000:
                            text = text[:4000] + "..."
                        
                        documents = [(text, specific_url, 1)]
                        context = text
                        file_names = [specific_url]
                        sources = [{
                            "title": f"Content from {resolved_url}",
                            "snippet": text,
                            "link": resolved_url,
                            "source_type": "requests_fallback"
                        }]
                        logger.info(f"[RAG] Successfully used requests fallback for {resolved_url}")
                        
                    except Exception as requests_error:
                        logger.error(f"[RAG] All fallback methods failed: {requests_error}")
                        # Return error response
                        documents = [("No content could be retrieved from the website.", resolved_url, 1)]
                        context = "No content could be retrieved from the website."
                        file_names = [resolved_url]
                        sources = [{
                            "title": f"Error accessing {resolved_url}",
                            "snippet": "Unable to retrieve content from this website. Please check the URL or try again later.",
                            "link": resolved_url,
                            "source_type": "error"
                        }]
            else:
                logger.warning("[RAG] Crawl4AI not available. Using simple requests fallback.")
                # Fallback to simple requests + BeautifulSoup
                try:
                    import requests
                    from bs4 import BeautifulSoup
                    
                    response = requests.get(resolved_url, timeout=10, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    text = soup.get_text()
                    # Clean up text
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    
                    # Limit text length
                    if len(text) > 4000:
                        text = text[:4000] + "..."
                    
                    documents = [(text, specific_url, 1)]
                    context = text
                    file_names = [specific_url]
                    sources = [{
                        "title": f"Content from {specific_url}",
                        "snippet": text,
                        "link": specific_url,
                        "source_type": "requests_fallback"
                    }]
                    logger.info(f"[RAG] Successfully used requests fallback for {specific_url}")
                    
                except Exception as requests_error:
                    logger.error(f"[RAG] Requests fallback failed: {requests_error}")
                    # Return error response
                    documents = [("No content could be retrieved from the website.", specific_url, 1)]
                    context = "No content could be retrieved from the website."
                    file_names = [specific_url]
                    sources = [{
                        "title": f"Error accessing {specific_url}",
                        "snippet": "Unable to retrieve content from this website. Please check the URL or try again later.",
                        "link": specific_url,
                        "source_type": "error"
                    }]
        else:
            # No specific URL provided - check if workspace has existing crawled content
            logger.info(f"[RAG] No specific URL provided, checking for existing crawled content in workspace")
            
            workspace_name = collection_name.replace("contract_docs_", "")
            collection_name_web = workspace_name
            
            # Check if collection exists and has content
            collection_exists = False
            existing_chunks_count = 0
            try:
                collection_info = client.get_collection(collection_name_web)
                if collection_info.points_count > 0:
                    collection_exists = True
                    existing_chunks_count = collection_info.points_count
                    logger.info(f"[RAG] Found existing collection '{collection_name_web}' with {existing_chunks_count} chunks")
            except Exception:
                logger.info(f"[RAG] Collection '{collection_name_web}' doesn't exist or is empty")
            
            if collection_exists:
                # Use existing crawled content
                logger.info(f"[RAG] Using existing crawled content from collection '{collection_name_web}'")
                query_vector = model.encode(query).tolist()
                hits = client.search(collection_name=collection_name_web, query_vector=query_vector, limit=top_k)
                context = "\n---\n".join([hit.payload["text"] for hit in hits])
                
                # Create sources from existing content
                sources = []
                crawled_pages = {}  # Track unique pages
                
                for hit in hits:
                    page_url = hit.payload["url"]
                    page_title = hit.payload.get("title", page_url)
                    chunk_index = hit.payload.get("chunk_index", 0)
                    total_chunks = hit.payload.get("total_chunks", 1)
                    
                    # Normalize URL to avoid duplicates
                    from urllib.parse import urlparse, urlunparse
                    parsed_url = urlparse(page_url)
                    normalized_url = urlunparse((
                        parsed_url.scheme,
                        parsed_url.netloc,
                        parsed_url.path.rstrip('/') or '/',
                        parsed_url.params,
                        parsed_url.query,
                        parsed_url.fragment
                    ))
                    
                    # Track unique pages
                    if normalized_url not in crawled_pages:
                        crawled_pages[normalized_url] = {
                            "title": page_title if page_title != "No title" else f"Page from {parsed_url.netloc}",
                            "url": page_url,
                            "chunks_found": 0,
                            "total_chunks": total_chunks
                        }
                    crawled_pages[normalized_url]["chunks_found"] += 1
                
                # Convert to sources format
                for page_url, page_info in crawled_pages.items():
                    source = {
                        "title": page_info["title"],
                        "file": page_info["url"],
                        "page": 1,
                        "link": page_info["url"],
                        "description": f"Content from {page_info['chunks_found']}/{page_info['total_chunks']} chunks of this page",
                        "source_type": "web_crawled_chunked",
                        "chunks_found": page_info["chunks_found"],
                        "total_chunks": page_info["total_chunks"]
                    }
                    sources.append(source)
                    logger.info(f"[RAG] Created source for existing crawled page: {page_info['url']}")
                
                documents = [(hit.payload["text"], hit.payload.get("url",""), 1) for hit in hits]
                file_names = [hit.payload.get("url","") for hit in hits]
            else:
                # No existing content - prompt for URL
                logger.info(f"[RAG] No existing crawled content found, prompting for URL")
                documents = [("No specific website provided. Please provide a specific URL to crawl.", "", 1)]
                context = "No specific website provided. Please provide a specific URL to crawl."
                file_names = [""]
                sources = [{
                    "title": "No specific URL provided",
                    "snippet": "Please provide a specific website URL to crawl and analyze.",
                    "link": "",
                    "source_type": "no_url"
                }]
    else:
        # Your existing Qdrant-based retrieval
        hits = client.search(collection_name=collection_name, query_vector=model.encode(query).tolist(), limit=top_k)
        documents = [(hit.payload["text"], hit.payload.get("source_file", ""), hit.payload.get("page", 1)) for hit in hits]
        context = "\n---\n".join([doc[0] for doc in documents])
        file_names = list({hit.payload.get("source_file", "") for hit in client.scroll(collection_name=collection_name, limit=10000)[0] if hit.payload.get("source_file", "")})
    # This prompt includes context and is used for Allyin (OpenRouter)
    allyin_prompt = qa_prompt_template(context, query, response_size, response_type, file_names)
    logger.info(f"[RAG] Allyin prompt length: {len(allyin_prompt)} characters.")

    openrouter_answer = ""
    chatgpt_answer = ""
    reply_chatgpt_raw = ""
    openrouter_time = 0.0
    chatgpt_time = 0.0

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_openrouter = executor.submit(call_openrouter, allyin_prompt)
        if compare_chatgpt:
            # Conditionally set prompt for ChatGPT: full context or just the query
            if share_data_with_chatgpt:
                chatgpt_prompt_content = allyin_prompt
                logger.info(f"[RAG] ChatGPT will receive full RAG context.")
            else:
                # When share_data_with_chatgpt is False, only send the raw query to ChatGPT,
                # formatted to still ask for JSON output.
                chatgpt_prompt_content = f"""
You are a helpful assistant. Strictly output only the JSON object.
Do not include any extra commentary, no introduction, no explanation, no closing statement.
Your reply MUST start with '{{' and end with '}}'.

Your response must be in strict JSON format. The answer should be provided under a single top-level key named "answer". For example: {{"answer": "Your answer goes here."}} If the answer is a list of items, provide it as a JSON array under the "answer" key.

Question:
{query}

Answer:
"""
                logger.info(f"[RAG] ChatGPT will receive ONLY the query (no RAG context): {query[:100]}...")


            future_chatgpt = executor.submit(call_chatgpt, chatgpt_prompt_content)
        else:
            future_chatgpt = None # Don't submit if not comparing

        reply, openrouter_time = future_openrouter.result()
        if future_chatgpt: # Only get result if submitted
            reply_chatgpt_raw, chatgpt_time = future_chatgpt.result()
        else:
            chatgpt_time = 0.0

    try:
        parsed_openrouter = json.loads(reply)
        openrouter_answer = parsed_openrouter.get("answer", reply)
    except (json.JSONDecodeError, IndexError):
        openrouter_answer = reply

    if compare_chatgpt and reply_chatgpt_raw:
        chatgpt_clean_raw = reply_chatgpt_raw.strip()
        if chatgpt_clean_raw.startswith("```"):
            chatgpt_clean_raw = re.sub(r"^```(?:json)?\s*", "", chatgpt_clean_raw, flags=re.IGNORECASE)
            chatgpt_clean_raw = re.sub(r"\s*```$", "", chatgpt_clean_raw)

        try:
            parsed_chatgpt = json.loads(chatgpt_clean_raw)
            if parsed_chatgpt == {}:
                chatgpt_answer = "Information not available"
            else:
                chatgpt_answer = parsed_chatgpt.get("answer", chatgpt_clean_raw)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"[RAG] ChatGPT response not perfect JSON. Raw: {chatgpt_clean_raw[:200]}...")
            chatgpt_answer = chatgpt_clean_raw
    elif not compare_chatgpt:
        chatgpt_answer = "ChatGPT comparison disabled."

    # elapsed = time.time() - start_func_time

    # return {
    #     "openrouter": openrouter_answer,
    #     "chatgpt": chatgpt_answer,
    #     "response_time": {
    #         "total": elapsed,
    #         "openrouter": openrouter_time,
    #         "chatgpt": chatgpt_time
    #     }
    # }, documents
    elapsed = time.time() - start_func_time

    if not use_web:
        sources = [
            {"file": doc[1], "page": doc[2]}
            for doc in documents
        ]

    return {
        "openrouter": openrouter_answer,
        "chatgpt": chatgpt_answer,
        "response_time": {
            "total": elapsed,
            "openrouter": openrouter_time,
            "chatgpt": chatgpt_time
        }
    }, sources


def criteria_prompt_template(criterion: str, contract_texts: dict, user_criterion_prompt: str, score_label: str) -> str:
    prompt = f"""
You are an expert contract evaluation assistant. You are provided with multiple contracts and criteria list. Evaluate each contract independently based on the multiple evaluation criteria. Do NOT miss any criteria. For each contract along with the criteria, output its serial, name, a score from 1 to {score_label} (higher is better), and a brief rationale. Stricly score out of {score_label}

### Additional Context (User Prompt), could also be the criteria if no criteria json is provided:
{user_criterion_prompt}

You have to score for ALL sub categories provided in {criterion} list. DO NOT make up subcategories, score only for subcategories in the {criterion} list only. Do not consider all of them as a single criteria, STRICTLY judge them independently and give a score for each subcategory.
### Evaluation Criterion:
{criterion}

### Contracts:
"""
    for name, text in contract_texts.items():
        prompt += f"\n=== Contract: {name} ===\n{text}\n"
    prompt += """

Your response must be in strict JSON format like:
{{
  "contracts": [
    {{"Serial": "1a","name": "Contract_A", "criteria" : "Proposed Approach and Understanding of Dubai Realty (DR) Expectations", "score": {score_label}, "weight":0.1, "rationale": "..."}},
    {{"Serial": "1b","name": "Contract_B", "criteria" : "Technical Specifications of the Proposed Approach","score": {score_label},  "weight":0.2, "rationale": "..."}}
  ]
}}
"""
    return prompt

def compute_weighted_scores(flat_contracts: list, max_score: int = 5) -> dict:
    """
    Computes weighted scores for contracts based on a flattened list of contract evaluation entries.
    Each entry is expected to have 'name', 'score', and 'weight'.
    Returns a dictionary of contract names to their final weighted scores and percentages.
    """
    scores = collections.defaultdict(lambda: {"weighted_sum": 0.0, "total_weight": 0.0})
    
    score_key = f"score_out_of_{max_score * 10}" # Re-define for use in this function's output

    for entry in flat_contracts:
        name = str(entry.get("name", "")).replace(".pdf", "").replace("contracts/", "").strip()
        
        try:
            score = float(entry.get("score", 0))
        except (ValueError, TypeError):
            score = 0.0 # Default to 0 if score is not a valid number
            logger.warning(f"Invalid score value encountered: {entry.get('score')}. Defaulting to 0.")

        try:
            # Handle cases where weight might be a string (e.g., "0.1") or None
            weight = float(entry.get("weight", 0))
        except (ValueError, TypeError):
            weight = 0.0 # Default to 0 if weight is not a valid number
            logger.warning(f"Invalid weight value encountered: {entry.get('weight')}. Defaulting to 0.")

        scores[name]["weighted_sum"] += score * weight
        scores[name]["total_weight"] += weight

    final_scores = {}
    for name, vals in scores.items():
        total = vals["total_weight"]
        if total > 0:
            raw_score = (vals["weighted_sum"] / total)
            percentage = (raw_score / max_score) * 100
        else:
            raw_score = 0.0
            percentage = 0.0 # Or handle as N/A if weights sum to zero

        final_scores[name] = {
            score_key: round(raw_score * (max_score * 10 / max_score), 2), # Scale back to out of 100 or 50 as needed
            "percentage": round(percentage, 2)
        }
    return final_scores


def score_contracts(user_criterion_prompt: str, collection_name: str, max_score: int = 5, compare_chatgpt: bool = False, share_data_with_chatgpt: bool = False) -> dict: # Added share_data_with_chatgpt
    # Retrieve all documents for the collection
    all_hits, _ = client.scroll(collection_name=collection_name, limit=10000)
    doc_names = list(set(hit.payload.get("source_file", "unknown") for hit in all_hits))
    contract_texts = {}

    import time
    start_time = time.time()

    # Define score_key for dynamic score key naming, using base-10 scale
    score_key = f"score_out_of_{max_score * 10}"


    for name in doc_names:
        hits, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=name))]
            ),
            limit=10_000,
        )
        hits.sort(key=lambda h: h.id)
        full_text = "\n".join(h.payload["text"] for h in hits)
        full_text = full_text[:8000]  # Truncate to avoid API limits
        contract_texts[name.replace(".pdf", "").replace("contracts/", "").strip()] = full_text

    # Append additional context from parsed_criteria.jsonl if available
    criteria_path = Path(__file__).resolve().parent.parent.parent / "data" / collection_name.replace("contract_docs_", "") / "parsed_criteria.jsonl"
    outpath = Path(__file__).resolve().parent.parent.parent / "data" / collection_name.replace("contract_docs_", "") / "cleaned_criteria.json"
    criteria_context = extract_criteria_from_jsonl(criteria_path, outpath)

    # This prompt includes all relevant context for OpenRouter
    openrouter_scoring_prompt = criteria_prompt_template(criteria_context, contract_texts, user_criterion_prompt, f"{max_score}")
    if criteria_context:
        openrouter_scoring_prompt += f"\n\n### Additional Context (Criteria):\n{criteria_context}"
    logger.info(f"[RAG-Score] OpenRouter prompt length: {len(openrouter_scoring_prompt)} characters.")


    openrouter_answer_raw = "" # Renamed to avoid confusion with parsed object
    chatgpt_answer_raw = ""    # Renamed to avoid confusion with parsed object
    openrouter_time = 0.0
    chatgpt_time = 0.0

    # Decide if we will actually run ChatGPT and share context
    run_chatgpt = compare_chatgpt and share_data_with_chatgpt

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_openrouter = executor.submit(call_openrouter, openrouter_scoring_prompt)
        if run_chatgpt:
            # ChatGPT will receive full scoring context because share_data_with_chatgpt=True
            chatgpt_scoring_prompt_content = openrouter_scoring_prompt
            logger.info(f"[RAG-Score] ChatGPT will receive full scoring context.")
            future_chatgpt = executor.submit(call_chatgpt, chatgpt_scoring_prompt_content)
        else:
            logger.info("[RAG-Score] ChatGPT call skipped (share_data_with_chatgpt=False). Will return 'Information not available'.")
            future_chatgpt = None

        openrouter_answer_raw, openrouter_time = future_openrouter.result()
        if future_chatgpt:
            chatgpt_answer_raw, chatgpt_time = future_chatgpt.result()
        else:
            chatgpt_time = 0.0
            # Force a deterministic JSON so downstream parsing works
            chatgpt_answer_raw = '{"contracts": [], "answer": "Information not available"}'

    # Initialize parsed answers to empty dictionaries
    parsed_openrouter_answer = {}
    parsed_chatgpt_answer = {}

    try:
        parsed_openrouter_answer = json.loads(openrouter_answer_raw)
    except json.JSONDecodeError:
        logger.error(f"[RAG-Score] OpenRouter response not valid JSON. Raw: {openrouter_answer_raw[:200]}...")
        parsed_openrouter_answer = {"error": "Invalid JSON from OpenRouter", "raw_response": openrouter_answer_raw}

    if compare_chatgpt and chatgpt_answer_raw:
        chatgpt_clean_raw = chatgpt_answer_raw.strip()
        if chatgpt_clean_raw.startswith("```"):
            chatgpt_clean_raw = re.sub(r"^```(?:json)?\s*", "", chatgpt_clean_raw, flags=re.IGNORECASE)
            chatgpt_clean_raw = re.sub(r"\s*```$", "", chatgpt_clean_raw)

        try:
            parsed_chatgpt_answer = json.loads(chatgpt_clean_raw)
        except json.JSONDecodeError:
            logger.warning(f"[RAG-Score] ChatGPT response not perfect JSON. Raw: {chatgpt_clean_raw[:200]}...")
            parsed_chatgpt_answer = {"error": "Invalid JSON from ChatGPT", "raw_response": chatgpt_clean_raw}
    elif not compare_chatgpt:
        parsed_chatgpt_answer = {"message": "ChatGPT comparison disabled."}

    elapsed = time.time() - start_time

    final_scores_openrouter = compute_weighted_scores(parsed_openrouter_answer.get("contracts", []), max_score=max_score)
    final_scores_chatgpt = compute_weighted_scores(parsed_chatgpt_answer.get("contracts", []), max_score=max_score)

    # Summary logic: only use contracts from present results
    summary_of_best = []
    try:
        all_results_for_summary = parsed_openrouter_answer.get("contracts", [])
        if compare_chatgpt and isinstance(parsed_chatgpt_answer, dict):
            all_results_for_summary.extend(parsed_chatgpt_answer.get("contracts", []))

        # Combine all scores for best contract selection from computed final scores
        score_dict_for_best_selection = dict(final_scores_openrouter)
        if compare_chatgpt:
            score_dict_for_best_selection.update(final_scores_chatgpt)

        best_contract = None
        if score_dict_for_best_selection:
            # Find the contract with the highest score (using 'score_out_of_X' key)
            best_contract_item = max(
                score_dict_for_best_selection.items(),
                key=lambda x: x[1].get(score_key, 0) # Use score_key for comparison
            )
            best_contract = best_contract_item[0]

        if best_contract:
            # Collect rationales for the best contract from all available raw results
            relevant_entries = [
                e for e in all_results_for_summary if e.get("name", "").replace(".pdf", "").replace("contracts/", "").strip() == best_contract
            ]

            breakdown_text = "\n".join(
                f"- {e.get('criteria', e.get('criterion', 'N/A'))} (score: {e.get('score', 'N/A')}): {e.get('rationale', 'N/A')}"
                for e in relevant_entries
            )

            summary_prompt = f"""
You are a contract evaluation expert. Based on the following detailed rationale and scores for contract '{best_contract}', give 3 bullet points summarizing why this contract stands out from others.

### Details:
{breakdown_text}

Your output must be in JSON format like:
{{
  "summary": [
    "First reason...",
    "Second reason...",
    "Third reason..."
  ]
}}
"""
            summary_response, _ = call_openrouter(summary_prompt)
            summary_response = summary_response.strip()
            if summary_response.startswith("```"):
                summary_response = re.sub(r"^```(?:json)?\s*", "", summary_response, flags=re.IGNORECASE)
                summary_response = re.sub(r"\s*```$", "", summary_response)

            summary_of_best = {
                "best_contract": best_contract,
                "summary": json.loads(summary_response)["summary"]
            }
        else:
            summary_of_best = []
    except Exception as e:
        logger.error(f"[RAG-Score] Error generating summary: {e}", exc_info=True)
        summary_of_best = [f"Error generating summary: {str(e)}"]

    return {
        "raw_openrouter": parsed_openrouter_answer, # Return the parsed objects here
        "raw_chatgpt": parsed_chatgpt_answer,     # Return the parsed objects here
        "final_scores_openrouter": final_scores_openrouter,
        "final_scores_chatgpt": final_scores_chatgpt,
        "summary_of_best": summary_of_best,
        "response_time": elapsed
    }

def compare_responses(openrouter_response: str, chatgpt_response: str) -> dict:
    """Compares two LLM responses and provides a verdict."""
    comparison_prompt = f"""
You are an unbiased expert AI judge. Two LLMs were given the same context and asked the same question.
Compare both of their responses based on helpfulness, correctness, clarity, and completeness.
First, provide a short justification for each response. Then give your final verdict about which one is better.

### Response A (Allyin):
{openrouter_response}

### Response B (ChatGPT):
{chatgpt_response}

### Output Format:
{{
  "reason_allyin": "...",
  "reason_chatgpt": "...",
  "verdict": "..."
}}
"""
    try:
        response, _ = call_openrouter(comparison_prompt)
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*", "", response, flags=re.IGNORECASE)
            response = re.sub(r"\s*```$", "", response)
        return json.loads(response)
    except Exception as e:
        logger.error(f"[Compare] Error comparing responses: {e}", exc_info=True)
        return {"error": str(e)}


    # --- Crawl4AI + RAG Answer ---
import asyncio
import hashlib
try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    CRAWL4AI_AVAILABLE = True
except ImportError:
    AsyncWebCrawler = None
    CRAWL4AI_AVAILABLE = False

async def crawl4ai_and_answer(url: str, query: str, collection_name: str = "testing", depth: int = 2, max_pages: int = 20, top_k: int = 3):
    """
    Crawl a site using Crawl4AI, store in Qdrant, and answer a query with RAG.
    Chunks are upserted progressively. On timeout, returns partial results from Qdrant.
    """
    if not CRAWL4AI_AVAILABLE:
        raise ImportError("crawl4ai is not installed. Please install it with `pip install crawl4ai`.")

    ensure_qdrant_collection(collection_name)
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=depth, 
            include_external=False,
            max_pages=max_pages
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True
    )

    logger.info(f"[Crawl4AI] Starting crawl of {url} with depth {depth} and max_pages {max_pages}")
    stored_chunks = 0
    stored_pages = 0
    try:
        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun(url, config=config)
            logger.info(f"[Crawl4AI] Crawled {len(results)} pages in total")
            crawled_urls = []
            for result in results:
                page_url = getattr(result, "url", "unknown")
                page_title = getattr(result, "title", "No title")
                page_depth = result.metadata.get('depth', 0)
                if page_title == "No title" or not page_title.strip():
                    from urllib.parse import urlparse
                    parsed_url = urlparse(page_url)
                    if parsed_url.path and parsed_url.path != '/':
                        path_parts = [part for part in parsed_url.path.split('/') if part]
                        if path_parts:
                            page_title = path_parts[-1].replace('-', ' ').replace('_', ' ').title()
                        else:
                            page_title = f"Page from {parsed_url.netloc}"
                    else:
                        page_title = f"Homepage - {parsed_url.netloc}"
                crawled_urls.append(f"{page_title} - {page_url} (Depth: {page_depth})")
            logger.info(f"[Crawl4AI] Crawled pages: {crawled_urls}")
            for result in results[:3]:
                logger.info(f"[Crawl4AI] URL: {result.url}")
                logger.info(f"[Crawl4AI] Depth: {result.metadata.get('depth', 0)}")

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            batch = []
            batch_size = 10
            for r_idx, result in enumerate(results):
                text = getattr(result, "markdown", None)
                if text and hasattr(text, "raw_markdown"):
                    text = text.raw_markdown
                if not text:
                    text = getattr(result, "cleaned_html", "") or ""
                if not text.strip():
                    continue
                page_title = getattr(result, "title", "No title")
                if page_title == "No title" or not page_title.strip():
                    from urllib.parse import urlparse
                    parsed_url = urlparse(result.url)
                    if parsed_url.path and parsed_url.path != '/':
                        path_parts = [part for part in parsed_url.path.split('/') if part]
                        if path_parts:
                            page_title = path_parts[-1].replace('-', ' ').replace('_', ' ').title()
                        else:
                            page_title = f"Page from {parsed_url.netloc}"
                    else:
                        page_title = f"Homepage - {parsed_url.netloc}"
                chunks = text_splitter.split_text(text)
                logger.info(f"[Crawl4AI] Split content from {result.url} into {len(chunks)} chunks")
                for i, chunk in enumerate(chunks):
                    if len(batch) % batch_size == 0 and len(batch) > 0:
                        client.upsert(collection_name=collection_name, points=batch)
                        stored_chunks += len(batch)
                        batch = []
                        logger.info(f"[Crawl4AI] Progressive upsert: {stored_chunks} chunks stored so far (page {r_idx+1}/{len(results)})")
                    embedding = model.encode(chunk).tolist()
                    uid = hashlib.md5((result.url + chunk[:200] + str(i)).encode()).hexdigest()
                    batch.append(PointStruct(
                        id=uid,
                        vector=embedding,
                        payload={
                            "url": result.url, 
                            "depth": result.metadata.get("depth", 0), 
                            "text": chunk,
                            "title": page_title,
                            "metadata": result.metadata,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "source_type": "web_crawled"
                        }
                    ))
                stored_pages += 1
            # Final upsert for remaining batch
            if batch:
                client.upsert(collection_name=collection_name, points=batch)
                stored_chunks += len(batch)
                logger.info(f"[Crawl4AI] Final upsert: {stored_chunks} chunks stored in total from {stored_pages} pages")
    except asyncio.TimeoutError:
        logger.warning(f"[Crawl4AI] Crawling timed out. Returning partial results. Chunks so far: {stored_chunks}, pages: {stored_pages}")
        # Return partial results: search Qdrant for the query
        query_vector = model.encode(query).tolist()
        hits = client.search(collection_name=collection_name, query_vector=query_vector, limit=top_k)
        context = "\n---\n".join([hit.payload["text"] for hit in hits])
        # Build sources from Qdrant
        sources = []
        crawled_pages = {}
        for hit in hits:
            page_url = hit.payload["url"]
            page_title = hit.payload.get("title", page_url)
            chunk_index = hit.payload.get("chunk_index", 0)
            total_chunks = hit.payload.get("total_chunks", 1)
            from urllib.parse import urlparse, urlunparse
            parsed_url = urlparse(page_url)
            normalized_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path.rstrip('/') or '/',
                parsed_url.params,
                parsed_url.query,
                parsed_url.fragment
            ))
            if normalized_url not in crawled_pages:
                crawled_pages[normalized_url] = {
                    "title": page_title if page_title != "No title" else f"Page from {parsed_url.netloc}",
                    "url": page_url,
                    "chunks_found": 0,
                    "total_chunks": total_chunks
                }
            crawled_pages[normalized_url]["chunks_found"] += 1
        for page_url, page_info in crawled_pages.items():
            source = {
                "title": page_info["title"],
                "file": page_url,
                "page": 1,
                "link": page_url,
                "description": f"Content from {page_info['chunks_found']}/{page_info['total_chunks']} chunks of this page",
                "source_type": "web_crawled_chunked",
                "chunks_found": page_info["chunks_found"],
                "total_chunks": page_info["total_chunks"]
            }
            sources.append(source)
            logger.info(f"[Crawl4AI] Created source for partial crawled page: {page_url}")
        # Return minimal answer
        return {
            "answer": "Partial answer due to timeout. This is based on currently crawled and indexed content.",
            "sources": sources
        }

    # Normal completion: Run semantic search
    query_vector = model.encode(query).tolist()
    hits = client.search(collection_name=collection_name, query_vector=query_vector, limit=top_k)
    context = "\n---\n".join([hit.payload["text"] for hit in hits])
    sources = []
    crawled_pages = {}
    for hit in hits:
        page_url = hit.payload["url"]
        page_title = hit.payload.get("title", page_url)
        chunk_index = hit.payload.get("chunk_index", 0)
        total_chunks = hit.payload.get("total_chunks", 1)
        from urllib.parse import urlparse, urlunparse
        parsed_url = urlparse(page_url)
        normalized_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path.rstrip('/') or '/',
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment
        ))
        if normalized_url not in crawled_pages:
            crawled_pages[normalized_url] = {
                "title": page_title if page_title != "No title" else f"Page from {parsed_url.netloc}",
                "url": page_url,
                "chunks_found": 0,
                "total_chunks": total_chunks
            }
        crawled_pages[normalized_url]["chunks_found"] += 1
    for page_url, page_info in crawled_pages.items():
        source = {
            "title": page_info["title"],
            "file": page_url,
            "page": 1,
            "link": page_url,
            "description": f"Content from {page_info['chunks_found']}/{page_info['total_chunks']} chunks of this page",
            "source_type": "web_crawled_chunked",
            "chunks_found": page_info["chunks_found"],
            "total_chunks": page_info["total_chunks"]
        }
        sources.append(source)
        logger.info(f"[Crawl4AI] Created source for crawled page: {page_url}")

    prompt = f"""
    You are a helpful assistant. Use the following context to answer.

    ### Context
    {context}

    ### Question
    {query}

    ### Answer
    """
    answer, _ = call_openrouter(prompt)
    return {"answer": answer, "sources": sources}

def crawl4ai_sync(url: str, query: str, collection_name: str = "testing", depth: int = 2, max_pages: int = 20, top_k: int = 3):
    """
    Synchronous wrapper for Crawl4AI crawling and RAG answering.
    Handles timeouts and returns partial results from Qdrant if timeout occurs.
    """
    try:
        # Always create a new event loop in a separate thread to avoid conflicts
        import concurrent.futures
        import threading
        
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                # Increased timeout to 1200s (20min)
                return new_loop.run_until_complete(
                    asyncio.wait_for(
                        crawl4ai_and_answer(url, query, collection_name, depth, max_pages, top_k),
                        timeout=1200
                    )
                )
            finally:
                new_loop.close()
                
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            try:
                # Increased thread execution timeout to 1500s (25min)
                return future.result(timeout=1500)
            except concurrent.futures.TimeoutError:
                logger.warning(f"[Crawl4AI] Thread execution timed out after 1500 seconds, returning partial results from Qdrant.")
                # Query Qdrant for partial results
                query_vector = model.encode(query).tolist()
                hits = client.search(collection_name=collection_name, query_vector=query_vector, limit=top_k)
                context = "\n---\n".join([hit.payload["text"] for hit in hits])
                sources = []
                crawled_pages = {}
                for hit in hits:
                    page_url = hit.payload["url"]
                    page_title = hit.payload.get("title", page_url)
                    chunk_index = hit.payload.get("chunk_index", 0)
                    total_chunks = hit.payload.get("total_chunks", 1)
                    from urllib.parse import urlparse, urlunparse
                    parsed_url = urlparse(page_url)
                    normalized_url = urlunparse((
                        parsed_url.scheme,
                        parsed_url.netloc,
                        parsed_url.path.rstrip('/') or '/',
                        parsed_url.params,
                        parsed_url.query,
                        parsed_url.fragment
                    ))
                    if normalized_url not in crawled_pages:
                        crawled_pages[normalized_url] = {
                            "title": page_title if page_title != "No title" else f"Page from {parsed_url.netloc}",
                            "url": page_url,
                            "chunks_found": 0,
                            "total_chunks": total_chunks
                        }
                        crawled_pages[normalized_url]["chunks_found"] += 1
                for page_url, page_info in crawled_pages.items():
                    source = {
                        "title": page_info["title"],
                        "file": page_url,
                        "page": 1,
                        "link": page_url,
                        "description": f"Content from {page_info['chunks_found']}/{page_info['total_chunks']} chunks of this page",
                        "source_type": "web_crawled_chunked",
                        "chunks_found": page_info["chunks_found"],
                        "total_chunks": page_info["total_chunks"]
                    }
                    sources.append(source)
                    logger.info(f"[Crawl4AI] Created source for partial crawled page: {page_url}")
                return {
                    "answer": "Partial answer due to timeout. This is based on currently crawled and indexed content.",
                    "sources": sources
                }
                
    except Exception as e:
        logger.error(f"[Crawl4AI] Error in crawl4ai_sync: {e}")
        # Return error response
        return {
            "answer": f"Error occurred during web crawling: {str(e)}",
            "sources": []
        }