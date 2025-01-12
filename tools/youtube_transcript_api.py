"""YouTube transcript extraction using youtube_transcript_api."""

import logging
from typing import Dict, Any, Optional, List
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YouTubeTranscriptAPI:
    """YouTube transcript API wrapper."""
    
    def get_transcript(self, video_id: str, language: str = 'en') -> Optional[Dict[str, Any]]:
        """Get transcript for a video.
        
        Args:
            video_id: YouTube video ID
            language: Preferred language code
            
        Returns:
            Dictionary containing transcript text and language
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript([language])
            result = transcript.fetch()
            
            # Combine all transcript parts into one text
            text = ' '.join(part['text'] for part in result)
            
            return {
                'text': text,
                'language': language
            }
            
        except Exception as e:
            logger.error(f"Error getting transcript for video {video_id}: {str(e)}")
            return None
    
    def get_available_languages(self, video_id: str) -> List[str]:
        """Get available transcript languages for a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            List of available language codes
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            return [t.language_code for t in transcript_list]
            
        except Exception as e:
            logger.error(f"Error getting available languages for video {video_id}: {str(e)}")
            return []
    
    def translate_transcript(self, video_id: str, target_lang: str) -> Optional[Dict[str, Any]]:
        """Translate transcript to target language.
        
        Args:
            video_id: YouTube video ID
            target_lang: Target language code
            
        Returns:
            Dictionary containing translated text and language
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Get English transcript first (or any available transcript)
            transcript = None
            for lang in ['en', 'en-US', 'en-GB']:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except:
                    continue
                    
            if not transcript:
                # If no English transcript, get the first available one
                transcript = transcript_list.find_transcript([])
            
            # Translate to target language
            translated = transcript.translate(target_lang)
            result = translated.fetch()
            
            # Combine all transcript parts into one text
            text = ' '.join(part['text'] for part in result)
            
            return {
                'text': text,
                'language': target_lang
            }
            
        except Exception as e:
            logger.error(f"Error translating transcript for video {video_id}:\n{str(e)}")
            return None 