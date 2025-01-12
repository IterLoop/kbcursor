import requests
import logging
import sys
import os
import re
from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from scripts.config import HF_CONFIG, MONGO_CONFIG
from tools.mongo import MongoDB

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SearchTermGenerator:
    def __init__(self):
        """Initialize the search term generator with MongoDB connection."""
        self.mongo = MongoDB(
            mongo_url=MONGO_CONFIG['MONGO_DB_URL'],
            db_name=MONGO_CONFIG['MONGODB_DB_NAME1']
        )
        self.article_requests = self.mongo.db['article_requests']

    def validate_search_terms(self, terms: List[str], min_terms: int, max_terms: int) -> Tuple[bool, str]:
        """
        Validate the generated search terms against requirements.
        
        Args:
            terms: List of search terms
            min_terms: Minimum required terms
            max_terms: Maximum allowed terms
            
        Returns:
            Tuple of (is_valid, message)
        """
        term_count = len(terms)
        
        # Check term count
        if term_count < min_terms:
            return False, f"Generated only {term_count} terms, minimum required is {min_terms}"
        if term_count > max_terms:
            return False, f"Generated {term_count} terms, exceeding maximum of {max_terms}"
            
        # Check term quality
        short_terms = [t for t in terms if len(t.split()) < 2]
        if len(short_terms) > term_count * 0.2:  # No more than 20% single-word terms
            return False, f"Too many single-word terms ({len(short_terms)})"
            
        # Check for structural artifacts
        artifact_terms = [t for t in terms if any(x in t.lower() for x in ['terms:', 'list:', '.', ')', '('])]
        if artifact_terms:
            return False, f"Found terms with structural artifacts: {artifact_terms}"
            
        return True, f"Generated {term_count} valid terms"

    def clean_search_terms(self, text: str) -> list:
        """Clean and extract search terms from the generated text."""
        # Remove any prefixes and numbering
        text = re.sub(r'^.*?(?:search terms:|terms:|list:|here:)', '', text, flags=re.IGNORECASE|re.DOTALL)
        
        # Split by commas or newlines
        terms = re.split(r'[,\n]', text)
        
        # Clean each term
        terms = [
            # Remove numbering, punctuation, and clean whitespace
            re.sub(r'^\d+\.\s*|\.$|\)$|\s*[\(\)]\s*', '', term.strip())
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
            # Skip structural artifacts
            if any(x in term_lower for x in ['terms:', 'list:', 'example:', 'topic:']):
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
        
        logger.info(f"Term count range: {min_terms}-{max_terms} (imagination_bonus={imagination_bonus}, research_bonus={research_bonus})")
        return (min_terms, max_terms)

    def format_article_prompt(self, topic: str, params: Dict) -> str:
        """
        Format the prompt with article parameters.
        
        Args:
            topic (str): The main topic for search term generation
            params (Dict): Dictionary containing generation parameters
            
        Returns:
            str: Formatted prompt string
        """
        imagination_level = params.get('imagination_level', 3)
        research_level = params.get('research_level', 3)
        audience = params.get('audience', 'general')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        
        # Get term count range based on levels
        min_terms, max_terms = self.get_term_count_range(
            imagination_level,
            research_level
        )
        
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
        generation_start = datetime.now(UTC)
        try:
            logger.info("Starting search term generation process...")
            logger.info(f"Parameters: {params}")
            
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
                "   Topic: Sustainable fashion trends\n"
                "   Audience: Fashion industry professionals\n" 
                "   Style: Technical\n"
                "   Research Level: 4\n"
                "   Imagination Level: 2\n"
                "   Terms: circular fashion business models, textile recycling technologies, sustainable fiber innovations, "
                "eco-friendly dyeing processes, fashion supply chain transparency, zero-waste pattern cutting, "
                "blockchain in fashion traceability, sustainable fashion certifications, garment end-of-life management\n\n"
                "2. Article Request:\n"
                "   Topic: Mental health in remote work\n"
                "   Audience: HR managers\n"
                "   Style: Analytical\n" 
                "   Research Level: 3\n"
                "   Imagination Level: 3\n"
                "   Terms: remote work burnout prevention, virtual team building strategies, digital wellness programs, "
                "remote employee engagement metrics, work-from-home mental health policies, virtual counseling platforms, "
                "remote work-life balance strategies, digital stress management tools\n\n"
                "3. Article Request:\n"
                "   Topic: Future of autonomous vehicles\n"
                "   Audience: Technology enthusiasts\n"
                "   Style: Visionary\n"
                "   Research Level: 2\n"
                "   Imagination Level: 5\n"
                "   Terms: next-gen autonomous sensors, self-healing vehicle systems, AI traffic orchestration, "
                "autonomous vehicle social interaction, flying autonomous vehicles, robotic vehicle maintenance, "
                "autonomous vehicle entertainment systems, inter-vehicle communication networks\n\n"
                "4. Article Request:\n"
                "   Topic: Urban vertical farming\n"
                "   Audience: Agricultural entrepreneurs\n"
                "   Style: Practical\n"
                "   Research Level: 5\n"
                "   Imagination Level: 3\n"
                "   Terms: hydroponic system optimization, LED grow light efficiency, vertical farm automation systems, "
                "urban agriculture ROI analysis, controlled environment agriculture, vertical farming nutrient management, "
                "urban farm space utilization, vertical farming energy consumption, crop selection for vertical farms\n\n"
                "5. Article Request:\n"
                "   Topic: Quantum computing applications\n"
                "   Audience: Business executives\n"
                "   Style: Strategic\n"
                "   Research Level: 3\n"
                "   Imagination Level: 4\n"
                "   Terms: quantum advantage use cases, quantum-ready business strategy, quantum risk assessment, "
                "quantum computing ROI projections, quantum-safe cybersecurity, quantum computing service providers, "
                "quantum algorithm business applications, quantum computing talent acquisition\n\n"
                "6. Article Request:\n"
                "   Topic: Renewable energy storage solutions\n"
                "   Audience: Energy sector professionals\n"
                "   Style: Technical\n"
                "   Research Level: 5\n"
                "   Imagination Level: 3\n"
                "   Terms: grid-scale battery technologies, flow battery advancements, thermal energy storage systems, "
                "hydrogen storage infrastructure, compressed air energy storage, phase change materials in energy storage, "
                "energy storage economics, battery recycling technologies, smart grid integration strategies\n\n"
                "7. Article Request:\n"
                "   Topic: Digital art and NFT marketplaces\n"
                "   Audience: Artists and collectors\n"
                "   Style: Contemporary\n"
                "   Research Level: 3\n"
                "   Imagination Level: 5\n"
                "   Terms: emerging NFT platforms comparison, digital art authentication methods, blockchain art royalties, "
                "virtual gallery technologies, NFT environmental impact solutions, digital art curation tools, "
                "metaverse art exhibitions, NFT market analytics, cross-platform NFT integration\n\n"
                "8. Article Request:\n"
                "   Topic: Personalized medicine advances\n"
                "   Audience: Healthcare professionals\n"
                "   Style: Scientific\n"
                "   Research Level: 5\n"
                "   Imagination Level: 4\n"
                "   Terms: genomic medicine applications, AI-driven drug development, patient-specific treatment protocols, "
                "biomarker identification methods, precision oncology advances, pharmacogenomic testing standards, "
                "personalized immunotherapy approaches, digital twin healthcare models, targeted therapy optimization\n\n"
                "Examples of poor search term generation to avoid:\n\n"
                "Bad Example 1:\n"
                "   Topic: AI privacy concerns in healthcare\n"
                "   Problem: Terms lose healthcare context and become too generic\n"
                "   Poor Terms: GDPR compliance requirements, CCPA regulations, data encryption methods, "
                "cybersecurity best practices, identity verification systems, access management protocols\n"
                "   Why it's bad: These terms could apply to any industry and lose the healthcare focus\n\n"
                "Bad Example 2:\n"
                "   Topic: AI privacy concerns in healthcare\n"
                "   Problem: Terms have formatting issues and unclear abbreviations\n"
                "   Poor Terms: Health Information ExchangeHIEand interoperability, AI/MLHealthcare, "
                "PrivacyAIHealth, HIPAA_compliance_rules\n"
                "   Why it's bad: Terms are poorly formatted and hard to read\n\n"
                "Guidelines for high-quality terms:\n"
                "- Maintain consistent context with the main topic\n"
                "- Use proper spacing and formatting\n"
                "- Spell out abbreviations on first use\n"
                "- Ensure each term is specific and actionable\n"
                "- Combine relevant concepts meaningfully\n\n"
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
            logger.info("Sending request to Hugging Face API...")
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            logger.debug(f"API Response: {result}")
            
            # Extract and clean search terms
            if isinstance(result, list) and len(result) > 0:
                raw_terms = self.clean_search_terms(result[0]["generated_text"])
                
                # Validate terms
                is_valid, validation_msg = self.validate_search_terms(raw_terms, min_terms, max_terms)
                logger.info(f"Term validation: {validation_msg}")
                
                if not is_valid:
                    logger.warning("Generated terms did not meet quality requirements")
                
                # Store search terms in database
                self.store_search_terms(topic, raw_terms, params)
                
                # Log generation summary
                generation_time = datetime.now(UTC) - generation_start
                logger.info(
                    f"\nSearch Term Generation Summary:\n"
                    f"- Topic: {topic}\n"
                    f"- Style: {params.get('style', 'neutral')}\n"
                    f"- Audience: {params.get('audience', 'general')}\n"
                    f"- Terms Generated: {len(raw_terms)}\n"
                    f"- Generation Time: {generation_time.total_seconds():.2f}s\n"
                    f"- Validation: {validation_msg}\n"
                )
                
                return raw_terms
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
                    "created_at": datetime.now(UTC),
                    "status": "search_terms_generated"
                }
                result = self.article_requests.insert_one(article_request)
                article_request["_id"] = result.inserted_id
            else:
                logger.info(f"Found existing article request for topic: {topic}. Updating search terms...")
            
            # Update the article request with search terms
            update_data = {
                "search_terms": search_terms,
                "search_terms_generated_at": datetime.now(UTC),
                "search_parameters": params or {},
                "status": "search_terms_generated"
            }
            
            result = self.article_requests.update_one(
                {"_id": article_request["_id"]},
                {"$set": update_data}
            )
            
            logger.info(f"Updated article request {article_request['_id']} with {len(search_terms)} search terms")
            
        except Exception as e:
            logger.exception(f"Error storing search terms in article_requests: {str(e)}")
            raise

def main():
    """Run test generation with sample parameters."""
    # Test article parameters with high imagination and research levels
    test_params = {
        "topic": "artificial intelligence tariff concerns in supply chain",
        "imagination_level": 2,  # Maximum imagination
        "research_level": 5,     # Maximum research
        "audience": "general",
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