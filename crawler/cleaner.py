import re
from bs4 import BeautifulSoup
import markdown
import html
from typing import Optional
from .crawler import WebContent

class TextCleaner:
    @staticmethod
    def clean_html(html_content: str) -> str:
        """Remove HTML tags and clean up the text"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'head', 'title', 'meta', '[document]']):
            element.decompose()
            
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, str) and '<!--' in text):
            comment.extract()
            
        text = soup.get_text()
        
        # Remove extra whitespace and normalize line endings
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean raw text by removing special characters and normalizing whitespace"""
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
        
        # Remove multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        
        # Remove extra spaces around punctuation
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        
        return text.strip()

    def clean_web_content(self, content: WebContent) -> WebContent:
        """Clean WebContent object by cleaning both title and text"""
        cleaned_text = self.clean_text(self.clean_html(content.text))
        cleaned_title = self.clean_text(content.title) if content.title else None
        
        return WebContent(
            url=content.url,
            title=cleaned_title,
            text=cleaned_text,
            metadata=content.metadata,
            source=content.source
        )

    def to_markdown(self, content: WebContent) -> str:
        """Convert WebContent to markdown format with metadata"""
        md_parts = []
        
        # Add title
        if content.title:
            md_parts.append(f"# {content.title}\n")
        
        # Add metadata section
        md_parts.append("## Metadata\n")
        md_parts.append(f"- Source: {content.source}")
        md_parts.append(f"- URL: {content.url}")
        for key, value in content.metadata.items():
            if value:
                md_parts.append(f"- {key}: {value}")
        md_parts.append("\n")
        
        # Add content section
        md_parts.append("## Content\n")
        md_parts.append(content.text)
        
        return "\n".join(md_parts) 