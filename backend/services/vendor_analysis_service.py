# services/vendor_analysis_service.py
import os
import json
import logging
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
from services.custom_perplexity_tool import CustomPerplexitySearchTool

logger = logging.getLogger(__name__)
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

class VendorAnalysisService:
    """
    Service to analyze enriched vendor data using LLM for deep insights.
    """
    
    def __init__(self):
        self.perplexity_api_key = PERPLEXITY_API_KEY
    
    def analyze_enriched_vendor_data(self, vendor_data: Dict[str, Any], external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze enriched vendor data and provide deep insights.
        """
        try:
            logger.info(f"Starting deep analysis for vendor: {vendor_data.get('vendor_name', 'Unknown')}")
            start_time = time.time()
            
            # Check if we have any meaningful external data to analyze
            has_meaningful_data = self._has_meaningful_external_data(external_data)
            
            if not has_meaningful_data:
                logger.info(f"No meaningful external data found for {vendor_data.get('vendor_name', 'Unknown')}, skipping Perplexity call")
                analysis_result = self._create_no_data_analysis(vendor_data, external_data)
            else:
                # Build analysis prompt
                analysis_prompt = self._build_analysis_prompt(vendor_data, external_data)
                
                # Call LLM for analysis
                analysis_result = self._call_llm_for_analysis(analysis_prompt)
            
            analysis_time = time.time() - start_time
            logger.info(f"Deep analysis completed in {analysis_time:.2f}s")
            
            return {
                "vendor_name": vendor_data.get("vendor_name", "Unknown"),
                "analysis": analysis_result,
                "analysis_metadata": {
                    "analysis_time": analysis_time,
                    "timestamp": time.time(),
                    "perplexity_called": has_meaningful_data
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing vendor data: {e}")
            return {
                "vendor_name": vendor_data.get("vendor_name", "Unknown"),
                "analysis": {
                    "error": str(e),
                    "reddit_insights": "Analysis failed",
                    "linkedin_insights": "Analysis failed",
                    "overall_assessment": "Unable to complete analysis",
                    "risk_factors": ["Analysis service unavailable"],
                    "competitive_advantages": [],
                    "recommendations": "Please try again later"
                },
                "analysis_metadata": {
                    "analysis_time": 0,
                    "error": str(e),
                    "timestamp": time.time()
                }
            }
    
    def _build_analysis_prompt(self, vendor_data: Dict[str, Any], external_data: Dict[str, Any]) -> str:
        """
        Build a comprehensive prompt for LLM analysis of enriched vendor data.
        """
        vendor_name = vendor_data.get("vendor_name", "Unknown Vendor")
        
        # Check if we have real data or empty data
        reddit_data = external_data.get('reddit', {})
        linkedin_data = external_data.get('linkedin', {})
        google_places_data = external_data.get('google_places', {})
        
        has_reddit_data = reddit_data.get('mentions') and len(reddit_data.get('mentions', [])) > 0
        has_linkedin_data = linkedin_data.get('company_info') and linkedin_data.get('company_info', {}).get('name')
        has_google_places_data = google_places_data.get('reviews') and len(google_places_data.get('reviews', [])) > 0
        
        prompt = f"""
        You are an expert vendor analysis specialist. Analyze the following vendor data and provide comprehensive insights based ONLY on the provided data sources.

        IMPORTANT: 
        - Base your analysis ONLY on the vendor information and external data (Reddit, LinkedIn, Google Places) provided below
        - Do NOT perform additional web searches or reference external sources not provided
        - Focus on analyzing the sentiment, patterns, and insights from the existing data

        VENDOR INFORMATION:
        Name: {vendor_name}
        Company Size: {vendor_data.get('company_size', 'Not specified')}
        Specialization: {vendor_data.get('specialization', 'Not specified')}
        Experience: {vendor_data.get('experience', 'Not specified')}
        Location: {vendor_data.get('location', 'Not specified')}
        Website: {vendor_data.get('website', 'Not specified')}
        Strengths: {', '.join(vendor_data.get('strengths', []))}
        Risk Factors: {', '.join(vendor_data.get('risk_factors', []))}

        REDDIT COMMUNITY DATA:
        Data Available: {has_reddit_data}
        {json.dumps(reddit_data, indent=2) if has_reddit_data else "No Reddit data available - API may not be configured or vendor not discussed on Reddit"}

        LINKEDIN COMPANY DATA:
        Data Available: {has_linkedin_data}
        {json.dumps(linkedin_data, indent=2) if has_linkedin_data else "No LinkedIn data available - API may not be configured or company not found on LinkedIn"}

        GOOGLE PLACES REVIEWS DATA:
        Data Available: {has_google_places_data}
        {json.dumps(google_places_data, indent=2) if has_google_places_data else "No Google Places data available - API may not be configured or business not found on Google Places"}

        Please provide a comprehensive analysis in the following JSON format:

        {{
            "reddit_insights": "Analysis of Reddit community sentiment, discussions, and user experiences about this vendor. Include specific mentions, sentiment trends, and community feedback.",
            "linkedin_insights": "Analysis of LinkedIn company data including growth trends, engagement metrics, company updates, and professional network perception.",
            "google_reviews_insights": "Analysis of Google Places reviews including customer satisfaction, service quality, common themes in feedback, and overall rating trends.",
            "overall_assessment": "Comprehensive assessment combining all data sources - company credibility, market presence, customer satisfaction, and business health.",
            "risk_factors": ["List of potential risks or concerns identified from the analysis"],
            "competitive_advantages": ["List of competitive advantages and strengths identified"],
            "market_positioning": "Analysis of where this vendor stands in the market compared to competitors",
            "customer_sentiment_summary": "Summary of customer sentiment across all sources including Reddit, LinkedIn, and Google Reviews",
            "recent_developments": "Key recent developments or changes identified from the data",
            "recommendations": "Specific recommendations for potential customers considering this vendor"
        }}

        Guidelines:
        1. Be specific and reference actual data points from the sources when available
        2. If Reddit data is available, analyze community sentiment and discussions
        3. If LinkedIn data is available, analyze company growth, engagement, and professional presence
        4. If Google Places data is available, analyze customer reviews, ratings, and service quality feedback
        5. If external data is not available, focus on the original vendor information and acknowledge data limitations
        6. Identify both positive and negative aspects objectively
        7. Provide actionable insights for decision-making
        8. Consider the vendor's market position and competitive landscape
        9. Highlight any red flags or concerns that should be investigated further
        10. Rate your confidence in the analysis on a scale of 1-10
        11. Always acknowledge when external data sources are not available or limited

        Return ONLY the JSON response without any additional text or explanations.
        """
        
        return prompt
    
    def _has_meaningful_external_data(self, external_data: Dict[str, Any]) -> bool:
        """
        Check if we have meaningful external data to analyze.
        """
        reddit_data = external_data.get('reddit', {})
        linkedin_data = external_data.get('linkedin', {})
        google_places_data = external_data.get('google_places', {})
        
        # Check Reddit data
        has_reddit_data = (
            reddit_data.get('mentions') and 
            len(reddit_data.get('mentions', [])) > 0 and
            not reddit_data.get('error')
        )
        
        # Check LinkedIn data
        has_linkedin_data = (
            linkedin_data.get('company_info') and 
            linkedin_data.get('company_info', {}).get('name') and
            not linkedin_data.get('error')
        )
        
        # Check Google Places data
        has_google_places_data = (
            google_places_data.get('reviews') and 
            len(google_places_data.get('reviews', [])) > 0 and
            not google_places_data.get('error')
        )
        
        # Return True if we have at least one meaningful data source
        return has_reddit_data or has_linkedin_data or has_google_places_data
    
    def _create_no_data_analysis(self, vendor_data: Dict[str, Any], external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create analysis when no meaningful external data is available.
        """
        vendor_name = vendor_data.get("vendor_name", "Unknown Vendor")
        
        # Check what data sources were attempted
        reddit_data = external_data.get('reddit', {})
        linkedin_data = external_data.get('linkedin', {})
        google_places_data = external_data.get('google_places', {})
        
        reddit_error = reddit_data.get('error', 'No Reddit data available')
        linkedin_error = linkedin_data.get('error', 'No LinkedIn data available')
        google_places_error = google_places_data.get('error', 'No Google Places data available')
        
        return {
            "reddit_insights": f"No Reddit data available for {vendor_name}. {reddit_error}",
            "linkedin_insights": f"No LinkedIn data available for {vendor_name}. {linkedin_error}",
            "google_reviews_insights": f"No Google Places data available for {vendor_name}. {google_places_error}",
            "customer_sentiment_summary": "Customer sentiment data not available from external sources",
            "recent_developments": "Recent developments not available from external sources",
            "data_limitations": {
                "reddit_available": False,
                "linkedin_available": False,
                "google_places_available": False,
                "external_sources_checked": ["reddit", "linkedin", "google_places"],
                "analysis_based_on": "vendor_provided_information_only"
            }
        }
    
    def _call_llm_for_analysis(self, prompt: str) -> Dict[str, Any]:
        """
        Call LLM (Perplexity) for vendor analysis.
        """
        try:
            if not self.perplexity_api_key:
                raise Exception("PERPLEXITY_API_KEY environment variable is not set.")
            
            logger.info(f"Sending analysis request to Perplexity, prompt length: {len(prompt)}")
            
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
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON response
            try:
                analysis_result = json.loads(cleaned_response)
                logger.info("Successfully parsed LLM analysis response")
                return analysis_result
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for vendor analysis: {e}")
                logger.error(f"Cleaned response: {cleaned_response}")
                
                # Try to extract JSON using regex
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    try:
                        analysis_result = json.loads(json_match.group(0))
                        return analysis_result
                    except json.JSONDecodeError:
                        pass
                
                # Fallback to structured response
                return self._create_fallback_analysis(cleaned_response)
                
        except Exception as e:
            logger.error(f"Error calling LLM for vendor analysis: {e}")
            return self._create_fallback_analysis(f"Analysis failed: {str(e)}")
    
    def _create_fallback_analysis(self, raw_response: str) -> Dict[str, Any]:
        """
        Create a fallback analysis structure when JSON parsing fails.
        """
        return {
            "reddit_insights": f"Community analysis: {raw_response[:200]}..." if len(raw_response) > 200 else raw_response,
            "linkedin_insights": "LinkedIn data analysis completed but detailed insights unavailable due to parsing error.",
            "google_reviews_insights": "Google Places reviews analysis completed but detailed insights unavailable due to parsing error.",
            "overall_assessment": "Vendor analysis completed with some limitations in data processing.",
            "risk_factors": ["Data processing limitations may affect analysis accuracy"],
            "competitive_advantages": ["Analysis in progress"],
            "market_positioning": "Market positioning analysis requires further review",
            "customer_sentiment_summary": "Customer sentiment data processed with limitations",
            "recent_developments": "Recent developments analysis completed",
            "recommendations": "Consider additional verification of vendor capabilities",
            "analysis_note": "Analysis completed with parsing limitations"
        }
