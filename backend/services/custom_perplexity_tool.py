# services/custom_perplexity_tool.py
import os
import json
import requests
from typing import Any, Optional
from autogen.tools.experimental import PerplexitySearchTool
from autogen.tools.experimental.perplexity.perplexity_search import SearchResponse, PerplexityChatCompletionResponse
from pydantic import ValidationError

class CustomPerplexitySearchTool(PerplexitySearchTool):
    """
    Custom PerplexitySearchTool with configurable timeout for complex requests.
    Supports domain exclusion to avoid biased vendor sources.
    """
    
    def __init__(
        self,
        model: str = "sonar",
        api_key: Optional[str] = None,
        max_tokens: int = 1000,
        search_domain_filter: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        timeout: int = 60,  # Increased default timeout to 60 seconds
        num_search_results: int = 10,  # Default to 10, within the 3-20 range
    ):
        super().__init__(model=model, api_key=api_key, max_tokens=max_tokens, search_domain_filter=search_domain_filter)
        self.timeout = timeout
        self.exclude_domains = exclude_domains or []
        self.num_search_results = max(3, min(20, num_search_results))  # Ensure it's within bounds
    
    
    def _filter_citations(self, citations: list) -> list:
        """
        Filter out citations from excluded domains.
        """
        if not self.exclude_domains or not citations:
            return citations
        
        filtered_citations = []
        for citation in citations:
            # Handle different citation formats
            if isinstance(citation, str):
                url = citation
            elif isinstance(citation, dict) and 'url' in citation:
                url = citation['url']
            else:
                # Keep unknown formats
                filtered_citations.append(citation)
                continue
            
            if not url or not isinstance(url, str):
                filtered_citations.append(citation)
                continue
            
            # Extract domain from URL
            import re
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if not domain_match:
                filtered_citations.append(citation)
                continue
            
            domain = domain_match.group(1).lower()
            
            # Check if domain should be excluded
            should_exclude = False
            for exclude_domain in self.exclude_domains:
                if exclude_domain.lower() in domain or domain in exclude_domain.lower():
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered_citations.append(citation)
        
        return filtered_citations
    
    def _execute_query(self, payload: dict[str, Any]) -> "PerplexityChatCompletionResponse":
        """
        Executes a query by sending a POST request to the Perplexity API with custom timeout.
        Override to ensure num_search_results is within valid bounds.
        """
        # Ensure num_search_results is within the valid range (3-20)
        if 'num_search_results' in payload:
            payload['num_search_results'] = max(3, min(20, payload['num_search_results']))
        else:
            payload['num_search_results'] = self.num_search_results
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        response = requests.request("POST", self.url, json=payload, headers=headers, timeout=self.timeout)
        try:
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            raise RuntimeError(
                f"Perplexity API => Request timed out after {self.timeout} seconds: {response.text}. Status code: {response.status_code}"
            ) from e
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(
                f"Perplexity API => HTTP error occurred: {response.text}. Status code: {response.status_code}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Perplexity API => Error during request: {response.text}. Status code: {response.status_code}"
            ) from e

        try:
            response_json = response.json()
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Perplexity API => Invalid JSON response received. Error: {e}") from e

        try:
            # This may raise a pydantic.ValidationError if the response structure is not as expected.
            perp_resp = PerplexityChatCompletionResponse(**response_json)
        except ValidationError as e:
            raise RuntimeError("Perplexity API => Validation error when parsing API response: " + str(e)) from e
        except Exception as e:
            raise RuntimeError(
                "Perplexity API => Failed to parse API response into PerplexityChatCompletionResponse: " + str(e)
            ) from e

        # Filter out excluded domains from citations if any
        if self.exclude_domains and hasattr(perp_resp, 'citations') and perp_resp.citations:
            perp_resp.citations = self._filter_citations(perp_resp.citations)
        
        return perp_resp
    
    def search(self, query: str) -> "SearchResponse":
        """
        Override the search method to ensure our custom _execute_query is used.
        """
        return super().search(query)
