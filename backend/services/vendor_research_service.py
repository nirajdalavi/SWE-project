# services/vendor_research_service.py
import os
import json
import logging
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
from services.airbyte_enrichment_service import AirbyteEnrichmentService
from services.vendor_analysis_service import VendorAnalysisService

logger = logging.getLogger(__name__)
load_dotenv()

class VendorResearchService:
    """
    Service to research specific vendors using external data sources for comprehensive analysis.
    This is similar to the deep analysis part of vendor recommendations but for user-specified vendors.
    """
    
    def __init__(self):
        self.enrichment_service = AirbyteEnrichmentService()
        self.analysis_service = VendorAnalysisService()
    
    def research_vendor(
        self,
        vendor_name: str,
        location: str,
        workspace_name: str = None,
        enable_reddit_analysis: bool = False,
        enable_linkedin_analysis: bool = False,
        enable_google_reviews: bool = False
    ) -> Dict[str, Any]:
        """
        Research a specific vendor using external data sources.
        
        Args:
            vendor_name: Name of the vendor to research
            location: Location of the vendor
            workspace_name: Workspace name for metrics tracking
            enable_reddit_analysis: Whether to enable Reddit data analysis
            enable_linkedin_analysis: Whether to enable LinkedIn data analysis
            enable_google_reviews: Whether to enable Google Places reviews analysis
        
        Returns:
            Dictionary containing vendor research results with deep analysis
        """
        try:
            start_time = time.time()
            logger.info(f"Starting vendor research for: {vendor_name} in {location}")
            
            # Validate that at least one external source is enabled
            if not (enable_reddit_analysis or enable_linkedin_analysis or enable_google_reviews):
                return {
                    "success": False,
                    "error": "At least one external data source must be enabled for vendor research"
                }
            
            # Create basic vendor data structure
            vendor_data = {
                "vendor_name": vendor_name,
                "location": location,
                "company_size": "Not specified",
                "specialization": "Not specified", 
                "experience": "Not specified",
                "website": "Not specified",
                "strengths": [],
                "risk_factors": []
            }
            
            # Enrich vendor data from external sources
            logger.info(f"Enriching vendor data from external sources (Reddit: {enable_reddit_analysis}, LinkedIn: {enable_linkedin_analysis}, Google Reviews: {enable_google_reviews})")
            
            external_data = self.enrichment_service.enrich_vendor_data(
                vendor_name=vendor_name,
                website=None,  # We don't have website info for user-specified vendors
                location=location,
                enable_reddit=enable_reddit_analysis,
                enable_linkedin=enable_linkedin_analysis,
                enable_google_reviews=enable_google_reviews
            )
            
            # Analyze enriched data
            logger.info("Starting deep analysis of enriched vendor data")
            deep_analysis = self.analysis_service.analyze_enriched_vendor_data(
                vendor_data=vendor_data,
                external_data=external_data
            )
            
            # Log whether Perplexity was called
            perplexity_called = deep_analysis.get("analysis_metadata", {}).get("perplexity_called", True)
            if not perplexity_called:
                logger.info(f"Skipped Perplexity call for {vendor_name} - no meaningful external data found")
            
            # Combine vendor data with enriched analysis
            research_result = {
                **vendor_data,  # Basic vendor data
                "external_data": external_data,
                "deep_analysis": deep_analysis["analysis"],
                "analysis_metadata": deep_analysis["analysis_metadata"]
            }
            
            research_time = time.time() - start_time
            logger.info(f"Vendor research completed for {vendor_name} in {research_time:.2f}s")
            
            # Track metrics if workspace is provided
            if workspace_name:
                self._track_research_metrics(workspace_name, vendor_name, research_time, external_data)
            
            return {
                "success": True,
                "data": research_result,
                "research_metadata": {
                    "vendor_name": vendor_name,
                    "location": location,
                    "sources_used": external_data.get("sources_used", []),
                    "research_time": research_time,
                    "data_quality": self._assess_data_quality(external_data),
                    "timestamp": time.time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in vendor research for {vendor_name}: {e}")
            return {
                "success": False,
                "error": f"Error researching vendor {vendor_name}: {str(e)}"
            }
    
    def _track_research_metrics(self, workspace_name: str, vendor_name: str, research_time: float, external_data: Dict[str, Any]) -> None:
        """Track research metrics for analytics."""
        try:
            metrics_file = f"data/{workspace_name}/vendor_research_metrics.json"
            
            # Load existing metrics or create new
            if os.path.exists(metrics_file):
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)
            else:
                metrics = {
                    "total_researches": 0,
                    "vendors_researched": [],
                    "average_research_time": 0,
                    "sources_usage": {
                        "reddit": 0,
                        "linkedin": 0,
                        "google_reviews": 0
                    },
                    "last_updated": time.time()
                }
            
            # Update metrics
            metrics["total_researches"] += 1
            if vendor_name not in metrics["vendors_researched"]:
                metrics["vendors_researched"].append(vendor_name)
            
            # Update average research time
            total_time = metrics["average_research_time"] * (metrics["total_researches"] - 1) + research_time
            metrics["average_research_time"] = total_time / metrics["total_researches"]
            
            # Update sources usage
            sources_used = external_data.get("sources_used", [])
            for source in sources_used:
                if source in metrics["sources_usage"]:
                    metrics["sources_usage"][source] += 1
            
            metrics["last_updated"] = time.time()
            
            # Save updated metrics
            os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to track research metrics: {e}")
    
    def _assess_data_quality(self, external_data: Dict[str, Any]) -> str:
        """Assess the quality of external data collected."""
        try:
            quality_score = 0
            total_sources = 0
            
            # Check Reddit data quality
            reddit_data = external_data.get("reddit", {})
            if reddit_data and not reddit_data.get("error"):
                total_sources += 1
                if reddit_data.get("mentions") and len(reddit_data["mentions"]) > 0:
                    quality_score += 1
            
            # Check LinkedIn data quality
            linkedin_data = external_data.get("linkedin", {})
            if linkedin_data and not linkedin_data.get("error"):
                total_sources += 1
                if linkedin_data.get("company_info"):
                    quality_score += 1
            
            # Check Google Places data quality
            google_data = external_data.get("google_places", {})
            if google_data and not google_data.get("error"):
                total_sources += 1
                if google_data.get("reviews") and len(google_data["reviews"]) > 0:
                    quality_score += 1
            
            if total_sources == 0:
                return "No Data"
            elif quality_score == 0:
                return "Poor"
            elif quality_score / total_sources < 0.5:
                return "Fair"
            elif quality_score / total_sources < 0.8:
                return "Good"
            else:
                return "Excellent"
                
        except Exception as e:
            logger.warning(f"Failed to assess data quality: {e}")
            return "Unknown"
