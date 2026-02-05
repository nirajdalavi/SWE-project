# services/resume_scoring_service.py
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import requests
import re
import time
from qdrant_client import QdrantClient

# Get workspace root - should match main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = PROJECT_ROOT / "data"

logger = logging.getLogger(__name__)
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_MODEL = "qwen/qwq-32b"

# Initialize Qdrant client
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)



def extract_candidate_names_from_parsed_file(workspace_name: str) -> Dict[str, str]:
    """
    Extract candidate names directly from parsed_resumes.jsonl file.
    This ensures we get the actual resume content, not random chunks from Qdrant.
    """
    try:
        # Construct path to parsed_resumes.jsonl
        script_dir = Path(__file__).resolve().parent.parent.parent
        parsed_file_path = script_dir / "data" / workspace_name / "parsed_resumes.jsonl"
        
        if not parsed_file_path.exists():
            logger.warning(f"Parsed resumes file not found: {parsed_file_path}")
            return {}
        
        # Read and combine text by filename
        resume_docs = {}
        with open(parsed_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    doc = json.loads(line.strip())
                    filename = doc.get("file", "")
                    text = doc.get("text", "")
                    
                    # Remove file extension for the key
                    filename_without_ext = Path(filename).stem
                    
                    if filename_without_ext not in resume_docs:
                        resume_docs[filename_without_ext] = []
                    resume_docs[filename_without_ext].append(text)
                except json.JSONDecodeError:
                    continue
        
        # Combine all chunks for each document
        combined_resumes = {}
        for filename, texts in resume_docs.items():
            combined_resumes[filename] = '\n'.join(texts)
        
        # Now extract names from the actual resume content
        resumes_content = ""
        for i, (filename, text) in enumerate(combined_resumes.items(), 1):
            # Log the first part of each resume for debugging
            logger.info(f"Resume {i} ({filename}) first 200 chars: {text[:200]}")
            resumes_content += f"\n\n--- RESUME {i}: {filename} ---\n{text[:500]}"  # Use first 500 chars for better name detection
        
        prompt = f"""
        Extract the candidate's full name from each of the following resume texts.
        
        Instructions:
        1. Look for the person's name at the top of the resume, in contact information, or in the header
        2. Names are typically in formats like "John Doe", "Jane Smith", "Dr. John Smith", etc.
        3. Look for patterns like "Name:", "Contact:", or just the name prominently displayed
        4. If you find a clear name, return it exactly as it appears
        5. If no clear name is found, use the filename (without extension) as fallback
        
        Resume Texts:
        {resumes_content}
        
        Return a JSON object mapping each filename to the extracted name.
        Use the EXACT filename (without extension) as the key in your response.
        
        Example format:
        {{
            "retreat&regroup": "John Doe",
            "NJ_s_resume (3)": "Jane Smith"
        }}
        
        IMPORTANT: 
        - Return only the JSON object, no extra text or explanations
        - Use the exact filename as the key, not "RESUME 1", "RESUME 2", etc.
        """
        
        response = call_openrouter(prompt, temperature=0.0)
        logger.info(f"Name extraction response: {response}")
        
        # Try to parse the response
        try:
            name_mapping = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from the response if it's wrapped in other text
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                name_mapping = json.loads(json_match.group(0))
            else:
                raise ValueError("Could not parse JSON response")
        
        # Validate and clean the mapping
        valid_mapping = {}
        for filename, name in name_mapping.items():
            if isinstance(name, str) and name.strip():
                clean_name = name.strip().strip('"').strip("'")
                # Check if the name looks like a real name (not just a filename)
                if (clean_name.lower() not in ["unknown candidate", "no name found", "n/a", "unknown"] and 
                    len(clean_name.split()) >= 1 and 
                    not clean_name.lower().endswith(('.pdf', '.docx', '.doc', '.txt'))):
                    valid_mapping[filename] = clean_name
                else:
                    # Fallback to filename without extension
                    fallback_name = Path(filename).stem
                    valid_mapping[filename] = fallback_name
            else:
                # Fallback to filename without extension
                fallback_name = Path(filename).stem
                valid_mapping[filename] = fallback_name
        
        return valid_mapping
        
    except Exception as e:
        logger.error(f"Error in name extraction from parsed file: {e}")
        logger.error(f"Response was: {response if 'response' in locals() else 'No response'}")
        # Fallback: use filenames without extensions
        fallback_mapping = {filename: Path(filename).stem for filename in combined_resumes.keys()}
        logger.info(f"Using fallback mapping: {fallback_mapping}")
        return fallback_mapping



def call_openrouter(prompt: str, model_name: str = OPENROUTER_MODEL, temperature: float = 0.0) -> str:
    """Makes a call to the OpenRouter API."""
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
        match = re.search(r'\{.*\}', reply_text, re.DOTALL)
        if match:
            return match.group(0)
        return reply_text
    except requests.exceptions.Timeout:
        logger.error(f"[OpenRouter] Request to {model_name} timed out after 600 seconds.")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"[OpenRouter] Request to {model_name} failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"[OpenRouter] Response status: {e.response.status_code}, content: {e.response.text}")
        raise

def extract_criteria_from_job_description(job_description_text: str, workspace_name: str = None) -> List[Dict[str, Any]]:
    """
    Extract scoring criteria from job description using AI.
    Returns a list of criteria with default weights.
    """
    prompt = f"""
    You are an expert HR professional tasked with creating evaluation criteria for resume screening.
    
    Analyze the following job description and extract exactly 10 key criteria for evaluating candidate resumes.
    Each criterion should be specific, measurable, and relevant to the role.
    
    Job Description:
    {job_description_text}
    
    CRITICAL: You MUST return a valid JSON array starting with [ and ending with ]. 
    Do NOT return individual objects without the array brackets.
    Do NOT include any explanations, introductions, or additional text.
    
    Each object must have these exact fields:
    - "criterion": A clear, specific criterion name (string)
    - "description": A brief description of what this criterion evaluates (string)
    - "weight": Set to 10 for all criteria (integer)
    
    CORRECT format (with array brackets):
    [
        {{
            "criterion": "Technical Skills",
            "description": "Relevant technical skills and technologies",
            "weight": 10
        }},
        {{
            "criterion": "Experience Level",
            "description": "Years of relevant work experience",
            "weight": 10
        }}
    ]
    
    WRONG format (without array brackets):
    {{
        "criterion": "Technical Skills",
        "description": "Relevant technical skills and technologies",
        "weight": 10
    }}
    
    Focus on criteria that are:
    1. Specific to the role requirements
    2. Measurable from resume content
    3. Important for job performance
    4. Cover technical, soft skills, and experience aspects
    
    Return ONLY the JSON array with [ and ] brackets, no other text.
    """
    
    try:
        response = call_openrouter(prompt, temperature=0.1)
        logger.info(f"Raw LLM response for criteria extraction: {response}")
        
        # Save raw response for debugging
        if workspace_name:
            from pathlib import Path
            raw_response_file = Path(__file__).resolve().parent.parent.parent / "data" / workspace_name / "raw_criteria_response.json"
            raw_response_file.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_response_file, "w") as f:
                json.dump({
                    "raw_response": response,
                    "job_description": job_description_text,
                    "timestamp": time.time()
                }, f, indent=2)
        
        # Clean the response - remove markdown code blocks if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        
        cleaned_response = cleaned_response.strip()
        
        # Try to parse the JSON
        try:
            criteria_data = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Cleaned response: {cleaned_response}")
            
            # Try to extract JSON using regex
            import re
            
            # First try to find a JSON array
            json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
            if json_match:
                try:
                    criteria_data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    raise ValueError("Could not extract valid JSON array from response")
            else:
                # If no array found, try to extract individual objects and wrap them in an array
                # Look for patterns like {"criterion": "...", "description": "...", "weight": ...}
                object_pattern = r'\{[^{}]*"criterion"[^{}]*\}'
                matches = re.findall(object_pattern, cleaned_response, re.DOTALL)
                
                if matches:
                    try:
                        # Parse each object and combine into an array
                        criteria_data = []
                        for match in matches:
                            obj = json.loads(match)
                            criteria_data.append(obj)
                        logger.info(f"Successfully extracted {len(criteria_data)} criteria objects from response")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing individual objects: {e}")
                        raise ValueError("Could not parse individual criteria objects")
                else:
                    raise ValueError("No JSON array or individual objects found in response")
        
        if not isinstance(criteria_data, list):
            logger.error("AI response is not a list format")
            raise ValueError("Response is not a list")
        
        # Validate and clean criteria
        valid_criteria = []
        for i, criterion in enumerate(criteria_data):
            if isinstance(criterion, dict) and "criterion" in criterion:
                valid_criterion = {
                    "criterion": str(criterion.get("criterion", f"Criterion {i+1}")).strip(),
                    "description": str(criterion.get("description", "")).strip(),
                    "weight": 10  # Set all criteria weights to 10 by default
                }
                valid_criteria.append(valid_criterion)
        
        # Ensure we have exactly 10 criteria
        while len(valid_criteria) < 10:
            valid_criteria.append({
                "criterion": f"Additional Criterion {len(valid_criteria) + 1}",
                "description": "Additional evaluation criterion",
                "weight": 10
            })
        
        logger.info(f"Successfully extracted {len(valid_criteria)} criteria from job description")
        return valid_criteria[:10]  # Return exactly 10 criteria
        
    except Exception as e:
        logger.error(f"Error extracting criteria from job description: {e}")
        logger.error(f"Raw response was: {response if 'response' in locals() else 'No response'}")
        
        # Return default criteria if AI extraction fails
        return [
            {"criterion": "Technical Skills", "description": "Relevant technical skills and technologies", "weight": 10},
            {"criterion": "Experience Level", "description": "Years of relevant work experience", "weight": 10},
            {"criterion": "Education", "description": "Educational background and qualifications", "weight": 10},
            {"criterion": "Project Experience", "description": "Relevant project work and achievements", "weight": 10},
            {"criterion": "Leadership", "description": "Leadership and management experience", "weight": 10},
            {"criterion": "Communication Skills", "description": "Communication and presentation abilities", "weight": 10},
            {"criterion": "Problem Solving", "description": "Analytical and problem-solving capabilities", "weight": 10},
            {"criterion": "Industry Knowledge", "description": "Knowledge of relevant industry and domain", "weight": 10},
            {"criterion": "Certifications", "description": "Professional certifications and training", "weight": 10},
            {"criterion": "Cultural Fit", "description": "Alignment with company culture and values", "weight": 10}
        ]


def load_resumes_from_parsed_file(parsed_file: Path) -> Dict[str, str]:
    """
    Load resume documents from parsed_resumes.jsonl file as fallback.
    
    Args:
        parsed_file (Path): Path to the parsed_resumes.jsonl file
        
    Returns:
        Dict[str, str]: Dictionary mapping filename to text content
    """
    resumes = {}
    try:
        with open(parsed_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    filename = data.get('file', '').split('/')[-1]  # Get just the filename
                    text = data.get('text', '')
                    if filename and text:
                        # Remove file extension for consistency
                        filename_without_ext = Path(filename).stem
                        resumes[filename_without_ext] = text
        logger.info(f"Loaded {len(resumes)} resumes from parsed file")
        return resumes
    except Exception as e:
        logger.error(f"Error loading resumes from parsed file: {e}")
        return {}


def get_resume_documents_from_qdrant(workspace_name: str) -> Dict[str, str]:
    """
    Retrieve all resume documents from Qdrant collection.
    
    Args:
        workspace_name (str): Name of the workspace
        
    Returns:
        Dict[str, str]: Dictionary mapping filename (without extension) to combined text content
    """
    collection_name = f"contract_docs_{workspace_name}"
    
    try:
        # Get all documents from the collection
        all_hits, _ = client.scroll(collection_name=collection_name, limit=10000)
        logger.info(f"Retrieved {len(all_hits)} documents from collection '{collection_name}'")
        
        # Debug: Log all source files to see what's in the collection
        source_files = set()
        for hit in all_hits:
            source_file = hit.payload.get("source_file", "")
            source_files.add(source_file)
        
        logger.info(f"Found source files in collection: {list(source_files)}")
        
        # Group documents by filename
        resume_docs = {}
        for hit in all_hits:
            source_file = hit.payload.get("source_file", "")
            text = hit.payload.get("text", "")
            
            logger.debug(f"Processing document: {source_file}")
            
            # Only include documents from the resumes directory or files that look like resumes
            if ("resumes" in source_file or 
                source_file.endswith(('.pdf', '.docx', '.doc', '.txt')) or
                "resume" in source_file.lower()):
                
                # Remove file extension for the key
                filename_without_ext = Path(source_file).stem
                
                if filename_without_ext not in resume_docs:
                    resume_docs[filename_without_ext] = []
                resume_docs[filename_without_ext].append(text)
                logger.debug(f"Added resume document: {filename_without_ext}")
        
        # Combine all chunks for each document
        combined_resumes = {}
        for filename, texts in resume_docs.items():
            combined_resumes[filename] = '\n'.join(texts)
            logger.info(f"Combined {len(texts)} chunks for resume: {filename}")
        
        logger.info(f"Found {len(combined_resumes)} resume documents: {list(combined_resumes.keys())}")
        
        # If no resumes found in Qdrant, try to load from parsed files as fallback
        if not combined_resumes:
            logger.warning(f"No resume documents found in Qdrant for workspace '{workspace_name}', trying parsed files...")
            try:
                parsed_file = WORKSPACE_ROOT / workspace_name / "parsed_resumes.jsonl"
                if parsed_file.exists():
                    combined_resumes = load_resumes_from_parsed_file(parsed_file)
                    logger.info(f"Loaded {len(combined_resumes)} resumes from parsed file: {list(combined_resumes.keys())}")
            except Exception as parse_error:
                logger.error(f"Error loading resumes from parsed file: {parse_error}")
        
        return combined_resumes
        
    except Exception as e:
        logger.error(f"Error retrieving resume documents from Qdrant for workspace '{workspace_name}': {e}")
        return {}

def score_multiple_resumes_batch(resume_texts: Dict[str, str], criteria: List[Dict[str, Any]], workspace_name: str) -> Dict[str, Any]:
    """
    Score multiple resumes against the given criteria in a single batch call.
    This is much more efficient for large numbers of resumes.
    """
    criteria_text = "\n".join([f"{i+1}. {c['criterion']} (Weight: {c['weight']}): {c['description']}" for i, c in enumerate(criteria)])
    
    # Prepare resume content for batch evaluation
    resumes_content = ""
    for i, (resume_name, resume_text) in enumerate(resume_texts.items(), 1):
        resumes_content += f"\n\n--- RESUME {i}: {resume_name} ---\n{resume_text}"
    
    prompt = f"""
    Evaluate ALL the following resumes against the given criteria and provide scores and rationales for each.
    
    Evaluation Criteria (with weights):
    {criteria_text}
    
    Resumes to evaluate:
    {resumes_content}
    
    For each resume, provide:
    1. A score out of 10 for each criterion (where 10 is excellent, 1 is poor)
    2. A brief rationale for each score
    3. An overall rationale summarizing the candidate's strengths and weaknesses
    4. Use the EXACT weights provided for each criterion
    
    Return a JSON object with the following structure:
    {{
        "resume_scores": [
            {{
                "resume_name": "<EXACT filename without extension>",
                "overall_score": <calculated weighted average score>,
                "overall_rationale": "<comprehensive summary of the candidate's profile, strengths, and areas for improvement>",
                "criteria_scores": [
                    {{
                        "criterion": "<criterion name>",
                        "score": <score out of 10>,
                        "weight": <EXACT weight from criteria>,
                        "weighted_score": <score * weight>,
                        "rationale": "<brief explanation of the score>"
                    }}
                ]
            }}
        ]
    }}
    
    IMPORTANT: 
    - Use the exact weights provided in the criteria. Do not change them.
    - Calculate the overall_score as the sum of weighted_scores divided by the sum of weights.
    - Evaluate ALL resumes in the list.
    - Keep rationales concise but informative.
    - The overall_rationale should provide a comprehensive assessment of the candidate's profile.
    - Use the EXACT filename as resume_name (e.g., "retreat&regroup", "NJ_s_resume (3)"), not "RESUME 1", "RESUME 2", etc.
    """
    

    
    try:
        response = call_openrouter(prompt)
        scoring_result = json.loads(response)
        
        # Validate the response structure
        if not isinstance(scoring_result, dict) or "resume_scores" not in scoring_result:
            raise ValueError("Invalid response format - missing resume_scores")
        
        # Create a mapping of criterion names to their actual weights
        criteria_weights = {c['criterion']: c['weight'] for c in criteria}
        
        # Validate and clean each resume score
        valid_resume_scores = []
        total_score = 0
        best_score = 0
        worst_score = 10
        best_resume = ""
        worst_resume = ""
        
        # Extract candidate names from parsed file for efficiency
        candidate_names = extract_candidate_names_from_parsed_file(workspace_name)
        
        for resume_score_data in scoring_result.get("resume_scores", []):
            if not isinstance(resume_score_data, dict) or "resume_name" not in resume_score_data:
                continue
                
            original_filename = resume_score_data.get("resume_name", "")
            criteria_scores = resume_score_data.get("criteria_scores", [])
            
            # Get candidate name from batch extraction
            candidate_name = candidate_names.get(original_filename, original_filename)
            
            # Validate and clean each criterion score
            valid_criteria_scores = []
            total_weighted_score = 0
            total_weight = 0
            
            for score_data in criteria_scores:
                if isinstance(score_data, dict) and "criterion" in score_data:
                    criterion_name = score_data.get("criterion", "")
                    score = min(max(score_data.get("score", 5), 1), 10)
                    
                    # Use the actual weight from criteria
                    actual_weight = criteria_weights.get(criterion_name, 5)
                    weighted_score = score * actual_weight
                    
                    valid_criteria_score = {
                        "criterion": criterion_name,
                        "score": score,
                        "weight": actual_weight,
                        "weighted_score": weighted_score,
                        "rationale": score_data.get("rationale", "No rationale provided")
                    }
                    valid_criteria_scores.append(valid_criteria_score)
                    total_weighted_score += weighted_score
                    total_weight += actual_weight
            
            # Calculate overall score for this resume
            overall_score = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0
            
            valid_resume_score = {
                "resume_name": candidate_name,
                "original_filename": original_filename,
                "overall_score": overall_score,
                "overall_rationale": resume_score_data.get("overall_rationale", "No overall rationale provided"),
                "criteria_scores": valid_criteria_scores
            }
            valid_resume_scores.append(valid_resume_score)
            
            # Update summary statistics
            total_score += overall_score
            if overall_score > best_score:
                best_score = overall_score
                best_resume = candidate_name
            if overall_score < worst_score:
                worst_score = overall_score
                worst_resume = candidate_name
        
        # No longer generating AI-powered summary bullets - using simple top candidates display instead
        best_resume_bullets = []
        
        # Calculate summary statistics
        summary = {
            "total_resumes": len(valid_resume_scores),
            "average_score": round(total_score / len(valid_resume_scores), 2) if valid_resume_scores else 0,
            "highest_score": best_score,
            "lowest_score": worst_score,
            "best_resume": best_resume,
            "worst_resume": worst_resume,
            "best_resume_bullets": best_resume_bullets
        }
        
        return {
            "resume_scores": valid_resume_scores,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Error in batch scoring resumes: {e}")
        # Return empty results if batch scoring fails
        return {
            "resume_scores": [],
            "summary": {
                "total_resumes": 0,
                "average_score": 0,
                "highest_score": 0,
                "lowest_score": 0,
                "best_resume": "",
                "worst_resume": "",
                "best_resume_bullets": []
            }
        }





def score_multiple_resumes(workspace_name: str, criteria: List[Dict[str, Any]], resume_texts: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Score multiple resumes against the given criteria.
    Uses batch scoring for efficiency, falls back to individual scoring if needed.
    """
    # If resume_texts not provided, get from Qdrant (for backward compatibility)
    if resume_texts is None:
        resume_texts = get_resume_documents_from_qdrant(workspace_name)
    
    if not resume_texts:
        logger.warning(f"No resume documents found for workspace '{workspace_name}'")
        return {
            "resume_scores": [],
            "summary": {
                "total_resumes": 0,
                "average_score": 0,
                "highest_score": 0,
                "lowest_score": 0,
                "best_resume": "",
                "worst_resume": "",
                "best_resume_bullets": []
            }
        }
    
    # Use batch scoring for efficiency
    return score_multiple_resumes_batch(resume_texts, criteria, workspace_name)
