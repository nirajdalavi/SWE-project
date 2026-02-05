# services/google_places_service.py
import os
import json
import logging
import requests
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class GooglePlacesService:
    """
    Service to fetch Google Places data including reviews and ratings for vendors.
    """
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAP_API")
        self.base_url = "https://maps.googleapis.com/maps/api/place"
        
        if not self.api_key:
            logger.warning("GOOGLE_MAP_API environment variable is not set. Google Places functionality will be disabled.")
    
    def get_place_data(self, vendor_name: str, location: str = None) -> Dict[str, Any]:
        """
        Get Google Places data for a vendor including reviews and ratings.
        
        Args:
            vendor_name: Name of the vendor/company
            location: Optional location to help with search accuracy
            
        Returns:
            Dictionary containing place data, reviews, and ratings
        """
        try:
            logger.info(f"Fetching Google Places data for vendor: {vendor_name}")
            
            if not self.api_key:
                logger.warning("Google Places API key not available, returning empty data")
                return self._get_empty_places_data(vendor_name, "API key not configured")
            
            # Step 1: Search for the place
            place_id = self._search_place(vendor_name, location)
            if not place_id:
                logger.warning(f"Place not found for vendor: {vendor_name}")
                return self._get_empty_places_data(vendor_name, "Place not found")
            
            # Step 2: Get detailed place information
            place_details = self._get_place_details(place_id)
            if not place_details:
                logger.warning(f"Could not get place details for: {vendor_name}")
                return self._get_empty_places_data(vendor_name, "Could not retrieve place details")
            
            # Step 3: Get reviews
            reviews = self._get_place_reviews(place_id)
            
            # Step 4: Process and structure the data
            places_data = self._process_places_data(place_details, reviews, vendor_name, place_id)
            
            logger.info(f"Google Places data retrieved for {vendor_name}: {len(reviews)} reviews, rating: {place_details.get('rating', 'N/A')}")
            return places_data
            
        except Exception as e:
            logger.error(f"Error fetching Google Places data for {vendor_name}: {e}")
            return self._get_empty_places_data(vendor_name, str(e))
    
    def _search_place(self, vendor_name: str, location: str = None) -> Optional[str]:
        """
        Search for a place using Google Places Text Search API, focusing on business and technology companies.
        """
        try:
            # Build search query with business/technology focus
            query = self._build_business_search_query(vendor_name, location)
            
            # URL encode the query
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            
            # Make the request with business-focused parameters
            url = f"{self.base_url}/textsearch/json"
            params = {
                'query': query,
                'key': self.api_key,
                'type': 'establishment'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'OK':
                logger.warning(f"Google Places search failed: {data.get('status')} - {data.get('error_message', 'Unknown error')}")
                return None
            
            results = data.get('results', [])
            if not results:
                logger.warning(f"No results found for query: {query}")
                return None
            
            # Filter results to prioritize business and technology companies
            filtered_results = self._filter_business_results(results, vendor_name)
            
            if not filtered_results:
                logger.warning(f"No business/technology results found for {vendor_name}")
                return None
            
            # Return the best matching result's place_id
            place_id = filtered_results[0].get('place_id')
            logger.info(f"Found business place for {vendor_name}: {filtered_results[0].get('name', 'Unknown')}")
            return place_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during place search: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching for place: {e}")
            return None
    
    def _build_business_search_query(self, vendor_name: str, location: str = None) -> str:
        """
        Build a search query focused on business and technology companies.
        """
        # Start with the vendor name
        query_parts = [vendor_name]
        
        # Add location if provided
        if location:
            query_parts.append(location)
        
        # Add business context keywords to prioritize business results
        query_parts.extend(["corporate", "headquarters", "business"])
        
        return " ".join(query_parts)
    
    def _filter_business_results(self, results: List[Dict[str, Any]], vendor_name: str) -> List[Dict[str, Any]]:
        """
        Filter Google Places results to prioritize business and technology companies.
        """
        if not results:
            return []
        
        # Technology and business-specific types (higher priority)
        tech_business_types = [
            'electronics_store', 'store', 'establishment', 'point_of_interest',
            'finance', 'insurance_agency', 'accounting', 'lawyer', 'real_estate_agency'
        ]
        
        # Keywords that indicate business/technology focus
        business_keywords = [
            'corporate', 'headquarters', 'office', 'business', 'company', 'corporation',
            'technology', 'software', 'tech', 'IT', 'cloud', 'services', 'solutions',
            'enterprise', 'consulting', 'professional', 'management', 'development',
            'systems', 'data', 'digital', 'innovation', 'research', 'laboratory',
            'inc', 'llc', 'ltd', 'limited', 'corp', 'co', 'group', 'global', 'international',
            'center', 'centre', 'building', 'tower', 'plaza', 'campus', 'park'
        ]
        
        filtered_results = []
        
        for result in results:
            place_types = result.get('types', [])
            place_name = result.get('name', '').lower()
            place_address = result.get('formatted_address', '').lower()
            
            # Check if it's a business/technology type
            is_business_type = any(place_type in tech_business_types for place_type in place_types)
            
            # Check if name/address contains business keywords
            has_business_keywords = any(keyword in place_name or keyword in place_address 
                                     for keyword in business_keywords)
            
            # Check if vendor name is in the place name (exact match or partial)
            vendor_name_lower = vendor_name.lower()
            name_match = (vendor_name_lower in place_name or 
                         any(word in place_name for word in vendor_name_lower.split()))
            
            # Score the result
            score = 0
            if name_match:
                score += 10  # High priority for name matches
            if is_business_type:
                score += 5   # Medium priority for business types
            if has_business_keywords:
                score += 3   # Lower priority for keyword matches
            
            # Only include results with some business relevance
            if score > 0:
                result['business_score'] = score
                filtered_results.append(result)
        
        # Sort by business relevance score (highest first)
        filtered_results.sort(key=lambda x: x.get('business_score', 0), reverse=True)
        
        # Log the filtering results
        if filtered_results:
            logger.info(f"Filtered {len(results)} results to {len(filtered_results)} business/technology results for {vendor_name}")
            for i, result in enumerate(filtered_results[:3]):  # Log top 3
                logger.info(f"  {i+1}. {result.get('name', 'Unknown')} (score: {result.get('business_score', 0)})")
        
        return filtered_results
    
    def _get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a place using Google Places Details API.
        """
        try:
            url = f"{self.base_url}/details/json"
            params = {
                'place_id': place_id,
                'key': self.api_key,
                'fields': 'name,rating,user_ratings_total,formatted_address,formatted_phone_number,website,opening_hours,types,business_status'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'OK':
                logger.warning(f"Google Places details failed: {data.get('status')} - {data.get('error_message', 'Unknown error')}")
                return None
            
            return data.get('result', {})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during place details fetch: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting place details: {e}")
            return None
    
    def _get_place_reviews(self, place_id: str) -> List[Dict[str, Any]]:
        """
        Get reviews for a place using Google Places Details API.
        """
        try:
            url = f"{self.base_url}/details/json"
            params = {
                'place_id': place_id,
                'key': self.api_key,
                'fields': 'reviews'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'OK':
                logger.warning(f"Google Places reviews failed: {data.get('status')} - {data.get('error_message', 'Unknown error')}")
                return []
            
            result = data.get('result', {})
            reviews = result.get('reviews', [])
            
            # Process reviews to extract relevant information
            processed_reviews = []
            for review in reviews:
                processed_review = {
                    'author_name': review.get('author_name', 'Anonymous'),
                    'rating': review.get('rating', 0),
                    'text': review.get('text', ''),
                    'time': review.get('time', 0),
                    'relative_time_description': review.get('relative_time_description', ''),
                    'language': review.get('language', 'en')
                }
                processed_reviews.append(processed_review)
            
            return processed_reviews
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during reviews fetch: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting place reviews: {e}")
            return []
    
    def _process_places_data(self, place_details: Dict[str, Any], reviews: List[Dict[str, Any]], vendor_name: str, place_id: str) -> Dict[str, Any]:
        """
        Process and structure the Google Places data.
        """
        try:
            # Calculate review statistics
            review_stats = self._calculate_review_stats(reviews)
            
            # Analyze sentiment of reviews
            sentiment_analysis = self._analyze_review_sentiment(reviews)
            
            # Extract key information
            places_data = {
                "vendor_name": vendor_name,
                "place_id": place_id,
                "place_info": {
                    "name": place_details.get('name', vendor_name),
                    "address": place_details.get('formatted_address', ''),
                    "phone": place_details.get('formatted_phone_number', ''),
                    "website": place_details.get('website', ''),
                    "business_status": place_details.get('business_status', ''),
                    "types": place_details.get('types', [])
                },
                "rating_info": {
                    "overall_rating": place_details.get('rating', 0),
                    "total_reviews": place_details.get('user_ratings_total', 0)
                },
                "reviews": reviews,
                "review_statistics": review_stats,
                "sentiment_analysis": sentiment_analysis,
                "source": "google_places_api",
                "data_quality": {
                    "reviews_available": len(reviews) > 0,
                    "rating_available": place_details.get('rating') is not None,
                    "contact_info_available": bool(place_details.get('formatted_phone_number') or place_details.get('website'))
                }
            }
            
            return places_data
            
        except Exception as e:
            logger.error(f"Error processing places data: {e}")
            return self._get_empty_places_data(vendor_name, f"Data processing error: {str(e)}")
    
    def _calculate_review_stats(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate statistics from reviews.
        """
        if not reviews:
            return {
                "total_reviews": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "recent_reviews_count": 0
            }
        
        ratings = [review.get('rating', 0) for review in reviews if review.get('rating')]
        
        # Calculate rating distribution
        rating_distribution = {}
        for rating in range(1, 6):
            rating_distribution[str(rating)] = ratings.count(rating)
        
        # Count recent reviews (within last 6 months)
        current_time = time.time()
        six_months_ago = current_time - (6 * 30 * 24 * 60 * 60)  # 6 months in seconds
        recent_reviews = [r for r in reviews if r.get('time', 0) > six_months_ago]
        
        return {
            "total_reviews": len(reviews),
            "average_rating": sum(ratings) / len(ratings) if ratings else 0,
            "rating_distribution": rating_distribution,
            "recent_reviews_count": len(recent_reviews)
        }
    
    def _analyze_review_sentiment(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze sentiment of reviews based on ratings and text content.
        """
        if not reviews:
            return {
                "overall_sentiment": "neutral",
                "positive_reviews": 0,
                "negative_reviews": 0,
                "neutral_reviews": 0,
                "sentiment_score": 0.5
            }
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for review in reviews:
            rating = review.get('rating', 0)
            text = review.get('text', '').lower()
            
            # Simple sentiment analysis based on rating and keywords
            if rating >= 4:
                positive_count += 1
            elif rating <= 2:
                negative_count += 1
            else:
                # For 3-star reviews, check text for sentiment
                positive_keywords = ['good', 'great', 'excellent', 'amazing', 'love', 'recommend', 'helpful', 'professional']
                negative_keywords = ['bad', 'terrible', 'awful', 'hate', 'disappointed', 'poor', 'unprofessional', 'waste']
                
                positive_score = sum(1 for keyword in positive_keywords if keyword in text)
                negative_score = sum(1 for keyword in negative_keywords if keyword in text)
                
                if positive_score > negative_score:
                    positive_count += 1
                elif negative_score > positive_score:
                    negative_count += 1
                else:
                    neutral_count += 1
        
        total_reviews = len(reviews)
        sentiment_score = (positive_count + 0.5 * neutral_count) / total_reviews if total_reviews > 0 else 0.5
        
        if sentiment_score >= 0.7:
            overall_sentiment = "positive"
        elif sentiment_score <= 0.3:
            overall_sentiment = "negative"
        else:
            overall_sentiment = "neutral"
        
        return {
            "overall_sentiment": overall_sentiment,
            "positive_reviews": positive_count,
            "negative_reviews": negative_count,
            "neutral_reviews": neutral_count,
            "sentiment_score": sentiment_score
        }
    
    def _get_empty_places_data(self, vendor_name: str, error: str = None) -> Dict[str, Any]:
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
