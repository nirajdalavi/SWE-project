# services/vendor_recommendation_service.py
import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import requests
import time
from services.custom_perplexity_tool import CustomPerplexitySearchTool
from services.airbyte_enrichment_service import AirbyteEnrichmentService
from services.vendor_analysis_service import VendorAnalysisService

logger = logging.getLogger(__name__)
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

def validate_vendor_websites(recommendations: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and format website URLs for vendor recommendations.
    """
    if "recommendations" in recommendations:
        for vendor in recommendations["recommendations"]:
            if "website" not in vendor or not vendor["website"]:
                vendor["website"] = "N/A"
            elif vendor["website"] != "N/A" and not vendor["website"].startswith(("http://", "https://")):
                # If website is provided but doesn't start with http/https, prepend https://
                vendor["website"] = "https://" + vendor["website"]
    return recommendations


def extract_vendor_names_from_prompt(prompt: str) -> List[str]:
    """
    Extract potential vendor names from a prompt to exclude their websites.
    Enhanced to better detect vendor names from project requirements.
    """
    vendor_names = []
    import re
    
    # Look for quoted strings that might be vendor names
    quoted_names = re.findall(r'"([^"]+)"', prompt)
    vendor_names.extend(quoted_names)
    
    # Look for common vendor names mentioned in the text
    common_vendors = [
        'Salesforce', 'HubSpot', 'Microsoft Dynamics', 'Microsoft', 'Oracle', 'SAP', 'Workday', 
        'ServiceNow', 'Zoho', 'Pipedrive', 'Freshworks', 'Monday.com', 'Creatio', 'SugarCRM',
        'Pega', 'Appian', 'OutSystems', 'Mendix', 'Salesforce', 'Adobe', 'IBM', 'Amazon',
        'Google', 'Apple', 'Meta', 'Twitter', 'LinkedIn', 'Slack', 'Zoom', 'Dropbox',
        'Box', 'Atlassian', 'Jira', 'Confluence', 'Trello', 'Asana', 'Notion', 'Airtable'
    ]
    
    prompt_lower = prompt.lower()
    for vendor in common_vendors:
        if vendor.lower() in prompt_lower:
            vendor_names.append(vendor)
    
    # Look for "vendors like X, Y, Z" patterns
    like_pattern = re.findall(r'vendors?\s+like\s+([^.]+)', prompt_lower)
    for match in like_pattern:
        # Split by common separators and clean up
        vendors_in_match = re.split(r'[,;]|\s+or\s+|\s+and\s+', match)
        for vendor in vendors_in_match:
            vendor = vendor.strip()
            if vendor and len(vendor) > 2:
                vendor_names.append(vendor.title())
    
    # Look for capitalized words that might be company names
    capitalized_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', prompt)
    # Filter out common words that aren't company names
    common_words = {
        'Project', 'Requirements', 'Industry', 'Budget', 'Timeline', 'Location', 'Vendor', 
        'Company', 'Technology', 'Software', 'Service', 'Solution', 'Looking', 'Need',
        'Team', 'Should', 'Provide', 'Advanced', 'Reporting', 'Capabilities', 'Integration',
        'Existing', 'Email', 'Marketing', 'Tools', 'Cloud', 'Based', 'Sales', 'Looking'
    }
    potential_vendors = [phrase for phrase in capitalized_phrases if phrase not in common_words and len(phrase.split()) <= 3]
    vendor_names.extend(potential_vendors)
    
    return list(set(vendor_names))  # Remove duplicates


def format_perplexity_citations(citations) -> List[Dict[str, str]]:
    """
    Convert Perplexity's citations to proper citation format with titles.
    Handles both URL strings and citation objects.
    Note: Vendor websites should already be excluded by prompt instructions.
    """
    if not citations:
        return []
    
    formatted_citations = []
    
    for citation in citations:
        # Handle different citation formats
        if isinstance(citation, str):
            url = citation
        elif isinstance(citation, dict) and 'url' in citation:
            url = citation['url']
        else:
            logger.warning(f"Unexpected citation format: {type(citation)} - {citation}")
            continue
            
        if not url or not isinstance(url, str):
            continue
            
        # Extract domain and path to create a meaningful title
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if not domain_match:
            continue
            
        domain = domain_match.group(1)
        
        # Create a title based on the domain and URL structure
        if 'gartner.com' in domain:
            title = "Gartner Research and Analysis"
        elif 'forrester.com' in domain:
            title = "Forrester Research and Market Analysis"
        elif 'capterra.com' in domain:
            title = "Capterra Software Reviews and Comparisons"
        elif 'techradar.com' in domain:
            title = "TechRadar Technology Reviews"
        elif 'pcmag.com' in domain:
            title = "PCMag Software Reviews and Recommendations"
        elif 'zdnet.com' in domain:
            title = "ZDNet Technology Analysis and Reviews"
        elif 'cnet.com' in domain:
            title = "CNET Technology Reviews and Comparisons"
        elif 'venturebeat.com' in domain:
            title = "VentureBeat Technology News and Analysis"
        elif 'techcrunch.com' in domain:
            title = "TechCrunch Technology News and Reviews"
        else:
            # Generic title based on domain
            title = f"Research and Analysis from {domain}"
        
        formatted_citations.append({
            "title": title,
            "url": url
        })
    
    return formatted_citations


def determine_vendor_type(project_requirements: str, industry: str) -> str:
    """
    Analyze project requirements to determine the appropriate vendor type.
    This helps distinguish between service providers and technology vendors.
    """
    requirements_lower = project_requirements.lower()
    
    # Keywords that suggest service providers (actual businesses)
    service_keywords = [
        'salon', 'spa', 'restaurant', 'hotel', 'clinic', 'hospital', 'school', 'university',
        'gym', 'fitness', 'retail', 'store', 'shop', 'cafe', 'bar', 'bakery', 'pharmacy',
        'dentist', 'lawyer', 'accountant', 'consultant', 'agency', 'studio', 'gallery',
        'theater', 'cinema', 'museum', 'library', 'bank', 'insurance', 'real estate',
        'travel', 'tour', 'transport', 'cleaning', 'maintenance', 'repair', 'construction'
    ]
    
    # Keywords that suggest technology/software needs
    tech_keywords = [
        'software', 'system', 'platform', 'app', 'application', 'management', 'crm',
        'erp', 'pos', 'inventory', 'booking', 'scheduling', 'payment', 'billing',
        'website', 'ecommerce', 'digital', 'online', 'automation', 'integration',
        'api', 'database', 'cloud', 'saas', 'solution', 'tool', 'service provider',
        'vendor', 'supplier', 'equipment', 'hardware', 'technology', 'it', 'tech'
    ]
    
    # Keywords that suggest equipment/supplies
    equipment_keywords = [
        'equipment', 'furniture', 'supplies', 'products', 'materials', 'tools',
        'machines', 'devices', 'instruments', 'appliances', 'fixtures', 'furnishings'
    ]
    
    # Count matches for each category
    service_matches = sum(1 for keyword in service_keywords if keyword in requirements_lower)
    tech_matches = sum(1 for keyword in tech_keywords if keyword in requirements_lower)
    equipment_matches = sum(1 for keyword in equipment_keywords if keyword in requirements_lower)
    
    # Determine vendor type based on matches and industry
    if industry.lower() in ['technology', 'software', 'it']:
        return "TECHNOLOGY_VENDORS"
    elif tech_matches > service_matches and tech_matches > equipment_matches:
        return "TECHNOLOGY_VENDORS"
    elif equipment_matches > service_matches and equipment_matches > tech_matches:
        return "EQUIPMENT_SUPPLIERS"
    elif service_matches > 0:
        return "SERVICE_PROVIDERS"
    else:
        # Default to technology vendors if unclear
        return "TECHNOLOGY_VENDORS"


def call_perplexity(prompt: str, max_tokens: int = 1000) -> dict:
    """Makes a call to the Perplexity API and returns both content and citations."""
    try:
        if not PERPLEXITY_API_KEY:
            raise Exception("PERPLEXITY_API_KEY environment variable is not set. Please set it to use the Perplexity API.")
        
        logger.info(f"[Vendor Recommendation] Sending request to Perplexity, prompt length: {len(prompt)}")
        start_request_time = time.time()
        
        perplexity_search_tool = CustomPerplexitySearchTool(
            api_key=PERPLEXITY_API_KEY,
            max_tokens=max_tokens,
            timeout=60  # 60 second timeout for complex vendor recommendation requests
        )
        
        search_response = perplexity_search_tool.search(query=prompt)
        logger.info(f"[Vendor Recommendation] Search response type: {type(search_response)}")
        logger.info(f"[Vendor Recommendation] Search response attributes: {dir(search_response)}")
        
        if hasattr(search_response, 'error') and search_response.error:
            raise Exception(f"Perplexity API error: {search_response.error}")
        
        response = search_response.content
        citations = search_response.citations if hasattr(search_response, 'citations') else []
        
        logger.info(f"[Vendor Recommendation] Response content type: {type(response)}")
        logger.info(f"[Vendor Recommendation] Response content length: {len(response) if response else 'None'}")
        logger.info(f"[Vendor Recommendation] Citations count: {len(citations) if citations else 0}")
        logger.info(f"[Vendor Recommendation] Citations structure: {citations}")
        if citations:
            logger.info(f"[Vendor Recommendation] First citation type: {type(citations[0])}")
            logger.info(f"[Vendor Recommendation] First citation content: {citations[0]}")
        
        if response is None:
            raise Exception("Perplexity API returned None response. Please check your API key and try again.")
        
        logger.info(f"[Vendor Recommendation] Response received in {time.time() - start_request_time:.2f}s.")
        return {
            "content": response,
            "citations": citations
        }
    except Exception as e:
        logger.error(f"[Vendor Recommendation] Request to Perplexity failed: {e}")
        raise

def generate_enhanced_vendor_recommendations(
    project_requirements: str,
    industry: str = "general",
    location_preference: str = "any",
    vendor_count: int = 5,
    workspace_name: str = None,
    preference: str = "balanced",
    vendor_type: str = "auto",
    enable_reddit_analysis: bool = False,
    enable_linkedin_analysis: bool = False,
    enable_google_reviews: bool = False
) -> Dict[str, Any]:
    """
    Generate enhanced vendor recommendations with deep analysis from external sources.
    
    Args:
        project_requirements: Detailed description of the project requirements
        industry: Industry sector (e.g., "technology", "healthcare", "construction")
        location_preference: Geographic preference for vendors
        vendor_count: Number of vendors to recommend (default: 5)
        workspace_name: Workspace name for metrics tracking
        preference: Scoring preference - "technical_competence", "cost_effective", or "balanced"
        vendor_type: Vendor type - "auto", "service_providers", "technology_vendors", "equipment_suppliers"
        enable_reddit_analysis: Whether to enable Reddit data analysis
        enable_linkedin_analysis: Whether to enable LinkedIn data analysis
        enable_google_reviews: Whether to enable Google Places reviews analysis
    
    Returns:
        Dictionary containing enhanced vendor recommendations with deep analysis
    """
    try:
        start_time = time.time()
        logger.info(f"Starting enhanced vendor recommendations for {vendor_count} vendors")
        
        # Step 1: Get initial recommendations from Perplexity
        initial_recommendations = generate_vendor_recommendations(
            project_requirements=project_requirements,
            industry=industry,
            location_preference=location_preference,
            vendor_count=vendor_count,
            workspace_name=workspace_name,
            preference=preference,
            vendor_type=vendor_type
        )
        
        if not initial_recommendations.get("success", False):
            return initial_recommendations
        
        # Step 2: Enrich vendor data if any deep analysis is enabled
        if enable_reddit_analysis or enable_linkedin_analysis or enable_google_reviews:
            logger.info(f"Starting vendor data enrichment and deep analysis (Reddit: {enable_reddit_analysis}, LinkedIn: {enable_linkedin_analysis}, Google Reviews: {enable_google_reviews})")
            enrichment_service = AirbyteEnrichmentService()
            analysis_service = VendorAnalysisService()
            
            enhanced_recommendations = []
            
            for vendor in initial_recommendations["data"]["recommendations"]:
                try:
                    # Enrich vendor data from external sources
                    external_data = enrichment_service.enrich_vendor_data(
                        vendor_name=vendor["vendor_name"],
                        website=vendor.get("website"),
                        location=vendor.get("location"),
                        enable_reddit=enable_reddit_analysis,
                        enable_linkedin=enable_linkedin_analysis,
                        enable_google_reviews=enable_google_reviews
                    )
                    
                    # Analyze enriched data
                    deep_analysis = analysis_service.analyze_enriched_vendor_data(
                        vendor_data=vendor,
                        external_data=external_data
                    )
                    
                    # Log whether Perplexity was called
                    perplexity_called = deep_analysis.get("analysis_metadata", {}).get("perplexity_called", True)
                    if not perplexity_called:
                        logger.info(f"Skipped Perplexity call for {vendor['vendor_name']} - no meaningful external data found")
                    
                    # Combine original vendor data with enriched analysis
                    enhanced_vendor = {
                        **vendor,  # Original Perplexity data
                        "external_data": external_data,
                        "deep_analysis": deep_analysis["analysis"],
                        "analysis_metadata": deep_analysis["analysis_metadata"]
                    }
                    
                    enhanced_recommendations.append(enhanced_vendor)
                    
                except Exception as e:
                    logger.error(f"Error enriching vendor {vendor['vendor_name']}: {e}")
                    # Fallback to original vendor data if enrichment fails
                    enhanced_vendor = {
                        **vendor,
                        "external_data": {"error": str(e)},
                        "deep_analysis": {
                            "error": "Deep analysis failed",
                            "reddit_insights": "Analysis unavailable",
                            "linkedin_insights": "Analysis unavailable",
                            "overall_assessment": "Limited analysis due to data enrichment failure"
                        },
                        "analysis_metadata": {"error": str(e)}
                    }
                    enhanced_recommendations.append(enhanced_vendor)
            
            # Update the recommendations with enhanced data
            initial_recommendations["data"]["recommendations"] = enhanced_recommendations
            
            # Add metadata about the enhancement process
            sources_used = []
            if enable_reddit_analysis:
                sources_used.append("reddit")
            if enable_linkedin_analysis:
                sources_used.append("linkedin")
                
            initial_recommendations["enhancement_metadata"] = {
                "deep_analysis_enabled": True,
                "sources_used": sources_used,
                "reddit_enabled": enable_reddit_analysis,
                "linkedin_enabled": enable_linkedin_analysis,
                "total_enhancement_time": time.time() - start_time,
                "vendors_enhanced": len(enhanced_recommendations)
            }
        else:
            initial_recommendations["enhancement_metadata"] = {
                "deep_analysis_enabled": False,
                "sources_used": [],
                "reddit_enabled": False,
                "linkedin_enabled": False,
                "total_enhancement_time": 0,
                "vendors_enhanced": 0
            }
        
        total_time = time.time() - start_time
        logger.info(f"Enhanced vendor recommendations completed in {total_time:.2f}s")
        
        return initial_recommendations
        
    except Exception as e:
        logger.error(f"Error generating enhanced vendor recommendations: {e}")
        return {
            "success": False,
            "error": str(e),
            "citations": [],
            "timestamp": time.time()
        }


def generate_vendor_recommendations(
    project_requirements: str,
    industry: str = "general",
    location_preference: str = "any",
    vendor_count: int = 5,
    workspace_name: str = None,
    preference: str = "balanced",
    vendor_type: str = "auto"
) -> Dict[str, Any]:
    """
    Generate vendor recommendations based on project requirements using Perplexity.
    
    Args:
        project_requirements: Detailed description of the project requirements
        industry: Industry sector (e.g., "technology", "healthcare", "construction")
        location_preference: Geographic preference for vendors
        vendor_count: Number of vendors to recommend (default: 5)
        workspace_name: Workspace name for metrics tracking
        preference: Scoring preference - "technical_competence", "cost_effective", or "balanced"
        vendor_type: Vendor type - "auto", "service_providers", "technology_vendors", "equipment_suppliers"
    
    Returns:
        Dictionary containing vendor recommendations and analysis
    """
    try:
        start_time = time.time()
        
        # Enhanced context analysis to determine vendor type
        if vendor_type == "auto":
            determined_vendor_type = determine_vendor_type(project_requirements, industry)
        else:
            # Map frontend values to backend values
            vendor_type_mapping = {
                "service_providers": "SERVICE_PROVIDERS",
                "technology_vendors": "TECHNOLOGY_VENDORS", 
                "equipment_suppliers": "EQUIPMENT_SUPPLIERS"
            }
            determined_vendor_type = vendor_type_mapping.get(vendor_type, "TECHNOLOGY_VENDORS")
        
        # Build vendor type specific instructions
        vendor_type_instruction = ""
        if determined_vendor_type == "SERVICE_PROVIDERS":
            vendor_type_instruction = """
VENDOR TYPE: SERVICE_PROVIDERS
IMPORTANT: You are looking for actual service businesses (like salons, spas, restaurants, etc.) that provide services to customers, NOT technology vendors or software solutions. Focus on finding real service businesses that operate in the specified industry.
"""
        elif determined_vendor_type == "EQUIPMENT_SUPPLIERS":
            vendor_type_instruction = """
VENDOR TYPE: EQUIPMENT_SUPPLIERS
IMPORTANT: You are looking for companies that supply equipment, furniture, tools, or materials for the specified industry. Focus on finding suppliers of physical products and equipment.
"""
        else:  # TECHNOLOGY_VENDORS
            vendor_type_instruction = """
VENDOR TYPE: TECHNOLOGY_VENDORS
IMPORTANT: You are looking for technology companies, software providers, or digital solutions for the specified industry. Focus on finding software, platforms, or technology services.
"""
        
        
        # Build preference instruction
        preference_instruction = ""
        if preference == "technical_competence":
            preference_instruction = """
Scoring Preference: Prioritize vendors with superior technical expertise, innovation, and advanced capabilities. 
Score vendors higher for technical excellence, cutting-edge solutions, and proven technical track record.
Cost should be a secondary consideration.
"""
        elif preference == "cost_effective":
            preference_instruction = """
Scoring Preference: Prioritize vendors offering the best value for money and cost-effective solutions.
Score vendors higher for competitive pricing, good value proposition, and cost efficiency.
Technical capabilities should be adequate but not necessarily cutting-edge.
"""
        else:  # balanced
            preference_instruction = """
Scoring Preference: Balance technical competence with cost-effectiveness.
Score vendors based on the best overall value considering both technical capabilities and cost.
"""
        
        # Extract vendor names to exclude their websites from search
        vendor_names = extract_vendor_names_from_prompt(project_requirements)
        
        # Always include general source restrictions
        exclude_instruction = """
        
        CRITICAL SOURCE RESTRICTION - MUST BE FOLLOWED:
        - AVOID using information from vendor websites as they may be biased
        - DO NOT use vendor blogs, press releases, or marketing content from vendor websites
        - ONLY use independent third-party sources like:
          * Industry analyst reports (Gartner, Forrester, IDC)
          * Technology review sites (Capterra, G2, TrustRadius, Software Advice)
          * Independent technology publications (TechRadar, PCMag, ZDNet, CNET, VentureBeat, TechCrunch)
          * News sites and industry publications
          * Academic research and case studies
        - If you find information on a vendor's website, find the same information from an independent source instead
        """
        
        # Add specific vendor exclusions if vendor names are detected
        if vendor_names:
            vendor_list = ", ".join(vendor_names)
            exclude_instruction += f"""
        - ABSOLUTELY DO NOT use or cite information from the official websites of these specific vendors: {vendor_list}
        - DO NOT reference content from any .com domains that belong to these vendors (e.g., microsoft.com, salesforce.com, hubspot.com)
        """
        
        prompt = f"""
        You are an expert vendor recommendation specialist. Based on the following project requirements, provide {vendor_count} detailed vendor recommendations AND exactly 3 additional alternate vendors with limited details.
        
        CITATION NOTE:
        - Perplexity will automatically provide real citations from its web search
        - Do NOT generate fake citations in the JSON response
        - Focus on providing accurate vendor recommendations based on real information{exclude_instruction}

        {vendor_type_instruction}
        Project Requirements: {project_requirements}
        Industry: {industry}
        Location Preference: {location_preference}{preference_instruction}

        IMPORTANT: You MUST include both "recommendations" and "alternate_vendors" arrays in your response.

        Please provide your response in the following JSON format:
        {{
            "summary": "Brief overview of the project and key requirements",
            "recommendations": [
                {{
                    "vendor_name": "Vendor Name",
                    "company_size": "Small/Medium/Large",
                    "specialization": "Primary areas of expertise",
                    "strengths": ["Strength 1", "Strength 2", "Strength 3"],
                    "experience": "Years of experience in this field",
                    "location": "Primary location",
                    "website": "https://www.vendorwebsite.com",
                    "risk_factors": ["Risk 1", "Risk 2"],
                    "recommendation_score": 8.5,
                    "rationale": "Why this vendor is recommended"
                }}
            ],
            "alternate_vendors": [
                {{
                    "vendor_name": "Alternate Vendor Name 1",
                    "domain": "Industry/Domain specialization",
                    "recommendation_score": 7.5,
                    "website": "https://www.alternatevendor1.com"
                }},
                {{
                    "vendor_name": "Alternate Vendor Name 2",
                    "domain": "Industry/Domain specialization",
                    "recommendation_score": 7.2,
                    "website": "https://www.alternatevendor2.com"
                }},
                {{
                    "vendor_name": "Alternate Vendor Name 3",
                    "domain": "Industry/Domain specialization",
                    "recommendation_score": 7.0,
                    "website": "https://www.alternatevendor3.com"
                }}
            ]

        }}

        Guidelines:
        1. Ensure all vendors are real companies with verifiable information
        2. Provide balanced recommendations across different company sizes
        3. Include both established and emerging vendors
        4. Consider the specific industry requirements
        5. Include relevant risk factors for each vendor
        6. Score vendors on a scale of 1-10 based on the specified preference (technical competence, cost effectiveness, or balanced)
        7. Include the official website URL for each vendor (use "N/A" if not available). Website URLs should be complete URLs starting with http:// or https://
        8. For alternate_vendors: Provide exactly 3 additional vendors with only vendor_name, domain (industry specialization), recommendation_score, and website. These should be different from the main recommendations and offer alternative options.

        Return ONLY the JSON response without any additional text or explanations.
        """

        perplexity_response = call_perplexity(prompt, max_tokens=2000)
        response = perplexity_response["content"]
        perplexity_citations = perplexity_response["citations"]
        logger.info(f"Vendor recommendation response received: {len(response)} characters")
        logger.info(f"Perplexity citations received: {len(perplexity_citations)} sources")
        logger.info(f"Raw LLM response (first 500 chars): {response[:500]}")

        # Calculate response time
        response_time = time.time() - start_time

        # Clean the response - remove markdown code blocks if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        
        cleaned_response = cleaned_response.strip()
        
        # Parse the JSON response
        try:
            recommendations = json.loads(cleaned_response)
            logger.info(f"Parsed JSON keys: {list(recommendations.keys())}")
            
            # Extract citations from the LLM response if available
            llm_citations = recommendations.get("citations", [])
            
            # Remove citations from the recommendations data to keep it clean
            if "citations" in recommendations:
                del recommendations["citations"]
            
            # Validate and format website URLs
            recommendations = validate_vendor_websites(recommendations)
            
            # Prioritize Perplexity's real citations over LLM-generated ones
            # Perplexity citations are from actual web search, LLM citations are fabricated
            if perplexity_citations:
                try:
                    # Format Perplexity citations to include proper titles
                    # Note: Vendor websites should already be excluded by the prompt instructions
                    final_citations = format_perplexity_citations(perplexity_citations)
                    logger.info(f"Using Perplexity's real citations: {len(final_citations)} sources")
                except Exception as e:
                    logger.error(f"Error formatting Perplexity citations: {e}")
                    # Fall back to using Perplexity citations as-is
                    final_citations = perplexity_citations
            elif llm_citations:
                final_citations = llm_citations
                logger.info(f"Falling back to LLM-generated citations: {len(llm_citations)} sources")
            else:
                final_citations = []
                logger.info("No citations available from either source")
            
            # Save metrics if workspace_name is provided
            if workspace_name:
                save_vendor_metrics(workspace_name, response_time)
                # Save vendor recommendations to file for email functionality
                save_vendor_recommendations(workspace_name, recommendations)
            
            return {
                "success": True,
                "data": recommendations,
                "citations": final_citations,
                "timestamp": time.time()
            }
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for vendor recommendations: {e}")
            logger.error(f"Cleaned response: {cleaned_response}")
            
            # Try to extract JSON using regex
            import re
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                try:
                    recommendations = json.loads(json_match.group(0))
                    
                    # Validate and format website URLs
                    recommendations = validate_vendor_websites(recommendations)
                    
                    return {
                        "success": True,
                        "data": recommendations,
                        "citations": perplexity_citations if perplexity_citations else [],
                        "timestamp": time.time()
                    }
                except json.JSONDecodeError:
                    pass
            
            return {
                "success": False,
                "error": "Failed to parse vendor recommendations",
                "raw_response": cleaned_response,
                "citations": perplexity_citations if perplexity_citations else [],
                "timestamp": time.time()
            }

    except Exception as e:
        logger.error(f"Error generating vendor recommendations: {e}")
        return {
            "success": False,
            "error": str(e),
            "citations": [],
            "timestamp": time.time()
        }


def save_vendor_metrics(workspace_name: str, response_time: float):
    """
    Save vendor recommendation metrics to the workspace metrics file.
    """
    try:
        from pathlib import Path
        from datetime import datetime
        
        # Define workspace root path
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
        WORKSPACE_ROOT = PROJECT_ROOT / "data"
        
        metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
        now = datetime.now().isoformat()
        mode = "Vendor recommendations"

        new_record = {
            "timestamp": now,
            "mode": mode,
            "response_time": round(response_time, 2)
        }
        
        metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
            except Exception:
                logger.warning(f"Could not load existing metrics from {metrics_file}, starting new list.")
                metrics = []
        
        metrics.append(new_record)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
        
    except Exception as e:
        logger.error(f"Error saving vendor metrics for workspace '{workspace_name}': {e}")


def save_vendor_recommendations(workspace_name: str, recommendations: Dict[str, Any]):
    """
    Save vendor recommendations to a JSON file in the workspace directory.
    """
    try:
        from pathlib import Path
        
        # Define workspace root path
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
        WORKSPACE_ROOT = PROJECT_ROOT / "data"
        
        results_file = WORKSPACE_ROOT / workspace_name / "vendor_recommendations.json"
        
        # Ensure workspace directory exists
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save recommendations to file
        with open(results_file, "w") as f:
            json.dump(recommendations, f, indent=2)
        
        logger.info(f"Vendor recommendations saved to {results_file}")
        
    except Exception as e:
        logger.error(f"Error saving vendor recommendations for workspace '{workspace_name}': {e}")