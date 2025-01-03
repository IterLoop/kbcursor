from apify_client import ApifyClient
import json
import os
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import re
import markdown

def download_nltk_data():
    """Download required NLTK data packages"""
    required_packages = ['punkt', 'stopwords', 'averaged_perceptron_tagger']
    for package in required_packages:
        try:
            nltk.data.find(f'tokenizers/{package}')
        except LookupError:
            print(f"Downloading {package}...")
            nltk.download(package, quiet=True)

class ContentCrawler:
    def __init__(self, api_key: str):
        self.client = ApifyClient(api_key)
        self.actor_id = "apify/website-content-crawler"
        # Download required NLTK data
        download_nltk_data()

    def read_urls(self, input_file: str) -> list:
        """Read URLs from input file"""
        with open(input_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def crawl_websites(self, urls: list) -> list:
        """Crawl websites using Apify website content crawler"""
        run_input = {
            "startUrls": [{"url": url} for url in urls],
            "maxCrawlingDepth": 1,
            "maxPagesPerCrawl": 10,
            "maxConcurrency": 5,
            "additionalMimeTypes": ["text/markdown", "text/plain"],
            "excludes": [
                {"glob": "*.{png,jpg,jpeg,gif,pdf,zip,mp4,mp3,avi}"},
                {"glob": "*google*"},
                {"glob": "*facebook*"},
                {"glob": "*twitter*"},
                {"glob": "*linkedin*"}
            ]
        }

        # Run the actor and wait for it to finish
        run = self.client.actor(self.actor_id).call(run_input=run_input)
        
        # Fetch results from the actor's default dataset
        results = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(item)
        
        return results

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
                print(f"Warning: Sentence tokenization failed, falling back to simple split: {str(e)}")
                sentences = [s.strip() for s in text.split('.') if s.strip()]
            
            # Get stop words
            try:
                stop_words = set(stopwords.words('english'))
            except Exception as e:
                print(f"Warning: Stop words loading failed: {str(e)}")
                stop_words = set()
            
            # Clean sentences
            cleaned_sentences = []
            for sentence in sentences:
                try:
                    # Tokenize words
                    words = word_tokenize(sentence)
                    # Remove stop words and short words
                    words = [word for word in words if word not in stop_words and len(word) > 2]
                    # Rejoin words
                    if words:
                        cleaned_sentences.append(' '.join(words))
                except Exception as e:
                    print(f"Warning: Sentence cleaning failed: {str(e)}")
                    if sentence.strip():
                        cleaned_sentences.append(sentence.strip())
            
            return '\n\n'.join(cleaned_sentences)
            
        except Exception as e:
            print(f"Warning: Text cleaning encountered an error: {str(e)}")
            return text  # Return original text if cleaning fails

    def convert_to_markdown(self, content: dict) -> str:
        """Convert crawled content to markdown format"""
        md_content = f"# {content.get('title', 'Untitled')}\n\n"
        
        if content.get('text'):
            cleaned_text = self.clean_text(content['text'])
            md_content += cleaned_text
        
        return md_content

    def save_markdown(self, markdown_content: str, output_file: str):
        """Save content as markdown file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

def main():
    # Initialize the crawler with your API key
    api_key = "apify_api_RqJ95dSauHAkMv1WGiajI2ysI8zAlg04FzoV"
    
    try:
        print("Initializing crawler and downloading required NLTK data...")
        crawler = ContentCrawler(api_key)
        
        # Read URLs from file
        print("Reading URLs...")
        try:
            urls = crawler.read_urls("cleaned_urls.txt")
            if not urls:
                print("Warning: No URLs found in cleaned_urls.txt")
                return
            print(f"Found {len(urls)} URLs to process")
        except FileNotFoundError:
            print("Error: cleaned_urls.txt not found")
            return
        except Exception as e:
            print(f"Error reading URLs: {str(e)}")
            return
        
        # Crawl websites
        print("Starting crawler...")
        try:
            results = crawler.crawl_websites(urls)
            if not results:
                print("Warning: No content was crawled")
                return
            print(f"Successfully crawled {len(results)} pages")
        except Exception as e:
            print(f"Error during crawling: {str(e)}")
            return
        
        # Process each result
        print("Processing results...")
        for i, result in enumerate(results):
            try:
                # Convert to markdown and clean
                print(f"Processing page {i+1}/{len(results)}...")
                markdown_content = crawler.convert_to_markdown(result)
                
                # Save to file
                output_file = f"crawled_content_{i+1}.md"
                crawler.save_markdown(markdown_content, output_file)
                print(f"Saved content to {output_file}")
            except Exception as e:
                print(f"Error processing result {i+1}: {str(e)}")
                continue

        print("Crawling completed successfully!")

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
