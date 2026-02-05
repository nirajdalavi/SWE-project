# backend/services/prompt_generator_service.py
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from typing import List
import logging # Import logging

logger = logging.getLogger(__name__) # Get logger for this module

# Import necessary functions from other services
from services.rag_service import call_openrouter, call_chatgpt
from services.helper_service import extract_criteria_from_jsonl

# Load env variables for this service
load_dotenv()
# Note: OPENROUTER_API_KEY and OPENAI_API_KEY are used by call_openrouter/call_chatgpt,
# which are imported here.
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
# --- Initialize client and model for this service ---
# These are initialized here as the service directly depends on them.
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
# text_encoder_model = SentenceTransformer("all-MiniLM-L6-v2") # Not strictly needed for embedding here, but for model initialization if it was only here

# --- Define a SMALLER LLM for prompt generation ---
# Changed to a faster, smaller model for prompt generation to improve responsiveness
# This model is specifically for generating prompts, not for RAG answers/scoring.
SMALL_PROMPT_GEN_MODEL = "mistralai/mistral-7b-instruct:free" # Changed from "mistralai/mistral-small-3.2-24b-instruct:free"

def generate_ai_prompts(workspace_name: str, base_dir: Path) -> List[str]:
    """
    Generates a list of simple, relevant, and actionable prompts (questions)
    based on contract content (company names and key phrases) and loaded criteria
    for a given workspace using an LLM.
    Reads contract content directly from parsed.jsonl.
    """
    generated_prompts = []

    # 1. Get all contract texts for the workspace directly from parsed.jsonl
    parsed_jsonl_path = base_dir / "data" / workspace_name / "parsed.jsonl"
    contract_texts_map = {}

    if not parsed_jsonl_path.exists():
        logger.warning(f"parsed.jsonl not found for workspace '{workspace_name}' at {parsed_jsonl_path}. Skipping contract text extraction for prompt generation.")
    else:
        try:
            with open(parsed_jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        doc = json.loads(line)
                        file_name = doc.get("file", "unknown_file")
                        text_content = doc.get("text", "")
                        contract_texts_map[file_name] = contract_texts_map.get(file_name, "") + text_content + "\n"
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping malformed JSON line in {parsed_jsonl_path}: {line.strip()} - {e}")
                        continue

            # Truncate texts for prompt to avoid exceeding context window
            for key in contract_texts_map:
                contract_texts_map[key] = contract_texts_map[key][:8000] # Truncate to avoid API limits

        except Exception as e:
            logger.warning(f"Could not read or process parsed.jsonl for prompt generation: {e}")
            contract_texts_map = {}

    # --- ENHANCED DATA RETRIEVAL START ---

    # 2. Extract company names
    extracted_companies = set()
    company_designators = r'\b(?:LLC|Inc|Corp|Limited|Ltd|Company|Co|Corporation|Group|Holdings|Solutions|Technologies|Services|Associates|Partners|Ventures|Systems|Global|International|Digital|Pte?\.? Ltd|GmbH|AG|SA|AB|NV|BV|PLC|S\.A\.S)\b'
    company_pattern = re.compile(
        r'([A-Z][a-zA-Z0-9\s,\.&-]{1,50}?' + company_designators + r')', # Captures actual name + designator
        re.IGNORECASE
    )

    for text in contract_texts_map.values():
        for match in company_pattern.finditer(text): # Use finditer to get match objects for spans
            company_name = match.group(1).strip()
            company_name = re.sub(r'[,\.]+$', '', company_name).strip() # Remove trailing commas/dots
            if len(company_name.split()) > 1 and len(company_name.split()) <= 6: # Allow up to 6 words
                extracted_companies.add(company_name)

    common_phrases_to_exclude = {
        "the company", "this company", "any company", "all company",
        "the corporation", "this corporation", "terms and conditions",
        "party a", "party b", "contracting party"
    }
    company_names = [
        name for name in extracted_companies
        if name.lower() not in common_phrases_to_exclude and len(name.split()) > 1 # Must be multi-word
    ]
    company_names = list(set(company_names))[:5] # Limit to top 5 relevant companies for conciseness

    # 3. Simple Keyword/Keyphrase Identification
    all_combined_text = " ".join(contract_texts_map.values()).lower()

    common_contract_phrases = set()
    phrases_to_look_for = [
        r"intellectual property", r"payment terms", r"termination clause",
        r"confidentiality agreement", r"data privacy", r"force majeure",
        r"governing law", r"dispute resolution", r"warranty period",
        r"indemnification", r"limitation of liability", r"service level agreement",
        r"effective date", r"renewal terms", r"exclusivity clause", r"subcontracting"
    ]

    for phrase_pattern in phrases_to_look_for:
        if re.search(phrase_pattern, all_combined_text):
            common_contract_phrases.add(phrase_pattern.replace(r'\b', '').strip()) # Add cleaned phrase

    word_counts = {}
    words = re.findall(r'\b\w+\b', all_combined_text)
    for i in range(len(words) - 1):
        phrase = words[i] + " " + words[i+1]
        word_counts[phrase] = word_counts.get(phrase, 0) + 1
        if i < len(words) - 2:
            phrase_three = phrase + " " + words[i+2]
            word_counts[phrase_three] = word_counts.get(phrase_three, 0) + 1

    frequent_phrases = [
        p for p, count in word_counts.items()
        if count > 5 and len(p.split()) > 1 and len(p.split()) < 5 # 2 to 4 words
        and p.lower() not in common_phrases_to_exclude # Exclude common stop phrases
    ]
    extracted_keywords = list(set(list(common_contract_phrases) + frequent_phrases))[:5] # Combine and limit to top 5 for conciseness

    # --- ENHANCED DATA RETRIEVAL END ---

    # 4. Load cleaned criteria
    criteria_path = base_dir / "data" / workspace_name / "cleaned_criteria.json"
    criteria_context = ""
    if criteria_path.exists():
        try:
            with open(criteria_path, 'r', encoding='utf-8') as f:
                criteria_data = json.load(f)
            criteria_context = json.dumps(criteria_data, indent=2)
        except Exception as e:
            logger.warning(f"Could not extract criteria for prompt generation from {criteria_path}: {e}")
            criteria_context = ""

    # 5. Construct LLM prompt with richer context and new instructions
    llm_prompt = f"""
You are an expert in contract analysis and business intelligence.
Your task is to generate 10 diverse, very simple, short and highly relevant prompts (questions)
that a user might ask about contracts, the answers to these questions should be easily extractable.
These prompts should be actionable and cover information extraction, comparison, or evaluation aspects.
Focus on common contract elements, key entities, and any specific criteria provided.
Ensure the questions are direct and can be answered from a contract document.

### Context for Prompt Generation:
"""

    if company_names:
        llm_prompt += f"- Key Entities (Companies): {', '.join(company_names)}\n"
    if extracted_keywords:
        llm_prompt += f"- Important Concepts/Keywords: {', '.join(extracted_keywords)}\n"
    if criteria_context:
        llm_prompt += f"- Specific Evaluation Criteria: {criteria_context}\n"
    if not company_names and not extracted_keywords and not criteria_context:
        llm_prompt += "No specific entities, keywords, or criteria provided. Generate general simple contract analysis prompts.\n"

    llm_prompt += """
Generate exactly 10 prompts.
Prioritize clarity, simplicity, relevance, and actionability.
Your output must be a JSON array of strings, like this:
{
  "prompts": [
    "Prompt 1: ...",
    "Prompt 2: ...",
    "Prompt 3: ...",
    "..."
  ]
}
"""
    logger.info(f"🧠 Prompt for AI generation character length: {len(llm_prompt)}")

    # 6. Call LLM and parse response
    try:
        # UNPACK THE TUPLE HERE!
        response_text_raw, openrouter_time_elapsed = call_openrouter(llm_prompt, model_name=SMALL_PROMPT_GEN_MODEL, temperature=0.7)
        
        # Now, use response_text_raw which is the string you need to strip
        response_text = response_text_raw.strip()
        
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text, flags=re.IGNORECASE)
            response_text = re.sub(r"\s*```$", "", response_text)

        parsed_response = json.loads(response_text)
        generated_prompts = parsed_response.get("prompts", [])

        if isinstance(generated_prompts, list) and all(isinstance(p, str) for p in generated_prompts):
            return generated_prompts
        else:
            logger.warning("LLM response for prompt generation was not a list of strings.")
            return []

    except Exception as e:
        logger.error(f"Error generating AI prompts: {e}")
        return []