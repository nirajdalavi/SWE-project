# services/vendor_comparison_service.py
import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from services.custom_perplexity_tool import CustomPerplexitySearchTool

logger = logging.getLogger(__name__)
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

class VendorComparisonService:
    """
    Service to compare multiple vendors based on LLM-generated criteria.
    """
    
    def __init__(self):
        self.perplexity_api_key = PERPLEXITY_API_KEY
        logger.info(f"VendorComparisonService initialized with API key: {bool(self.perplexity_api_key)}")
    
    def compare_vendors(
        self, 
        vendors: List[Dict[str, str]], 
        workspace_name: str = None
    ) -> Dict[str, Any]:
        """
        Compare multiple vendors based on LLM-generated criteria.
        
        Args:
            vendors: List of vendor dictionaries with 'name' and 'location' keys
            workspace_name: Optional workspace name for metrics tracking
        
        Returns:
            Dictionary containing comparison results
        """
        try:
            start_time = time.time()
            logger.info(f"Starting vendor comparison for {len(vendors)} vendors")
            
            # Generate comparison criteria using LLM
            criteria = self._generate_comparison_criteria(vendors)
            
            # Compare vendors based on generated criteria
            comparison_results = self._compare_vendors_by_criteria(vendors, criteria)
            
            comparison_time = time.time() - start_time
            logger.info(f"Vendor comparison completed in {comparison_time:.2f}s")
            
            result = {
                "success": True,
                "vendors": vendors,
                "criteria": criteria,
                "comparison_results": comparison_results,
                "metadata": {
                    "workspace_name": workspace_name
                }
            }
            
            # Save metrics if workspace_name is provided
            if workspace_name:
                self._save_comparison_metrics(workspace_name, comparison_time)
                self._save_comparison_results(workspace_name, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error comparing vendors: {e}")
            return {
                "success": False,
                "error": str(e),
                "vendors": vendors,
                "metadata": {
                    "workspace_name": workspace_name
                }
            }
    
    def _generate_comparison_criteria(
        self, 
        vendors: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Generate comparison criteria using LLM based on vendor names and locations.
        """
        try:
            vendor_names = [vendor['name'] for vendor in vendors]
            vendor_locations = [vendor.get('location', 'Unknown') for vendor in vendors]
            
            # Build prompt for criteria generation
            prompt = self._build_criteria_generation_prompt(vendor_names, vendor_locations)
            
            # Call LLM for criteria generation
            criteria_response = self._call_llm_for_criteria(prompt)
            
            return criteria_response
            
        except Exception as e:
            logger.error(f"Error generating comparison criteria: {e}")
            # Fallback to basic criteria
            return self._get_fallback_criteria()
    
    def _build_criteria_generation_prompt(
        self, 
        vendor_names: List[str], 
        vendor_locations: List[str]
    ) -> str:
        """
        Build prompt for LLM to generate comparison criteria.
        """
        vendor_info = []
        for i, (name, location) in enumerate(zip(vendor_names, vendor_locations), 1):
            vendor_info.append(f"{i}. {name} (Location: {location})")
        
        vendor_list = "\n".join(vendor_info)
        
        prompt = f"""
You are an expert vendor comparison specialist. Based on the following vendors, generate comprehensive comparison criteria that would be most relevant for evaluating and comparing these vendors.

VENDORS TO COMPARE:
{vendor_list}

Please generate 8-12 relevant comparison criteria that would be most useful for evaluating these vendors. Consider factors like:

1. Pricing and cost structure
2. Service quality and reliability
3. Technical capabilities and expertise
4. Customer support and service
5. Geographic coverage and availability
6. Company size and stability
7. Industry experience and track record
8. Innovation and technology adoption
9. Scalability and growth potential
10. Integration capabilities
11. Security and compliance
12. Customization options

For each criterion, provide:
- A clear, specific name
- A brief description of what to evaluate
- The evaluation method (e.g., "quantitative", "qualitative", "binary")

Return your response in the following JSON format:

{{
    "criteria": [
        {{
            "name": "Pricing Competitiveness",
            "description": "Compare pricing models, cost structure, and value for money",
            "evaluation_method": "quantitative",
            "category": "Cost"
        }},
        {{
            "name": "Service Quality",
            "description": "Evaluate reliability, performance, and customer satisfaction",
            "evaluation_method": "qualitative",
            "category": "Quality"
        }}
    ]
}}

Guidelines:
1. Focus on criteria that are most relevant to the specific vendors being compared
2. Consider the industry context and typical vendor evaluation factors
3. Include both objective (quantitative) and subjective (qualitative) criteria
4. Ensure criteria are specific and measurable where possible
5. Balance different aspects: cost, quality, service, technical capabilities, etc.
6. Consider both short-term and long-term factors

Return ONLY the JSON response without any additional text or explanations.
"""
        
        return prompt
    
    def _call_llm_for_criteria(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Call LLM (Perplexity) for criteria generation.
        """
        try:
            if not self.perplexity_api_key:
                raise Exception("PERPLEXITY_API_KEY environment variable is not set.")
            
            logger.info(f"Sending criteria generation request to Perplexity, prompt length: {len(prompt)}")
            
            perplexity_search_tool = CustomPerplexitySearchTool(
                api_key=self.perplexity_api_key,
                max_tokens=1500,
                timeout=60
            )
            
            search_response = perplexity_search_tool.search(query=prompt)
            
            if hasattr(search_response, 'error') and search_response.error:
                raise Exception(f"Perplexity API error: {search_response.error}")
            
            response = search_response.content
            
            if response is None:
                raise Exception("Perplexity API returned None response.")
            
            # Clean and parse the response
            cleaned_response = self._clean_json_response(response)
            
            # Parse JSON response
            try:
                criteria_data = json.loads(cleaned_response)
                criteria = criteria_data.get("criteria", [])
                logger.info(f"Successfully generated {len(criteria)} comparison criteria")
                return criteria
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for criteria generation: {e}")
                logger.error(f"Cleaned response: {cleaned_response}")
                
                # Try to extract JSON using regex
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    try:
                        criteria_data = json.loads(json_match.group(0))
                        criteria = criteria_data.get("criteria", [])
                        return criteria
                    except json.JSONDecodeError:
                        pass
                
                # Fallback to basic criteria
                return self._get_fallback_criteria()
                
        except Exception as e:
            logger.error(f"Error calling LLM for criteria generation: {e}")
            return self._get_fallback_criteria()
    
    def _get_fallback_criteria(self) -> List[Dict[str, Any]]:
        """
        Get fallback criteria when LLM fails.
        """
        return [
            {
                "name": "Pricing Competitiveness",
                "description": "Compare pricing models, cost structure, and value for money",
                "evaluation_method": "quantitative",
                "category": "Cost"
            },
            {
                "name": "Service Quality",
                "description": "Evaluate reliability, performance, and customer satisfaction",
                "evaluation_method": "qualitative",
                "category": "Quality"
            },
            {
                "name": "Technical Capabilities",
                "description": "Assess technical expertise, tools, and capabilities",
                "evaluation_method": "qualitative",
                "category": "Technical"
            },
            {
                "name": "Customer Support",
                "description": "Evaluate support quality, availability, and responsiveness",
                "evaluation_method": "qualitative",
                "category": "Service"
            },
            {
                "name": "Company Stability",
                "description": "Assess company size, financial stability, and track record",
                "evaluation_method": "qualitative",
                "category": "Business"
            }
        ]
    
    def _compare_vendors_by_criteria(
        self, 
        vendors: List[Dict[str, str]], 
        criteria: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare vendors based on the generated criteria using LLM - SEPARATE API CALL.
        """
        try:
            logger.info(f"Starting vendor comparison for {len(vendors)} vendors with {len(criteria)} criteria")
            
            if not self.perplexity_api_key:
                logger.error("PERPLEXITY_API_KEY not set, cannot perform vendor comparison")
                raise Exception("PERPLEXITY_API_KEY environment variable is required for vendor comparison")
            
            # Build simple comparison prompt with vendor details
            vendor_details = []
            for vendor in vendors:
                vendor_details.append(f"{vendor['name']} (Location: {vendor.get('location', 'Unknown')})")
            
            criteria_names = [criterion['name'] for criterion in criteria]
            
            prompt = f"""
Compare these vendors: {', '.join(vendor_details)}

Based on these criteria: {', '.join(criteria_names)}

For each criterion, provide concise comparisons with scores and brief rationales.

Return JSON:
{{
    "comparisons": [
        {{
            "criterion": "Pricing",
            "vendors": [
                {{"name": "Microsoft", "location": "Redmond, WA", "score": 4, "rationale": "Enterprise pricing with volume discounts. $X per user/month."}},
                {{"name": "Google", "location": "Mountain View, CA", "score": 3, "rationale": "Pay-as-you-go model. $Y per hour with sustained use discounts."}}
            ]
        }}
    ]
}}

CRITICAL SCORING GUIDELINES:
- Score 1: Poor performance, significant issues, below industry standards
- Score 2: Below average, some concerns, limited capabilities  
- Score 3: Average performance, meets basic standards
- Score 4: Above average, strong performance, exceeds standards
- Score 5: Exceptional, industry-leading performance

Guidelines:
- Keep rationales under 40 words
- Include numerical scores (1-5) that match the rationale content
- Add specific metrics, percentages, or pricing when available
- Use comparative language
- Ensure score and rationale are perfectly aligned
- When mentioning ratings, be consistent with the 5-point scoring system
- If referencing external ratings, mention the source (e.g., "4/5 stars on Google Reviews")
"""
            
            logger.info(f"Making comparison API call with prompt length: {len(prompt)}")
            
            perplexity_search_tool = CustomPerplexitySearchTool(
                api_key=self.perplexity_api_key,
                max_tokens=4000,
                timeout=90
            )
            
            search_response = perplexity_search_tool.search(query=prompt)
            
            if hasattr(search_response, 'error') and search_response.error:
                raise Exception(f"Perplexity API error: {search_response.error}")
            
            response = search_response.content
            logger.info(f"Got comparison response, length: {len(response) if response else 0}")
            
            if response is None:
                raise Exception("Perplexity API returned None response.")
            
            # Clean and parse the response
            cleaned_response = self._clean_json_response(response)
            
            # Parse JSON response
            try:
                comparison_data = json.loads(cleaned_response)
                logger.info("Successfully parsed comparison JSON")
                
                # Transform to expected structure
                result = self._transform_simple_comparison(comparison_data, vendors, criteria)
                
                # Validate and fix score-rationale alignment
                result = self._validate_score_rationale_alignment(result)
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Response: {cleaned_response[:500]}")
                raise Exception("Failed to parse LLM response for vendor comparison")
            
        except Exception as e:
            logger.error(f"Error in vendor comparison: {e}")
            return self._create_fallback_comparison(vendors, criteria)
    
    def _build_comparison_prompt(
        self, 
        vendors: List[Dict[str, str]], 
        criteria: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for LLM to compare vendors based on criteria.
        """
        vendor_info = []
        for i, vendor in enumerate(vendors, 1):
            vendor_info.append(f"{i}. {vendor['name']} (Location: {vendor.get('location', 'Unknown')})")
        
        vendor_list = "\n".join(vendor_info)
        
        criteria_info = []
        for i, criterion in enumerate(criteria, 1):
            criteria_info.append(f"{i}. {criterion['name']} - {criterion['description']}")
        
        criteria_list = "\n".join(criteria_info)
        
        prompt = f"""
Compare these vendors: {', '.join([v['name'] for v in vendors])}

For each criterion below, provide a concise comparison with numerical scores:

{criteria_list}

For each vendor on each criterion, provide:
1. A numerical score (1-5 scale) that accurately reflects the performance level
2. A brief rationale (1-2 sentences max) that supports the score with specific metrics
3. Ensure the score and rationale are perfectly aligned

Return your response as valid JSON only:
{{
    "criteria_comparison": [
        {{
            "criterion_name": "First Criterion Name",
            "vendor_scores": [
                {{
                    "vendor_name": "Vendor1",
                    "score": 4,
                    "rationale": "Brief explanation with key metrics that justify the 4/5 score (e.g., 99.9% uptime, $X pricing)"
                }},
                {{
                    "vendor_name": "Vendor2", 
                    "score": 3,
                    "rationale": "Brief explanation with key metrics that justify the 3/5 score (e.g., 99.5% uptime, $Y pricing)"
                }}
            ]
        }}
    ]
}}

CRITICAL SCORING GUIDELINES:
- Score 1: Poor performance, significant issues, below industry standards
- Score 2: Below average, some concerns, limited capabilities
- Score 3: Average performance, meets basic standards
- Score 4: Above average, strong performance, exceeds standards
- Score 5: Exceptional, industry-leading performance

RATIONALES MUST:
- Keep under 50 words
- Include specific numbers, percentages, or metrics that support the score
- When mentioning ratings, be consistent with the 5-point scoring system
- If referencing external ratings (e.g., "4/5 stars on Google"), mention the source
- Use comparative language (e.g., "higher", "lower", "better", "worse")
- Directly justify why the vendor received that specific score
- Ensure the rationale content aligns with the numerical score given
"""
        
        return prompt
    
    def _call_llm_for_comparison(self, prompt: str, vendors: List[Dict[str, str]], criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Call LLM (Perplexity) for vendor comparison.
        """
        try:
            if not self.perplexity_api_key:
                logger.error("PERPLEXITY_API_KEY not set, cannot perform vendor comparison")
                raise Exception("PERPLEXITY_API_KEY environment variable is required for vendor comparison")
            
            logger.info(f"Perplexity API key is set: {bool(self.perplexity_api_key)}")
            
            logger.info(f"Sending comparison request to Perplexity, prompt length: {len(prompt)}")
            logger.info(f"Prompt preview: {prompt[:200]}...")
            
            perplexity_search_tool = CustomPerplexitySearchTool(
                api_key=self.perplexity_api_key,
                max_tokens=4000,
                timeout=90
            )
            
            logger.info("Making Perplexity API call...")
            search_response = perplexity_search_tool.search(query=prompt)
            logger.info("Perplexity API call completed")
            
            if hasattr(search_response, 'error') and search_response.error:
                raise Exception(f"Perplexity API error: {search_response.error}")
            
            response = search_response.content
            
            if response is None:
                raise Exception("Perplexity API returned None response.")
            
            # Clean and parse the response
            cleaned_response = self._clean_json_response(response)
            
            # Parse JSON response
            try:
                comparison_data = json.loads(cleaned_response)
                logger.info("Successfully parsed vendor comparison response")
                logger.info(f"Comparison data keys: {list(comparison_data.keys())}")
                
                # Transform the simplified response to the full structure
                logger.info("Transforming comparison response...")
                full_response = self._transform_comparison_response(comparison_data, vendors, criteria)
                logger.info(f"Transformed response keys: {list(full_response.keys())}")
                
                # Validate and fix score-rationale alignment
                full_response = self._validate_score_rationale_alignment(full_response)
                
                return full_response
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for vendor comparison: {e}")
                logger.error(f"Cleaned response (first 1000 chars): {cleaned_response[:1000]}")
                logger.error(f"Raw response (first 500 chars): {response[:500] if response else 'None'}")
                
                # Try multiple JSON extraction strategies
                import re
                
                # Strategy 1: Extract JSON object using regex
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    try:
                        # Try to fix common JSON issues before parsing
                        fixed_json = self._validate_and_fix_json(json_match.group(0))
                        comparison_data = json.loads(fixed_json)
                        logger.info("Successfully extracted and fixed JSON using regex")
                        return comparison_data
                    except json.JSONDecodeError as e2:
                        logger.error(f"Regex JSON extraction failed: {e2}")
                        # Try original without fixing
                        try:
                            comparison_data = json.loads(json_match.group(0))
                            logger.info("Successfully extracted JSON using regex (original)")
                            return comparison_data
                        except json.JSONDecodeError as e3:
                            logger.error(f"Original JSON also failed: {e3}")
                
                # Strategy 2: Try to find JSON array
                array_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
                if array_match:
                    try:
                        comparison_data = json.loads(array_match.group(0))
                        logger.info("Successfully extracted JSON array using regex")
                        return comparison_data
                    except json.JSONDecodeError as e2:
                        logger.error(f"JSON array extraction failed: {e2}")
                
                # Strategy 3: Try to extract multiple JSON objects
                json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response)
                for i, json_obj in enumerate(json_objects):
                    try:
                        comparison_data = json.loads(json_obj)
                        logger.info(f"Successfully extracted JSON object {i+1} using regex")
                        return comparison_data
                    except json.JSONDecodeError as e2:
                        logger.error(f"JSON object {i+1} extraction failed: {e2}")
                        continue
                
                # Fallback to fallback comparison
                logger.info("All JSON extraction strategies failed, falling back to fallback comparison")
                raise Exception("Failed to parse LLM response for vendor comparison")
                
        except Exception as e:
            logger.error(f"Error calling LLM for vendor comparison: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_fallback_comparison(vendors, criteria)
    
    def _transform_simple_comparison(
        self,
        comparison_data: Dict[str, Any],
        vendors: List[Dict[str, str]],
        criteria: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Transform simple comparison response to full structure.
        """
        try:
            comparisons = comparison_data.get("comparisons", [])
            
            # Build criteria comparison structure
            criteria_comparison = []
            for criterion in criteria:
                criterion_data = {
                    "criterion_name": criterion["name"],
                    "criterion_description": criterion["description"],
                    "evaluation_method": criterion["evaluation_method"],
                    "category": criterion.get("category", "General"),
                    "vendor_scores": []
                }
                
                # Find matching comparison
                matching_comparison = None
                for comp in comparisons:
                    if comp.get("criterion", "").lower() in criterion["name"].lower() or criterion["name"].lower() in comp.get("criterion", "").lower():
                        matching_comparison = comp
                        break
                
                if matching_comparison:
                    for vendor_data in matching_comparison.get("vendors", []):
                        # Try to get location from LLM response first, then fallback to original vendors
                        vendor_location = vendor_data.get("location")
                        if not vendor_location:
                            vendor_location = next((v.get("location", "Unknown") for v in vendors if v["name"] == vendor_data.get("name")), "Unknown")
                        
                        criterion_data["vendor_scores"].append({
                            "vendor_name": vendor_data.get("name", "Unknown"),
                            "vendor_location": vendor_location,
                            "score": vendor_data.get("score", 3),
                            "rationale": vendor_data.get("rationale", "No rationale provided")
                        })
                else:
                    # No matching comparison found, add default
                    for vendor in vendors:
                        criterion_data["vendor_scores"].append({
                            "vendor_name": vendor["name"],
                            "vendor_location": vendor.get("location", "Unknown"),
                            "score": 3,
                            "rationale": "Comparison data not available for this criterion"
                        })
                
                criteria_comparison.append(criterion_data)
            
            # Determine best vendor based on rationales
            best_vendor = self._determine_best_vendor(criteria_comparison, vendors)
            
            return {
                "criteria_comparison": criteria_comparison,
                "best_vendor": best_vendor
            }
            
        except Exception as e:
            logger.error(f"Error transforming simple comparison: {e}")
            return self._create_fallback_comparison(vendors, criteria)
    
    def _transform_comparison_response(
        self, 
        comparison_data: Dict[str, Any], 
        vendors: List[Dict[str, str]], 
        criteria: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Transform the simplified LLM response to the full structure expected by the API.
        """
        try:
            criteria_comparison = comparison_data.get("criteria_comparison", [])
            
            # Build the full criteria comparison structure
            full_criteria_comparison = []
            for i, criterion in enumerate(criteria):
                # Find the corresponding criterion in the LLM response
                llm_criterion = None
                for llm_crit in criteria_comparison:
                    if llm_crit.get("criterion_name") == criterion["name"]:
                        llm_criterion = llm_crit
                        break
                
                # Build the full criterion structure
                criterion_data = {
                    "criterion_name": criterion["name"],
                    "criterion_description": criterion["description"],
                    "evaluation_method": criterion["evaluation_method"],
                    "category": criterion.get("category", "General"),
                    "vendor_scores": []
                }
                
                # Add vendor scores
                if llm_criterion and "vendor_scores" in llm_criterion:
                    criterion_data["vendor_scores"] = []
                    for vendor in vendors:
                        # Find the vendor's score in the LLM response
                        vendor_score = None
                        for score in llm_criterion["vendor_scores"]:
                            if score.get("vendor_name") == vendor["name"]:
                                vendor_score = score
                                break
                        
                        if vendor_score:
                            criterion_data["vendor_scores"].append({
                                "vendor_name": vendor["name"],
                                "vendor_location": vendor.get("location", "Unknown"),
                                "score": vendor_score.get("score", 5),
                                "rationale": vendor_score.get("rationale", "No rationale provided")
                            })
                        else:
                            criterion_data["vendor_scores"].append({
                                "vendor_name": vendor["name"],
                                "vendor_location": vendor.get("location", "Unknown"),
                                "score": 3,
                                "rationale": "No comparison data available for this criterion"
                            })
                else:
                    # No LLM data for this criterion, add default responses
                    for vendor in vendors:
                        criterion_data["vendor_scores"].append({
                            "vendor_name": vendor["name"],
                            "vendor_location": vendor.get("location", "Unknown"),
                            "score": 3,
                            "rationale": "No comparison data available for this criterion"
                        })
                
                full_criteria_comparison.append(criterion_data)
            
            # Determine best vendor based on rationales
            best_vendor = self._determine_best_vendor(full_criteria_comparison, vendors)
            
            return {
                "criteria_comparison": full_criteria_comparison,
                "best_vendor": best_vendor
            }
            
        except Exception as e:
            logger.error(f"Error transforming comparison response: {e}")
            raise Exception("Failed to transform vendor comparison response")
    
    def _validate_score_rationale_alignment(self, comparison_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and fix inconsistencies between scores and rationales.
        """
        try:
            criteria_comparison = comparison_result.get("criteria_comparison", [])
            
            for criterion in criteria_comparison:
                vendor_scores = criterion.get("vendor_scores", [])
                
                for vendor_score in vendor_scores:
                    score = vendor_score.get("score", 3)
                    rationale = vendor_score.get("rationale", "")
                    
                    # Check for common inconsistencies and fix them
                    corrected_score = self._correct_score_based_on_rationale(score, rationale)
                    if corrected_score != score:
                        logger.info(f"Corrected score from {score} to {corrected_score} for rationale: {rationale[:50]}...")
                        vendor_score["score"] = corrected_score
            
            return comparison_result
            
        except Exception as e:
            logger.error(f"Error validating score-rationale alignment: {e}")
            return comparison_result
    
    def _correct_score_based_on_rationale(self, score: int, rationale: str) -> int:
        """
        Correct score based on rationale content for 5-point scale consistency.
        """
        rationale_lower = rationale.lower()
        
        # Check for rating mentions and convert them
        import re
        
        # Look for X/5 patterns - keep as is since we're using 5-point scale
        rating_5_match = re.search(r'(\d+(?:\.\d+)?)/5', rationale_lower)
        if rating_5_match:
            rating_5 = float(rating_5_match.group(1))
            converted_score = round(rating_5)
            # Use the converted score if a 5-point rating is mentioned
            return converted_score
        
        # Look for X/10 patterns and convert to 5-point scale
        rating_10_match = re.search(r'(\d+(?:\.\d+)?)/10', rationale_lower)
        if rating_10_match:
            rating_10 = float(rating_10_match.group(1))
            converted_score = round((rating_10 / 10) * 5)
            if abs(converted_score - score) > 1:
                return converted_score
        
        # Check for percentage mentions
        percentage_match = re.search(r'(\d+(?:\.\d+)?)%', rationale_lower)
        if percentage_match:
            percentage = float(percentage_match.group(1))
            # Convert percentage to 5-point scale
            converted_score = round((percentage / 100) * 5)
            if abs(converted_score - score) > 1:
                return converted_score
        
        # Check for qualitative indicators
        if any(word in rationale_lower for word in ['excellent', 'outstanding', 'exceptional', 'industry-leading']):
            if score < 4:
                return 5
        elif any(word in rationale_lower for word in ['poor', 'terrible', 'awful', 'significant issues']):
            if score > 2:
                return 1
        elif any(word in rationale_lower for word in ['average', 'moderate', 'decent']):
            if score < 2 or score > 4:
                return 3
        
        return score
    
    
    def _determine_best_vendor(
        self, 
        criteria_comparison: List[Dict[str, Any]], 
        vendors: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Determine the best vendor using LLM analysis of the comparison rationales.
        """
        try:
            if not self.perplexity_api_key:
                raise Exception("PERPLEXITY_API_KEY environment variable is required for best vendor determination")
            
            # Build prompt to determine best vendor
            vendor_names = [vendor['name'] for vendor in vendors]
            
            # Create summary of rationales for each vendor
            vendor_rationales = {}
            for vendor in vendors:
                vendor_rationales[vendor['name']] = []
                for criterion in criteria_comparison:
                    for vendor_score in criterion.get('vendor_scores', []):
                        # Try exact match first
                        if vendor_score.get('vendor_name') == vendor['name']:
                            vendor_rationales[vendor['name']].append({
                                'criterion': criterion.get('criterion_name'),
                                'rationale': vendor_score.get('rationale', '')
                            })
                        # Try case-insensitive match
                        elif vendor_score.get('vendor_name', '').lower() == vendor['name'].lower():
                            vendor_rationales[vendor['name']].append({
                                'criterion': criterion.get('criterion_name'),
                                'rationale': vendor_score.get('rationale', '')
                            })
                        # Try partial match (in case of name variations)
                        elif vendor['name'].lower() in vendor_score.get('vendor_name', '').lower():
                            vendor_rationales[vendor['name']].append({
                                'criterion': criterion.get('criterion_name'),
                                'rationale': vendor_score.get('rationale', '')
                            })
            
            prompt = f"""
Based on the detailed comparison rationales below, determine which vendor is the best overall choice and explain why.

VENDORS: {', '.join(vendor_names)}

COMPARISON RATIONALES:
{json.dumps(vendor_rationales, indent=2)}

Analyze all the rationales and determine which vendor performs best overall across all criteria. Consider strengths, weaknesses, and overall value.

Return JSON:
{{
    "best_vendor": {{
        "vendor_name": "Best Vendor Name",
        "reasoning": "Detailed explanation of why this vendor is the best choice based on the comparison rationales"
    }}
}}
"""
            
            logger.info("Determining best vendor using LLM analysis...")
            
            perplexity_search_tool = CustomPerplexitySearchTool(
                api_key=self.perplexity_api_key,
                max_tokens=1000,
                timeout=60
            )
            
            search_response = perplexity_search_tool.search(query=prompt)
            
            if hasattr(search_response, 'error') and search_response.error:
                raise Exception(f"Perplexity API error: {search_response.error}")
            
            response = search_response.content
            
            if response is None:
                raise Exception("Perplexity API returned None response.")
            
            # Clean and parse the response
            cleaned_response = self._clean_json_response(response)
            
            try:
                best_vendor_data = json.loads(cleaned_response)
                best_vendor_info = best_vendor_data.get("best_vendor", {})
                
                # Find the vendor location
                vendor_name = best_vendor_info.get("vendor_name", "Unknown")
                vendor_location = "Unknown"
                for vendor in vendors:
                    if vendor['name'] == vendor_name:
                        vendor_location = vendor.get('location', 'Unknown')
                        break
                
                return {
                    "vendor_name": vendor_name,
                    "vendor_location": vendor_location,
                    "reasoning": best_vendor_info.get("reasoning", "No reasoning provided")
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for best vendor determination: {e}")
                raise Exception("Failed to parse best vendor determination response")
                
        except Exception as e:
            logger.error(f"Error determining best vendor: {e}")
            raise Exception("Failed to determine best vendor")
    
    def _save_comparison_metrics(self, workspace_name: str, comparison_time: float):
        """
        Save vendor comparison metrics to the workspace metrics file.
        """
        try:
            from pathlib import Path
            from datetime import datetime
            
            # Define workspace root path
            PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
            WORKSPACE_ROOT = PROJECT_ROOT / "data"
            
            metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
            now = datetime.now().isoformat()
            mode = "Vendor comparison"

            new_record = {
                "timestamp": now,
                "mode": mode,
                "response_time": round(comparison_time, 2)
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
            
            logger.info(f"Logged response time ({comparison_time:.2f}s) for '{mode}' to {metrics_file}")
            
        except Exception as e:
            logger.error(f"Error saving vendor comparison metrics for workspace '{workspace_name}': {e}")
    
    def _save_comparison_results(self, workspace_name: str, results: Dict[str, Any]):
        """
        Save vendor comparison results to a JSON file in the workspace directory.
        """
        try:
            from pathlib import Path
            
            # Define workspace root path
            PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
            WORKSPACE_ROOT = PROJECT_ROOT / "data"
            
            results_file = WORKSPACE_ROOT / workspace_name / "vendor_comparison_results.json"
            
            # Ensure workspace directory exists
            results_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save results to file
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"Vendor comparison results saved to {results_file}")
            
        except Exception as e:
            logger.error(f"Error saving vendor comparison results for workspace '{workspace_name}': {e}")
    
    def _clean_json_response(self, response: str) -> str:
        """
        Clean JSON response to handle control characters and formatting issues.
        """
        import re
        
        # Basic cleaning
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Remove control characters that can cause JSON parsing issues
        # Replace common problematic characters
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
        
        # Fix common JSON issues
        cleaned = re.sub(r'\\n', '\\\\n', cleaned)  # Fix newlines in strings
        cleaned = re.sub(r'\\t', '\\\\t', cleaned)  # Fix tabs in strings
        
        # Try to find JSON object/array boundaries
        # Look for the first { and last } to extract just the JSON
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace:last_brace + 1]
        
        # Fix common JSON formatting issues
        # Remove trailing commas before closing braces/brackets
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        
        # Fix escaped quotes that shouldn't be escaped (like \"criteria" should be "criteria")
        cleaned = re.sub(r'\\"([^"]*)"', r'"\1"', cleaned)
        
        return cleaned
    
    def _validate_and_fix_json(self, json_str: str) -> str:
        """
        Validate and fix common JSON issues in LLM responses.
        """
        import re
        
        # Fix common issues
        fixed = json_str
        
        # Remove trailing commas before closing braces/brackets
        fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
        
        # Fix escaped quotes that shouldn't be escaped (like \"criteria" should be "criteria")
        fixed = re.sub(r'\\"([^"]*)"', r'"\1"', fixed)
        
        # Fix missing quotes around keys
        fixed = re.sub(r'(\w+):', r'"\1":', fixed)
        
        # Fix single quotes to double quotes
        fixed = re.sub(r"'([^']*)':", r'"\1":', fixed)
        fixed = re.sub(r":\s*'([^']*)'", r': "\1"', fixed)
        
        return fixed
    
    def _create_fallback_comparison(self, vendors: List[Dict[str, str]], criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a fallback comparison when the main comparison fails.
        """
        try:
            logger.info("Creating fallback comparison due to parsing error")
            
            # Create basic comparison structure
            comparison_results = []
            
            for criterion in criteria:
                criterion_comparison = {
                    "criterion_name": criterion.get("name", "Unknown Criterion"),
                    "criterion_description": criterion.get("description", "No description available"),
                    "vendor_scores": []
                }
                
                for vendor in vendors:
                    vendor_score = {
                        "vendor_name": vendor.get("name", "Unknown Vendor"),
                        "vendor_location": vendor.get("location", "Unknown Location"),
                        "score": 3,  # Default neutral score
                        "rationale": f"Unable to evaluate {vendor.get('name', 'vendor')} for {criterion.get('name', 'this criterion')} due to parsing error."
                    }
                    criterion_comparison["vendor_scores"].append(vendor_score)
                
                comparison_results.append(criterion_comparison)
            
            # Determine best vendor (first one as fallback)
            best_vendor = {
                "vendor_name": vendors[0].get("name", "Unknown Vendor"),
                "vendor_location": vendors[0].get("location", "Unknown Location"),
                "reasoning": "Selected as fallback due to parsing error in main comparison."
            }
            
            return {
                "comparison_results": comparison_results,
                "best_vendor": best_vendor,
                "fallback_used": True,
                "error_message": "Main comparison failed due to JSON parsing error, using fallback comparison."
            }
            
        except Exception as e:
            logger.error(f"Error creating fallback comparison: {e}")
            return {
                "comparison_results": [],
                "best_vendor": None,
                "fallback_used": True,
                "error_message": f"Failed to create fallback comparison: {str(e)}"
            }