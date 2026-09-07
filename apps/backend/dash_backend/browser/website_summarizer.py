"""Website Summarizer - Summarize and analyze web content."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class WebsiteSummary:
    """Summary of a website."""
    url: str
    title: str
    summary: str
    key_points: List[str]
    main_topics: List[str]
    reading_time_minutes: int
    word_count: int
    sentiment: str = "neutral"
    
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "key_points": self.key_points,
            "main_topics": self.main_topics,
            "reading_time_minutes": self.reading_time_minutes,
            "word_count": self.word_count,
            "sentiment": self.sentiment,
        }


class WebsiteSummarizer:
    """Summarizes and analyzes website content.
    
    Features:
    - Extract main content
    - Generate summary
    - Extract key points
    - Identify main topics
    - Estimate reading time
    - Analyze sentiment
    - Extract metadata
    """
    
    def __init__(self):
        self._min_summary_length = 50
        self._max_summary_length = 500
        
    async def summarize(
        self,
        url: str,
        content: str,
        title: str = "",
    ) -> WebsiteSummary:
        """Summarize a website.
        
        Args:
            url: Website URL
            content: Page content
            title: Page title
            
        Returns:
            WebsiteSummary
        """
        # Clean content
        clean_content = self._clean_content(content)
        
        # Extract key information
        word_count = len(clean_content.split())
        reading_time = max(1, word_count // 200)  # Average 200 words per minute
        
        # Generate summary
        summary = self._generate_summary(clean_content)
        
        # Extract key points
        key_points = self._extract_key_points(clean_content)
        
        # Identify topics
        topics = self._extract_topics(clean_content)
        
        # Analyze sentiment
        sentiment = self._analyze_sentiment(clean_content)
        
        return WebsiteSummary(
            url=url,
            title=title or self._extract_title(content),
            summary=summary,
            key_points=key_points,
            main_topics=topics,
            reading_time_minutes=reading_time,
            word_count=word_count,
            sentiment=sentiment,
        )
    
    def _clean_content(self, content: str) -> str:
        """Clean HTML/content to extract main text."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', content)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common navigation/footer patterns
        patterns = [
            r'menu|navigation|nav|footer|copyright|subscribe',
            r'cookie|privacy|terms|conditions',
            r'login|sign in|register|sign up',
        ]
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip lines matching patterns
            skip = False
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    skip = True
                    break
            
            if not skip and len(line) > 20:
                cleaned_lines.append(line)
        
        return ' '.join(cleaned_lines)
    
    def _generate_summary(self, content: str) -> str:
        """Generate a summary of the content."""
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return "No content available to summarize."
        
        # Take first few sentences for summary
        summary_sentences = sentences[:3]
        summary = '. '.join(summary_sentences)
        
        # Truncate if too long
        if len(summary) > self._max_summary_length:
            summary = summary[:self._max_summary_length - 3] + "..."
        
        return summary
    
    def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from content."""
        key_points = []
        
        # Look for bullet points or numbered lists
        bullet_patterns = [
            r'•\s*(.+)',
            r'-\s*(.+)',
            r'\*\s*(.+)',
            r'\d+\.\s*(.+)',
        ]
        
        for pattern in bullet_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                point = match.strip()
                if len(point) > 10 and len(point) < 200:
                    key_points.append(point)
        
        # If no bullets found, extract important sentences
        if not key_points:
            sentences = re.split(r'[.!?]+', content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 50 and len(sentence) < 200:
                    # Check for important keywords
                    if any(keyword in sentence.lower() for keyword in 
                          ['important', 'key', 'main', 'significant', 'crucial']):
                        key_points.append(sentence)
        
        return key_points[:5]  # Return top 5
    
    def _extract_topics(self, content: str) -> List[str]:
        """Extract main topics from content."""
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())
        
        # Count word frequency
        word_freq = {}
        for word in words:
            if word not in ['this', 'that', 'with', 'from', 'have', 'will', 'more']:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        topics = [word for word, count in sorted_words[:10]]
        
        return topics
    
    def _analyze_sentiment(self, content: str) -> str:
        """Analyze sentiment of content."""
        positive_words = [
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
            'success', 'successful', 'benefit', 'beneficial', 'positive',
            'love', 'enjoy', 'happy', 'pleased', 'satisfied',
        ]
        
        negative_words = [
            'bad', 'terrible', 'awful', 'horrible', 'poor', 'negative',
            'failure', 'fail', 'problem', 'issue', 'concern',
            'hate', 'dislike', 'unhappy', 'disappointed', 'frustrated',
        ]
        
        content_lower = content.lower()
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count > negative_count * 1.5:
            return "positive"
        elif negative_count > positive_count * 1.5:
            return "negative"
        else:
            return "neutral"
    
    def _extract_title(self, content: str) -> str:
        """Extract title from content."""
        # Try to find title tag
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        
        # Try to find h1 tag
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE)
        if h1_match:
            return h1_match.group(1).strip()
        
        return ""
    
    async def fact_check(self, content: str, claims: List[str]) -> Dict[str, Any]:
        """Fact-check claims against content.
        
        Args:
            content: Content to check against
            claims: Claims to verify
            
        Returns:
            Fact check results
        """
        results = {}
        
        for claim in claims:
            # Simple check: see if claim is mentioned in content
            claim_lower = claim.lower()
            content_lower = content.lower()
            
            if claim_lower in content_lower:
                results[claim] = {
                    "found": True,
                    "confidence": "high",
                    "context": self._get_context(content_lower, claim_lower),
                }
            else:
                # Check for partial matches
                words = claim_lower.split()
                matches = sum(1 for word in words if word in content_lower)
                
                if matches >= len(words) * 0.5:
                    results[claim] = {
                        "found": True,
                        "confidence": "medium",
                        "context": "Partial match found",
                    }
                else:
                    results[claim] = {
                        "found": False,
                        "confidence": "low",
                        "context": "No match found",
                    }
        
        return results
    
    def _get_context(self, content: str, claim: str, context_length: int = 200) -> str:
        """Get context around a claim."""
        index = content.find(claim)
        if index == -1:
            return ""
        
        start = max(0, index - context_length // 2)
        end = min(len(content), index + len(claim) + context_length // 2)
        
        return content[start:end].strip()


_website_summarizer: Optional[WebsiteSummarizer] = None


def get_website_summarizer() -> WebsiteSummarizer:
    global _website_summarizer
    if _website_summarizer is None:
        _website_summarizer = WebsiteSummarizer()
    return _website_summarizer
