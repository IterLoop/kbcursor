import requests
import logging
import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from scripts.config import HF_CONFIG, MONGO_CONFIG
from tools.mongo import MongoDB

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchTermGenerator:
    def __init__(self):
        """Initialize the search term generator with MongoDB connection."""
        self.mongo = MongoDB(
            mongo_url=MONGO_CONFIG['MONGO_DB_URL'],
            db_name=MONGO_CONFIG['MONGODB_DB_NAME1']
        )
        self.article_requests = self.mongo.db['article_requests']

    def clean_search_terms(self, text: str) -> list:
        """Clean and extract search terms from the generated text."""
        # Remove any prefixes and numbering
        text = re.sub(r'^.*?(?:search terms:|terms:|list:|here:)', '', text, flags=re.IGNORECASE|re.DOTALL)
        
        # Split by commas or newlines
        terms = re.split(r'[,\n]', text)
        
        # Clean each term
        terms = [
            # Remove numbering and clean whitespace
            re.sub(r'^\d+\.\s*', '', term.strip())
            for term in terms
            if term.strip()
        ]
        
        # Filter out terms that are too short or incomplete
        terms = [term for term in terms if len(term) > 2]  # Remove single letters or very short terms
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            # Convert to lowercase for comparison
            term_lower = term.lower()
            # Skip time-related terms that are too generic
            if term_lower in {'last 3 months', 'past 3 months', 'last 90 days', 'recent', 'current events'}:
                continue
            # Check if this term or a similar term is already included
            if not any(term_lower in seen_term.lower() or seen_term.lower() in term_lower for seen_term in seen):
                unique_terms.append(term)
                seen.add(term_lower)
        
        return unique_terms

    def get_term_count_range(self, imagination_level: int, research_level: int) -> tuple:
        """
        Determine the range of search terms to generate based on imagination and research levels.
        Higher levels result in more terms.
        
        Args:
            imagination_level (int): 1-5 scale
            research_level (int): 1-5 scale
            
        Returns:
            tuple: (min_terms, max_terms)
        """
        # Base range is 5-8 terms
        base_min = 5
        base_max = 8
        
        # Calculate additional terms based on levels
        # Each level above 3 adds to the range
        imagination_bonus = max(0, imagination_level - 3) * 2
        research_bonus = max(0, research_level - 3) * 2
        
        # Calculate final range
        min_terms = base_min + min(imagination_bonus, research_bonus)
        max_terms = base_max + imagination_bonus + research_bonus
        
        return (min_terms, max_terms)

    def format_article_prompt(self, topic: str, params: Dict) -> str:
        """Format the prompt with article parameters."""
        imagination_level = params.get('imagination_level', 3)
        research_level = params.get('research_level', 3)
        audience = params.get('audience', 'general')
        style = params.get('style', 'neutral')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        
        # Get term count range based on levels
        min_terms, max_terms = self.get_term_count_range(imagination_level, research_level)
        
        # Build prompt guidance based on levels
        guidance = []
        if imagination_level >= 4:
            guidance.append("Include creative and innovative perspectives")
        if imagination_level >= 5:
            guidance.append("Explore unconventional and forward-thinking angles")
            
        if research_level >= 4:
            guidance.append("Include technical and specialized terms")
        if research_level >= 5:
            guidance.append("Add academic and research-specific terminology")
            
        guidance_text = ". ".join(guidance) + "." if guidance else ""
        
        date_range = ""
        if date_from and date_to:
            date_range = f" within date range {date_from} to {date_to}"
        
        return (
            f"Topic: {topic}\n"
            f"Parameters:\n"
            f"- Audience: {audience}\n"
            f"- Style: {style}\n"
            f"- Imagination Level: {imagination_level}/5\n"
            f"- Research Level: {research_level}/5{date_range}\n"
            f"- Required Terms: {min_terms}-{max_terms}\n\n"
            f"Additional Guidance: {guidance_text}\n"
        )

    def generate_search_terms(self, topic: str, params: Optional[Dict] = None) -> List[str]:
        """
        Generate search terms using Hugging Face Inference API.
        
        Args:
            topic (str): The main topic or subject
            params (Dict): Optional parameters including:
                - imagination_level (int): 1-5 scale
                - research_level (int): 1-5 scale
                - audience (str): Target audience
                - style (str): Writing style
                - date_from (str): Start date
                - date_to (str): End date
        
        Returns:
            list: List of generated search terms
        """
        try:
            # Get API token from config
            api_token = HF_CONFIG['API_TOKENS']['INFERENCE']
            if not api_token:
                raise ValueError("HF_INFERENCE_TOKEN not found in config")
            
            # Format the article prompt
            article_prompt = self.format_article_prompt(topic, params or {})
            
            # Hugging Face Inference API endpoint
            API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
            
            # Headers for authentication
            headers = {"Authorization": f"Bearer {api_token}"}
            
            # Get term count range
            min_terms, max_terms = self.get_term_count_range(
                params.get('imagination_level', 3),
                params.get('research_level', 3)
            )
            
            # Prepare the prompt with examples
            system_prompt = (
                f"Generate {min_terms}-{max_terms} specific and diverse search terms that comprehensively capture the "
                "key aspects of the following article request. Ensure the terms are tightly aligned with the given "
                "topic, audience, writing style, and other parameters. Focus on the central themes, related concepts, "
                "relevant methodologies, potential challenges and solutions, and important subtopics.\n\n"
                "Here are examples of search term sets that are well-aligned with the article request:\n\n"
                "1. Article Request:\n"
                "   Topic: Renewable energy adoption in urban areas\n" 
                "   Audience: Policymakers and city planners\n"
                "   Style: Persuasive\n"
                "   Research Level: 5\n"
                "   Terms: municipal renewable energy policies, urban solar incentives, city-level renewable portfolio standards, "
                "green building codes, net metering for urban solar, financing mechanisms for urban renewables, "
                "city renewable energy targets, zoning for urban wind power, microgrid deployment in cities\n\n"
                "2. Article Request:\n"
                "   Topic: Artificial intelligence in personalized education\n"
                "   Audience: Educators and EdTech professionals\n" 
                "   Style: Informative\n"
                "   Imagination Level: 4\n"
                "   Terms: AI-powered adaptive learning platforms, intelligent tutoring systems, AI curriculum customization, "
                "AI-driven formative assessment, knowledge tracing with AI, AI-enhanced project-based learning, "
                "AI for identifying learning gaps, ethics of AI in education, data privacy in AI-powered EdTech\n\n"
                "Now, generate an aligned set of search terms for this article request:\n\n"
                f"{article_prompt}"
            )
            
            payload = {
                "inputs": system_prompt,
                "parameters": {
                    "max_new_tokens": 250,  # Increased for more terms
                    "temperature": 0.7,
                    "return_full_text": False
                }
            }
            
            # Make API request
            logger.info(f"Sending request to Hugging Face API for prompt: {article_prompt}")
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            logger.info(f"API Response: {result}")
            
            # Extract and clean search terms
            if isinstance(result, list) and len(result) > 0:
                search_terms = self.clean_search_terms(result[0]["generated_text"])
                logger.info(f"Extracted search terms: {search_terms}")
                
                # Store search terms in database
                self.store_search_terms(topic, search_terms, params)
                
                return search_terms
            else:
                logger.warning("Unexpected API response format")
                return []
                
        except Exception as e:
            logger.exception(f"Error generating search terms: {str(e)}")
            raise

    def store_search_terms(self, topic: str, search_terms: List[str], params: Optional[Dict] = None) -> None:
        """Store the generated search terms by updating or creating an article request document."""
        try:
            # Find the most recent article request for this topic
            article_request = self.article_requests.find_one(
                {"outline": topic},
                sort=[("created_at", -1)]
            )
            
            if not article_request:
                # Create a new article request document if one doesn't exist
                logger.info(f"No article request found for topic: {topic}. Creating a new one...")
                article_request = {
                    "outline": topic,
                    "created_at": datetime.utcnow(),
                    "status": "search_terms_generated"
                }
                result = self.article_requests.insert_one(article_request)
                article_request["_id"] = result.inserted_id
            else:
                logger.info(f"Found existing article request for topic: {topic}. Updating search terms...")
            
            # Update the article request with search terms
            update_data = {
                "search_terms": search_terms,
                "search_terms_generated_at": datetime.utcnow(),
                "search_parameters": params or {},
                "status": "search_terms_generated"
            }
            
            result = self.article_requests.update_one(
                {"_id": article_request["_id"]},
                {"$set": update_data}
            )
            
            logger.info(f"Updated article request {article_request['_id']} with search terms")
            
        except Exception as e:
            logger.exception(f"Error storing search terms in article_requests: {str(e)}")
            raise

def main():
    # Test article parameters with high imagination and research levels
    test_params = {
        "topic": "artificial intelligence privacy concerns in healthcare",
        "imagination_level": 2,  # Maximum imagination
        "research_level": 5,     # Maximum research
        "audience": "General",
        "style": "analytical",
        "date_from": "2024-01-01",
        "date_to": "2024-03-31"
    }
    
    try:
        # Initialize generator and generate search terms
        logger.info("Initializing SearchTermGenerator...")
        generator = SearchTermGenerator()
        
        logger.info("Generating search terms with parameters: %s", test_params)
        search_terms = generator.generate_search_terms(
            topic=test_params["topic"],
            params=test_params
        )
        
        print("\nGenerated Search Terms:")
        for i, term in enumerate(search_terms, 1):
            print(f"{i}. {term}")
            
    except Exception as e:
        logger.error("Failed to generate search terms: %s", str(e), exc_info=True)
        print(f"Failed to generate search terms: {str(e)}")

if __name__ == "__main__":
    main() 