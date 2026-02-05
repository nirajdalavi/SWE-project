# backend/services/audit_service.py
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
import os
import requests
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "qwen/qwq-32b"

def call_openrouter(prompt: str) -> tuple[str, float]:
    """Call OpenRouter API and return response and time taken."""
    start_time = time.time()
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://allyin.ai",
        "X-Title": "Allyin Compass"
    }
    
    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4000
    }
    
    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        end_time = time.time()
        return content, end_time - start_time
        
    except Exception as e:
        logger.error(f"OpenRouter API call failed: {e}")
        return f"Error: {str(e)}", time.time() - start_time

def get_all_contracts_from_collection(collection_name: str) -> Dict[str, str]:
    """Retrieve all contracts from a Qdrant collection."""
    try:
        QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
        QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # Get all documents from the collection
        all_hits, _ = client.scroll(
            collection_name=collection_name,
            limit=10_000,
        )
        
        # Group by source file
        doc_names = list(set(hit.payload.get("source_file", "unknown") for hit in all_hits))
        contract_texts = {}
        
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
            # Truncate to avoid API limits but keep more content for audit
            full_text = full_text[:12000]  # Increased limit for audit
            contract_texts[name.replace(".pdf", "").replace("contracts/", "").strip()] = full_text
        
        logger.info(f"Retrieved {len(contract_texts)} contracts from collection {collection_name}")
        return contract_texts
        
    except Exception as e:
        logger.error(f"Error retrieving contracts from collection {collection_name}: {e}")
        return {}

def create_audit_prompt(contract_texts: Dict[str, str], workspace_name: str) -> str:
    """Create a comprehensive audit prompt for contract analysis."""
    
    contracts_summary = "\n\n".join([
        f"=== CONTRACT: {name} ===\n{text[:8000]}..." if len(text) > 8000 else f"=== CONTRACT: {name} ===\n{text}"
        for name, text in contract_texts.items()
    ])
    
    prompt = f"""You are a legal and business contract auditor. Your task is to perform a comprehensive audit of all contracts in the workspace "{workspace_name}".

CONTRACTS TO AUDIT:
{contracts_summary}

Please provide a detailed audit report covering the following areas:

## 1. CONTRACT OVERVIEW
- Total number of contracts analyzed
- Contract types and categories identified
- General business context and purpose

## 2. KEY TERMS & CONDITIONS ANALYSIS
- Payment terms and schedules
- Delivery timelines and milestones
- Service level agreements (SLAs)
- Performance metrics and KPIs
- Termination clauses and conditions

## 3. RISK ASSESSMENT
- High-risk clauses or terms
- Potential legal vulnerabilities
- Compliance issues or gaps
- Financial risks and exposures
- Operational risks

## 4. COMPLIANCE & REGULATORY REVIEW
- Regulatory compliance requirements
- Data protection and privacy considerations
- Industry-specific regulations
- International trade considerations (if applicable)

## 5. FINANCIAL ANALYSIS
- Total contract values
- Payment structures and schedules
- Cost implications and budget impacts
- Revenue recognition considerations
- Financial performance metrics

## 6. OPERATIONAL IMPACT
- Resource requirements and allocation
- Timeline dependencies and critical paths
- Integration requirements
- Change management considerations

## 7. RECOMMENDATIONS
- Priority actions required
- Contract optimization opportunities
- Risk mitigation strategies
- Process improvements
- Compliance enhancements

## 8. SUMMARY & NEXT STEPS
- Executive summary of key findings
- Critical issues requiring immediate attention
- Recommended follow-up actions
- Timeline for implementation

Please provide a thorough, professional audit report that would be suitable for executive review and decision-making. Focus on actionable insights and practical recommendations.

Format your response as a structured report with clear sections and bullet points where appropriate."""

    return prompt

def perform_contract_audit(workspace_name: str) -> Dict[str, Any]:
    """Perform comprehensive contract audit for a workspace."""
    logger.info(f"Starting contract audit for workspace: {workspace_name}")
    
    collection_name = f"contract_docs_{workspace_name}"
    
    try:
        # Check if collection exists
        QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
        QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        if not client.collection_exists(collection_name):
            raise Exception(f"No contracts found for workspace '{workspace_name}'. Please upload and embed contracts first.")
        
        # Get all contracts
        contract_texts = get_all_contracts_from_collection(collection_name)
        
        if not contract_texts:
            raise Exception(f"No contract documents found in collection '{collection_name}'")
        
        # Create audit prompt
        audit_prompt = create_audit_prompt(contract_texts, workspace_name)
        
        logger.info(f"Audit prompt created with {len(audit_prompt)} characters")
        
        # Call OpenRouter for audit analysis
        start_time = time.time()
        audit_response, api_time = call_openrouter(audit_prompt)
        total_time = time.time() - start_time
        
        # Prepare results
        audit_results = {
            "workspace_name": workspace_name,
            "collection_name": collection_name,
            "contracts_analyzed": len(contract_texts),
            "contract_names": list(contract_texts.keys()),
            "audit_report": audit_response,
            "processing_time": {
                "total_time": round(total_time, 2),
                "api_time": round(api_time, 2),
                "preprocessing_time": round(total_time - api_time, 2)
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "completed"
        }
        
        logger.info(f"Contract audit completed for workspace '{workspace_name}' in {total_time:.2f}s")
        return audit_results
        
    except Exception as e:
        logger.error(f"Error performing contract audit for workspace '{workspace_name}': {e}")
        return {
            "workspace_name": workspace_name,
            "error": str(e),
            "status": "failed",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

def save_audit_results(workspace_name: str, audit_results: Dict[str, Any]) -> str:
    """Save audit results to a JSON file in the workspace directory."""
    try:
        workspace_dir = Path(__file__).resolve().parent.parent.parent / "data" / workspace_name
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        audit_file = workspace_dir / "audit_results.json"
        
        with open(audit_file, 'w', encoding='utf-8') as f:
            json.dump(audit_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Audit results saved to {audit_file}")
        return str(audit_file)
        
    except Exception as e:
        logger.error(f"Error saving audit results: {e}")
        raise e
