# backend/services/legal_service.py
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
            # Truncate to avoid API limits but keep more content for legal analysis
            full_text = full_text[:12000]  # Increased limit for legal analysis
            contract_texts[name.replace(".pdf", "").replace("contracts/", "").strip()] = full_text
        
        logger.info(f"Retrieved {len(contract_texts)} contracts from collection {collection_name}")
        return contract_texts
        
    except Exception as e:
        logger.error(f"Error retrieving contracts from collection {collection_name}: {e}")
        return {}

def create_legal_analysis_prompt(contract_texts: Dict[str, str], workspace_name: str) -> str:
    """Create a comprehensive legal analysis prompt for contract clause recommendations."""
    
    contracts_summary = "\n\n".join([
        f"=== CONTRACT: {name} ===\n{text[:8000]}..." if len(text) > 8000 else f"=== CONTRACT: {name} ===\n{text}"
        for name, text in contract_texts.items()
    ])
    
    prompt = f"""You are a legal expert specializing in contract law and procurement. Your task is to perform a comprehensive legal analysis of all contracts in the workspace "{workspace_name}" and provide clause recommendations based on the nature of procurement and services.

CONTRACTS TO ANALYZE:
{contracts_summary}

Please provide a detailed legal analysis report covering the following areas:

## 1. CONTRACT NATURE & PROCUREMENT TYPE ANALYSIS
- Identify the type of procurement (goods, services, works, or mixed)
- Determine the nature of services being procured
- Assess the complexity and risk level of the procurement
- Identify any specialized industry requirements

## 2. EXISTING CLAUSE INVENTORY
- List all current clauses present in the contracts
- Categorize clauses by type (commercial, legal, technical, operational)
- Identify the strength and comprehensiveness of existing clauses
- Note any standard vs. custom clause implementations

## 3. MISSING CRITICAL CLAUSES ANALYSIS
Based on the procurement nature and service type, identify missing clauses:

### A. RISK MANAGEMENT CLAUSES
- Indemnity clauses (mutual vs. one-sided)
- Limitation of liability provisions
- Force majeure clauses
- Insurance requirements and coverage
- Risk allocation mechanisms

### B. PERFORMANCE & PENALTY CLAUSES
- Performance guarantees and warranties
- Liquidated damages and penalty clauses
- Service level agreements (SLAs) with penalties
- Milestone-based penalties
- Performance bonds and guarantees

### C. COMPLIANCE & REGULATORY CLAUSES
- Data protection and privacy compliance (GDPR, CCPA, etc.)
- Industry-specific regulatory compliance
- Environmental and sustainability requirements
- Anti-corruption and ethics clauses
- Export control and trade compliance

### D. INTELLECTUAL PROPERTY CLAUSES
- IP ownership and assignment
- Confidentiality and non-disclosure
- Patent and trademark considerations
- Work-for-hire provisions
- IP indemnification

### E. TERMINATION & EXIT CLAUSES
- Termination for convenience vs. cause
- Exit assistance and transition clauses
- Data return and destruction
- Post-termination obligations
- Survival clauses

## 4. RISK-BASED CLAUSE RECOMMENDATIONS
For each identified risk area, provide specific clause recommendations:

### HIGH-RISK PROJECTS
- Enhanced indemnity provisions
- Stricter penalty structures
- Comprehensive insurance requirements
- Detailed force majeure definitions
- Robust termination rights

### MEDIUM-RISK PROJECTS
- Standard indemnity and liability limits
- Moderate penalty structures
- Basic insurance requirements
- Standard force majeure clauses
- Balanced termination provisions

### LOW-RISK PROJECTS
- Basic liability protections
- Minimal penalty structures
- Standard insurance requirements
- Simple force majeure clauses
- Standard termination rights

## 5. INDUSTRY-SPECIFIC RECOMMENDATIONS
Based on the service type, recommend industry-specific clauses:
- Technology/IT services: Data security, software licensing, system integration
- Construction/Engineering: Safety requirements, quality standards, change orders
- Professional services: Professional liability, conflict of interest, deliverables
- Manufacturing/Supply: Quality control, delivery terms, product liability
- Financial services: Regulatory compliance, audit rights, confidentiality

## 6. CLAUSE TEMPLATES & DRAFTING GUIDANCE
Provide specific clause language recommendations for:
- Missing indemnity clauses with appropriate scope and limitations
- Penalty clause structures with graduated severity
- Force majeure definitions tailored to the procurement type
- Insurance requirements with specific coverage amounts
- Termination clauses with appropriate notice periods

## 7. IMPLEMENTATION PRIORITY MATRIX
Rank recommendations by:
- Legal risk level (High/Medium/Low)
- Implementation complexity (High/Medium/Low)
- Business impact (High/Medium/Low)
- Urgency (Immediate/Short-term/Long-term)

## 8. COMPLIANCE CHECKLIST
Provide a checklist of legal requirements to verify:
- Regulatory compliance gaps
- Standard industry practices
- Jurisdictional requirements
- International trade considerations

## 9. SUMMARY & ACTION ITEMS
- Executive summary of critical missing clauses
- Top 5 priority recommendations
- Implementation timeline
- Legal review requirements
- Stakeholder consultation needs

Please provide a thorough, actionable legal analysis that focuses on practical clause recommendations tailored to the specific nature of the procurement and services in these contracts. Include specific clause language where appropriate and prioritize recommendations based on risk assessment.

Format your response as a structured legal report with clear sections, specific recommendations, and actionable next steps."""

    return prompt

def perform_legal_analysis(workspace_name: str) -> Dict[str, Any]:
    """Perform comprehensive legal analysis for contract clause recommendations."""
    logger.info(f"Starting legal analysis for workspace: {workspace_name}")
    
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
        
        # Create legal analysis prompt
        legal_prompt = create_legal_analysis_prompt(contract_texts, workspace_name)
        
        logger.info(f"Legal analysis prompt created with {len(legal_prompt)} characters")
        
        # Call OpenRouter for legal analysis
        start_time = time.time()
        legal_response, api_time = call_openrouter(legal_prompt)
        total_time = time.time() - start_time
        
        # Prepare results
        legal_results = {
            "workspace_name": workspace_name,
            "collection_name": collection_name,
            "contracts_analyzed": len(contract_texts),
            "contract_names": list(contract_texts.keys()),
            "legal_analysis_report": legal_response,
            "processing_time": {
                "total_time": round(total_time, 2),
                "api_time": round(api_time, 2),
                "preprocessing_time": round(total_time - api_time, 2)
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "completed"
        }
        
        logger.info(f"Legal analysis completed for workspace '{workspace_name}' in {total_time:.2f}s")
        return legal_results
        
    except Exception as e:
        logger.error(f"Error performing legal analysis for workspace '{workspace_name}': {e}")
        return {
            "workspace_name": workspace_name,
            "error": str(e),
            "status": "failed",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

def save_legal_results(workspace_name: str, legal_results: Dict[str, Any]) -> str:
    """Save legal analysis results to a JSON file in the workspace directory."""
    try:
        workspace_dir = Path(__file__).resolve().parent.parent.parent / "data" / workspace_name
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        legal_file = workspace_dir / "legal_analysis_results.json"
        
        with open(legal_file, 'w', encoding='utf-8') as f:
            json.dump(legal_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Legal analysis results saved to {legal_file}")
        return str(legal_file)
        
    except Exception as e:
        logger.error(f"Error saving legal analysis results: {e}")
        raise e
