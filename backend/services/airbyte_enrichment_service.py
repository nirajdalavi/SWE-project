# services/airbyte_enrichment_service.py
import os
import json
import logging
import requests
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import praw
from linkedin_api import Linkedin
from services.google_places_service import GooglePlacesService

logger = logging.getLogger(__name__)
load_dotenv()

class AirbyteEnrichmentService:
    """
    Service to enrich vendor data using real Reddit and LinkedIn APIs.
    """
    
    def __init__(self):
        # Reddit API credentials
        self.reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        self.reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "VendorAnalysisBot/1.0")
        
        # LinkedIn API credentials
        self.linkedin_username = os.getenv("LINKEDIN_USERNAME")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        
        # Initialize Reddit API client
        self.reddit = None
        if self.reddit_client_id and self.reddit_client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.reddit_client_id,
                    client_secret=self.reddit_client_secret,
                    user_agent=self.reddit_user_agent
                )
                logger.info("Reddit API client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit API client: {e}")
        
        # Initialize LinkedIn API client
        self.linkedin = None
        if self.linkedin_username and self.linkedin_password:
            try:
                self.linkedin = Linkedin(self.linkedin_username, self.linkedin_password)
                logger.info("LinkedIn API client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LinkedIn API client: {e}")
        
        # Initialize Google Places API client
        self.google_places = GooglePlacesService()
    
    def get_reddit_data(self, vendor_name: str) -> Dict[str, Any]:
        """
        Get real Reddit data for a vendor using Reddit API.
        """
        try:
            logger.info(f"Fetching real Reddit data for vendor: {vendor_name}")
            
            if not self.reddit:
                logger.warning("Reddit API client not initialized, returning empty data")
                return self._get_empty_reddit_data(vendor_name)
            
            # Generate search variations for better coverage
            search_variations = self._generate_search_variations(vendor_name)
            logger.info(f"Search variations for {vendor_name}: {search_variations}")
            
            # Search for vendor mentions in relevant subreddits
            relevant_subreddits = [
                'technology', 'programming', 'startups', 'business', 'entrepreneur',
                'software', 'webdev', 'sysadmin', 'devops', 'machinelearning',
                'artificial', 'cloud', 'saas', 'b2b', 'enterprise'
            ]
            
            mentions = []
            recent_posts = []
            total_engagement = 0
            seen_urls = set()  # Avoid duplicates
            
            for subreddit_name in relevant_subreddits:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    
                    # Try each search variation
                    for search_query in search_variations:
                        search_results = subreddit.search(search_query, limit=5, time_filter='month')
                        
                        for submission in search_results:
                            # Skip if we've already seen this URL
                            if submission.permalink in seen_urls:
                                continue
                            seen_urls.add(submission.permalink)
                            
                            # Check if submission is relevant to any of our search variations
                            is_relevant = False
                            for variation in search_variations:
                                if (variation.lower() in submission.title.lower() or 
                                    variation.lower() in submission.selftext.lower()):
                                    is_relevant = True
                                    break
                            
                            if not is_relevant:
                                continue
                            
                            mention = {
                                "subreddit": f"r/{subreddit_name}",
                                "title": submission.title,
                                "score": submission.score,
                                "comments": submission.num_comments,
                                "url": f"https://reddit.com{submission.permalink}",
                                "created_utc": submission.created_utc,
                                "sentiment": self._analyze_reddit_sentiment(submission)
                            }
                            mentions.append(mention)
                            total_engagement += submission.score + submission.num_comments
                            
                            # Get recent posts from the same subreddit
                            if len(recent_posts) < 3:
                                recent_posts.append({
                                    "subreddit": f"r/{subreddit_name}",
                                    "title": submission.title,
                                    "score": submission.score,
                                    "url": f"https://reddit.com{submission.permalink}",
                                    "created_utc": submission.created_utc
                                })
                
                except Exception as e:
                    logger.warning(f"Error searching subreddit {subreddit_name}: {e}")
                    continue
            
            # Calculate overall sentiment
            sentiment_scores = [mention.get("sentiment", "neutral") for mention in mentions]
            positive_count = sentiment_scores.count("positive")
            negative_count = sentiment_scores.count("negative")
            
            if positive_count > negative_count:
                overall_sentiment = "positive"
            elif negative_count > positive_count:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"
            
            reddit_data = {
                "vendor_name": vendor_name,
                "mentions": mentions,
                "recent_posts": recent_posts,
                "sentiment": overall_sentiment,
                "discussion_count": len(mentions),
                "total_engagement": total_engagement,
                "source": "reddit_api_real",
                "subreddits_searched": relevant_subreddits
            }
            
            logger.info(f"Reddit data retrieved for {vendor_name}: {len(mentions)} mentions, {overall_sentiment} sentiment")
            return reddit_data
            
        except Exception as e:
            logger.error(f"Error fetching Reddit data for {vendor_name}: {e}")
            return self._get_empty_reddit_data(vendor_name, str(e))
    
    def get_linkedin_data(self, vendor_name: str) -> Dict[str, Any]:
        """
        Get real LinkedIn data for a vendor using LinkedIn API.
        """
        try:
            logger.info(f"Fetching real LinkedIn data for vendor: {vendor_name}")
            
            if not self.linkedin:
                logger.warning("LinkedIn API client not initialized, returning empty data")
                return self._get_empty_linkedin_data(vendor_name)
            
            # Search for company on LinkedIn
            company_data = None
            try:
                # Search for company by name
                search_results = self.linkedin.search_companies(keywords=vendor_name, limit=1)
                if search_results:
                    # Use the company ID directly instead of URN
                    company_id = search_results[0].get('urn_id')
                    if company_id:
                        company_data = self.linkedin.get_company(company_id)
            except Exception as e:
                logger.warning(f"Error searching for company {vendor_name} on LinkedIn: {e}")
            
            if not company_data:
                logger.warning(f"Company {vendor_name} not found on LinkedIn")
                return self._get_empty_linkedin_data(vendor_name, "Company not found")
            
            # Extract company information
            company_info = {
                "name": company_data.get('name', vendor_name),
                "description": company_data.get('description', ''),
                "industry": company_data.get('industry', ''),
                "company_size": company_data.get('companySize', ''),
                "headquarters": company_data.get('headquarter', ''),
                "founded": company_data.get('foundedOn', ''),
                "website": company_data.get('website', ''),
                "employee_count": company_data.get('staffCount', 0)
            }
            
            # Get follower statistics
            follower_stats = {
                "total_followers": company_data.get('followingInfo', {}).get('followerCount', 0),
                "follower_growth": "Data not available",  # LinkedIn API doesn't provide growth data
                "engagement_rate": "Data not available"
            }
            
            # Get recent posts (if available)
            recent_posts = []
            try:
                # Get company updates/posts using company ID
                updates = self.linkedin.get_company_updates(company_id)
                # Limit to 5 posts manually
                for update in updates[:5]:
                    if 'commentary' in update:
                        post = {
                            "content": update['commentary'],
                            "likes": update.get('numLikes', 0),
                            "comments": update.get('numComments', 0),
                            "shares": update.get('numShares', 0),
                            "date": update.get('createdAt', '')
                        }
                        recent_posts.append(post)
            except Exception as e:
                logger.warning(f"Error fetching company updates for {vendor_name}: {e}")
            
            # Calculate engagement metrics
            engagement_metrics = {
                "avg_likes_per_post": sum(post["likes"] for post in recent_posts) // max(len(recent_posts), 1),
                "avg_comments_per_post": sum(post["comments"] for post in recent_posts) // max(len(recent_posts), 1),
                "avg_shares_per_post": sum(post["shares"] for post in recent_posts) // max(len(recent_posts), 1)
            }
            
            linkedin_data = {
                "vendor_name": vendor_name,
                "company_info": company_info,
                "follower_stats": follower_stats,
                "recent_posts": recent_posts,
                "engagement_metrics": engagement_metrics,
                "source": "linkedin_api_real",
                "company_id": company_id
            }
            
            logger.info(f"LinkedIn data retrieved for {vendor_name}: {company_info.get('employee_count', 0)} employees, {follower_stats.get('total_followers', 0)} followers")
            return linkedin_data
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn data for {vendor_name}: {e}")
            return self._get_empty_linkedin_data(vendor_name, str(e))
    
    def get_google_places_data(self, vendor_name: str, location: str = None) -> Dict[str, Any]:
        """
        Get Google Places data for a vendor including reviews and ratings.
        """
        try:
            logger.info(f"Fetching Google Places data for vendor: {vendor_name}")
            return self.google_places.get_place_data(vendor_name, location)
        except Exception as e:
            logger.error(f"Error fetching Google Places data for {vendor_name}: {e}")
            return self._get_empty_google_places_data(vendor_name, str(e))
    
    def _generate_search_variations(self, vendor_name: str) -> List[str]:
        """
        Generate multiple search variations for better Reddit coverage.
        """
        variations = [vendor_name]
        
        # Add lowercase version
        if vendor_name.lower() not in variations:
            variations.append(vendor_name.lower())
        
        # Add uppercase version
        if vendor_name.upper() not in variations:
            variations.append(vendor_name.upper())
        
        # Remove common corporate suffixes for more casual searches
        corporate_suffixes = ['Corporation', 'Corp', 'Inc', 'LLC', 'Ltd', 'Limited', 'Company', 'Co']
        base_name = vendor_name
        for suffix in corporate_suffixes:
            if vendor_name.endswith(f' {suffix}'):
                base_name = vendor_name.replace(f' {suffix}', '').strip()
                break
        
        if base_name != vendor_name and base_name not in variations:
            variations.append(base_name)
            if base_name.lower() not in variations:
                variations.append(base_name.lower())
        
        # Add common abbreviations for tech companies
        tech_abbreviations = {
            'International Business Machines': ['IBM'],
            'Microsoft Corporation': ['Microsoft', 'MSFT'],
            'Amazon.com Inc': ['Amazon', 'AWS'],
            'Alphabet Inc': ['Google', 'Alphabet'],
            'Apple Inc': ['Apple'],
            'NVIDIA Corporation': ['NVIDIA', 'Nvidia', 'nvidia'],
            'Oracle Corporation': ['Oracle'],
            'Salesforce Inc': ['Salesforce'],
            'ServiceNow Inc': ['ServiceNow'],
            'Workday Inc': ['Workday']
        }
        
        for full_name, abbrevs in tech_abbreviations.items():
            if vendor_name.lower() in full_name.lower() or full_name.lower() in vendor_name.lower():
                for abbrev in abbrevs:
                    if abbrev not in variations:
                        variations.append(abbrev)
        
        return variations[:5]  # Limit to 5 variations to avoid too many API calls
    
    def _analyze_reddit_sentiment(self, submission) -> str:
        """
        Analyze sentiment of a Reddit submission based on score and comments.
        """
        try:
            score = submission.score
            num_comments = submission.num_comments
            
            # Simple sentiment analysis based on score and engagement
            if score > 10 and num_comments > 5:
                return "positive"
            elif score < 0 or (score < 5 and num_comments > 10):
                return "negative"
            else:
                return "neutral"
        except:
            return "neutral"
    
    def _get_empty_reddit_data(self, vendor_name: str, error: str = None) -> Dict[str, Any]:
        """Return empty Reddit data structure."""
        return {
            "vendor_name": vendor_name,
            "mentions": [],
            "recent_posts": [],
            "sentiment": "neutral",
            "discussion_count": 0,
            "total_engagement": 0,
            "source": "reddit_api_real",
            "error": error or "No data available"
        }
    
    def _get_empty_linkedin_data(self, vendor_name: str, error: str = None) -> Dict[str, Any]:
        """Return empty LinkedIn data structure."""
        return {
            "vendor_name": vendor_name,
            "company_info": {},
            "follower_stats": {},
            "recent_posts": [],
            "engagement_metrics": {},
            "source": "linkedin_api_real",
            "error": error or "No data available"
        }
    
    def _get_empty_google_places_data(self, vendor_name: str, error: str = None) -> Dict[str, Any]:
        """Return empty Google Places data structure."""
        return {
            "vendor_name": vendor_name,
            "place_info": {},
            "rating_info": {
                "overall_rating": 0,
                "total_reviews": 0
            },
            "reviews": [],
            "review_statistics": {
                "total_reviews": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "recent_reviews_count": 0
            },
            "sentiment_analysis": {
                "overall_sentiment": "neutral",
                "positive_reviews": 0,
                "negative_reviews": 0,
                "neutral_reviews": 0,
                "sentiment_score": 0.5
            },
            "source": "google_places_api",
            "data_quality": {
                "reviews_available": False,
                "rating_available": False,
                "contact_info_available": False
            },
            "error": error or "No data available"
        }
    
    def enrich_vendor_data(self, vendor_name: str, website: str = None, location: str = None, enable_reddit: bool = True, enable_linkedin: bool = True, enable_google_reviews: bool = True) -> Dict[str, Any]:
        """
        Enrich vendor data by gathering information from enabled sources only.
        """
        try:
            logger.info(f"Starting real data enrichment for vendor: {vendor_name} (Reddit: {enable_reddit}, LinkedIn: {enable_linkedin}, Google Reviews: {enable_google_reviews})")
            start_time = time.time()
            
            # Gather data from enabled sources only
            reddit_data = self.get_reddit_data(vendor_name) if enable_reddit else self._get_empty_reddit_data(vendor_name, "Reddit analysis disabled")
            linkedin_data = self.get_linkedin_data(vendor_name) if enable_linkedin else self._get_empty_linkedin_data(vendor_name, "LinkedIn analysis disabled")
            google_places_data = self.get_google_places_data(vendor_name, location) if enable_google_reviews else self._get_empty_google_places_data(vendor_name, "Google Reviews analysis disabled")
            
            enrichment_time = time.time() - start_time
            logger.info(f"Real data enrichment completed for {vendor_name} in {enrichment_time:.2f}s")
            
            # Track which sources were actually used
            sources_used = []
            if enable_reddit:
                sources_used.append("reddit_api")
            if enable_linkedin:
                sources_used.append("linkedin_api")
            if enable_google_reviews:
                sources_used.append("google_places_api")
            
            return {
                "vendor_name": vendor_name,
                "reddit": reddit_data,
                "linkedin": linkedin_data,
                "google_places": google_places_data,
                "enrichment_metadata": {
                    "sources_used": sources_used,
                    "reddit_enabled": enable_reddit,
                    "linkedin_enabled": enable_linkedin,
                    "google_reviews_enabled": enable_google_reviews,
                    "enrichment_time": enrichment_time,
                    "timestamp": time.time(),
                    "data_type": "real"
                }
            }
            
        except Exception as e:
            logger.error(f"Error enriching vendor data for {vendor_name}: {e}")
            return {
                "vendor_name": vendor_name,
                "reddit": self._get_empty_reddit_data(vendor_name, str(e)) if enable_reddit else self._get_empty_reddit_data(vendor_name, "Reddit analysis disabled"),
                "linkedin": self._get_empty_linkedin_data(vendor_name, str(e)) if enable_linkedin else self._get_empty_linkedin_data(vendor_name, "LinkedIn analysis disabled"),
                "google_places": self._get_empty_google_places_data(vendor_name, str(e)) if enable_google_reviews else self._get_empty_google_places_data(vendor_name, "Google Reviews analysis disabled"),
                "enrichment_metadata": {
                    "sources_used": [],
                    "reddit_enabled": enable_reddit,
                    "linkedin_enabled": enable_linkedin,
                    "google_reviews_enabled": enable_google_reviews,
                    "enrichment_time": 0,
                    "error": str(e),
                    "timestamp": time.time(),
                    "data_type": "error"
                }
            }