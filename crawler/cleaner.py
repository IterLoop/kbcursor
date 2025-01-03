import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class TextCleaner:
    def __init__(self):
        self._ensure_nltk_data()
        self.stop_words = set(stopwords.words('english'))
    
    def _ensure_nltk_data(self):
        """Ensure all required NLTK data is downloaded"""
        required_packages = ['punkt', 'stopwords', 'averaged_perceptron_tagger']
        for package in required_packages:
            try:
                nltk.data.find(f'tokenizers/{package}')
            except LookupError:
                logger.info(f"Downloading NLTK package: {package}")
                nltk.download(package, quiet=True)
    
    def clean_text(self, text: str) -> str:
        """Clean text using NLP techniques"""
        if not text:
            return ""
        
        try:
            # Convert to lowercase
            text = text.lower()
            
            # Remove special characters and digits but keep periods for sentence breaks
            text = re.sub(r'[^a-zA-Z\s.]', '', text)
            
            # Remove extra whitespace
            text = ' '.join(text.split())
            
            # Tokenize into sentences
            try:
                sentences = sent_tokenize(text)
            except Exception as e:
                logger.warning(f"Sentence tokenization failed, falling back to simple split: {e}")
                sentences = [s.strip() for s in text.split('.') if s.strip()]
            
            # Clean sentences
            cleaned_sentences = []
            for sentence in sentences:
                try:
                    # Tokenize words
                    words = word_tokenize(sentence)
                    # Remove stop words and short words
                    words = [word for word in words if word not in self.stop_words and len(word) > 2]
                    # Rejoin words
                    if words:
                        cleaned_sentences.append(' '.join(words))
                except Exception as e:
                    logger.warning(f"Sentence cleaning failed: {e}")
                    if sentence.strip():
                        cleaned_sentences.append(sentence.strip())
            
            return '\n\n'.join(cleaned_sentences)
            
        except Exception as e:
            logger.error(f"Text cleaning encountered an error: {e}")
            return text  # Return original text if cleaning fails
    
    def to_markdown(self, content) -> str:
        """Convert WebContent object to markdown format with metadata"""
        md_content = []
        
        # Add title
        md_content.append(f"# {content.title}\n")
        
        # Add metadata section
        md_content.append("## Metadata\n")
        md_content.append("```yaml")
        md_content.append(f"source: {content.source}")
        md_content.append(f"url: {content.url}")
        md_content.append(f"timestamp: {content.timestamp}")
        
        # Add all other metadata
        for key, value in content.metadata.items():
            if value:  # Only add non-empty values
                md_content.append(f"{key}: {value}")
        md_content.append("```\n")
        
        # Add cleaned content
        md_content.append("## Content\n")
        cleaned_text = self.clean_text(content.text)
        md_content.append(cleaned_text)
        
        return '\n'.join(md_content) 