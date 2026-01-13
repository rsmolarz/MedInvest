"""
Alpha Vantage News Service
Fetches and personalizes financial news for users
"""
import os
import requests
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Map user interests/specialties to Alpha Vantage topics
SPECIALTY_TOPIC_MAP = {
    'cardiology': ['life_sciences', 'technology'],
    'oncology': ['life_sciences', 'technology'],
    'radiology': ['life_sciences', 'technology'],
    'surgery': ['life_sciences'],
    'internal medicine': ['life_sciences', 'economy_macro'],
    'pediatrics': ['life_sciences'],
    'psychiatry': ['life_sciences'],
    'dermatology': ['life_sciences'],
    'orthopedics': ['life_sciences'],
    'neurology': ['life_sciences', 'technology'],
    'anesthesiology': ['life_sciences'],
    'emergency medicine': ['life_sciences'],
    'family medicine': ['life_sciences', 'economy_macro'],
}

# Investment-focused topics for all medical professionals
DEFAULT_INVESTMENT_TOPICS = [
    'real_estate',
    'finance',
    'economy_macro',
    'earnings',
    'technology',
]

# Sentiment labels and colors
SENTIMENT_LABELS = {
    'bullish': {'label': 'Bullish', 'color': 'success', 'icon': 'arrow-up'},
    'somewhat_bullish': {'label': 'Somewhat Bullish', 'color': 'success', 'icon': 'arrow-up'},
    'neutral': {'label': 'Neutral', 'color': 'secondary', 'icon': 'minus'},
    'somewhat_bearish': {'label': 'Somewhat Bearish', 'color': 'danger', 'icon': 'arrow-down'},
    'bearish': {'label': 'Bearish', 'color': 'danger', 'icon': 'arrow-down'},
}


def get_sentiment_label(score: float) -> Dict[str, str]:
    """Convert sentiment score to label and styling"""
    if score >= 0.35:
        return SENTIMENT_LABELS['bullish']
    elif score >= 0.15:
        return SENTIMENT_LABELS['somewhat_bullish']
    elif score >= -0.15:
        return SENTIMENT_LABELS['neutral']
    elif score >= -0.35:
        return SENTIMENT_LABELS['somewhat_bearish']
    else:
        return SENTIMENT_LABELS['bearish']


def format_published_time(time_str: str) -> str:
    """Convert Alpha Vantage time format to readable string"""
    try:
        dt = datetime.strptime(time_str, "%Y%m%dT%H%M%S")
        now = datetime.utcnow()
        diff = now - dt
        
        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes}m ago" if minutes > 0 else "Just now"
            return f"{hours}h ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return dt.strftime("%b %d, %Y")
    except:
        return time_str


def fetch_news(
    tickers: Optional[List[str]] = None,
    topics: Optional[List[str]] = None,
    limit: int = 20,
    sort: str = "LATEST"
) -> List[Dict[str, Any]]:
    """
    Fetch news from Alpha Vantage API
    
    Args:
        tickers: List of stock tickers to filter by
        topics: List of topics to filter by
        limit: Number of articles to return (max 200)
        sort: Sort order - LATEST, EARLIEST, or RELEVANCE
    
    Returns:
        List of processed news articles
    """
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        logger.error("ALPHA_VANTAGE_API_KEY not found in environment")
        return []
    
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": api_key,
        "limit": min(limit, 200),
        "sort": sort,
    }
    
    if tickers:
        params["tickers"] = ",".join(tickers[:5])  # Limit to 5 tickers
    
    if topics:
        params["topics"] = ",".join(topics[:3])  # Limit to 3 topics
    
    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "feed" not in data:
            logger.warning(f"No feed in Alpha Vantage response: {data.get('Note', data.get('Information', 'Unknown error'))}")
            return []
        
        articles = []
        for item in data.get("feed", []):
            sentiment_score = float(item.get("overall_sentiment_score", 0))
            sentiment_info = get_sentiment_label(sentiment_score)
            
            # Extract relevant topics from the article
            article_topics = []
            for topic_data in item.get("topics", []):
                if float(topic_data.get("relevance_score", 0)) > 0.5:
                    article_topics.append(topic_data.get("topic", "").replace("_", " ").title())
            
            # Extract ticker sentiments
            ticker_sentiments = []
            for ticker_data in item.get("ticker_sentiment", [])[:3]:
                ticker_sentiments.append({
                    "ticker": ticker_data.get("ticker", ""),
                    "score": float(ticker_data.get("ticker_sentiment_score", 0)),
                    "label": ticker_data.get("ticker_sentiment_label", "Neutral"),
                })
            
            articles.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "summary": item.get("summary", "")[:300] + "..." if len(item.get("summary", "")) > 300 else item.get("summary", ""),
                "source": item.get("source", ""),
                "authors": item.get("authors", []),
                "banner_image": item.get("banner_image", ""),
                "time_published": item.get("time_published", ""),
                "time_formatted": format_published_time(item.get("time_published", "")),
                "sentiment_score": sentiment_score,
                "sentiment": sentiment_info,
                "topics": article_topics[:3],
                "ticker_sentiments": ticker_sentiments,
            })
        
        return articles
        
    except requests.RequestException as e:
        logger.error(f"Error fetching news from Alpha Vantage: {e}")
        return []
    except Exception as e:
        logger.error(f"Error processing Alpha Vantage response: {e}")
        return []


def get_personalized_news(user, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Get news personalized to user's interests
    
    Personalization based on:
    - User's medical specialty -> relevant topics
    - User's followed topics/hashtags
    - Default investment topics for physicians
    """
    topics = set()
    
    # Add topics based on specialty
    if user.specialty:
        specialty_lower = user.specialty.lower()
        for specialty, specialty_topics in SPECIALTY_TOPIC_MAP.items():
            if specialty in specialty_lower:
                topics.update(specialty_topics)
                break
    
    # Add default investment topics
    topics.update(DEFAULT_INVESTMENT_TOPICS[:3])
    
    # Limit to 3 topics for API
    topics_list = list(topics)[:3]
    
    # Fetch news
    return fetch_news(topics=topics_list, limit=limit, sort="LATEST")


def get_trending_market_news(limit: int = 10) -> List[Dict[str, Any]]:
    """Get general trending market news"""
    return fetch_news(topics=["finance", "economy_macro"], limit=limit, sort="RELEVANCE")


def get_real_estate_news(limit: int = 10) -> List[Dict[str, Any]]:
    """Get real estate investment news"""
    return fetch_news(topics=["real_estate"], limit=limit)


def get_healthcare_news(limit: int = 10) -> List[Dict[str, Any]]:
    """Get healthcare/life sciences news"""
    return fetch_news(topics=["life_sciences"], limit=limit)


def get_news_by_ticker(ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get news for a specific stock ticker"""
    return fetch_news(tickers=[ticker.upper()], limit=limit)


def get_news_by_topic(topic: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Get news by topic
    
    Valid topics: earnings, technology, real_estate, finance, 
    economy_macro, life_sciences, blockchain, etc.
    """
    return fetch_news(topics=[topic], limit=limit)
