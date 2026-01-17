"""
Multi-source News Aggregator
Pulls news from multiple providers to avoid rate limiting
"""
import os
import requests
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Cache for all sources
_news_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 1800  # 30 minutes

SENTIMENT_LABELS = {
    'bullish': {'label': 'Bullish', 'color': 'success', 'icon': 'arrow-up'},
    'somewhat_bullish': {'label': 'Somewhat Bullish', 'color': 'success', 'icon': 'arrow-up'},
    'neutral': {'label': 'Neutral', 'color': 'secondary', 'icon': 'minus'},
    'somewhat_bearish': {'label': 'Somewhat Bearish', 'color': 'danger', 'icon': 'arrow-down'},
    'bearish': {'label': 'Bearish', 'color': 'danger', 'icon': 'arrow-down'},
}


def _get_cached(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    """Get from cache if valid"""
    if cache_key in _news_cache:
        cached = _news_cache[cache_key]
        if time.time() - cached["timestamp"] < CACHE_TTL_SECONDS:
            return cached["data"]
    return None


def _set_cached(cache_key: str, data: List[Dict[str, Any]]) -> None:
    """Store in cache"""
    _news_cache[cache_key] = {"timestamp": time.time(), "data": data}
    if len(_news_cache) > 100:
        oldest = min(_news_cache.keys(), key=lambda k: _news_cache[k]["timestamp"])
        del _news_cache[oldest]


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time"""
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
    return dt.strftime("%b %d, %Y")


# ============== NewsAPI.org ==============
def fetch_newsapi(category: str = "business", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch from NewsAPI.org (100 requests/day free)
    """
    cache_key = f"newsapi_{category}_{limit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    api_key = os.environ.get("NEWSAPI_API_KEY")
    if not api_key:
        logger.debug("NEWSAPI_API_KEY not configured")
        return []
    
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "apiKey": api_key,
            "category": category,
            "country": "us",
            "pageSize": limit
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for item in data.get("articles", []):
            pub_date = datetime.utcnow()
            if item.get("publishedAt"):
                try:
                    pub_date = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")).replace(tzinfo=None)
                except:
                    pass
            
            articles.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "summary": item.get("description", "") or "",
                "source": item.get("source", {}).get("name", "NewsAPI"),
                "authors": [item.get("author")] if item.get("author") else [],
                "banner_image": item.get("urlToImage", ""),
                "time_published": pub_date.strftime("%Y%m%dT%H%M%S"),
                "time_formatted": _format_time_ago(pub_date),
                "sentiment_score": 0,
                "sentiment": SENTIMENT_LABELS['neutral'],
                "topics": [category.title()],
                "ticker_sentiments": [],
                "provider": "NewsAPI"
            })
        
        _set_cached(cache_key, articles)
        logger.info(f"Fetched {len(articles)} articles from NewsAPI")
        return articles
    except Exception as e:
        logger.error(f"NewsAPI error: {e}")
        return []


# ============== Finnhub ==============
def fetch_finnhub(category: str = "general", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch from Finnhub (60 requests/minute free)
    """
    cache_key = f"finnhub_{category}_{limit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        logger.debug("FINNHUB_API_KEY not configured")
        return []
    
    try:
        url = "https://finnhub.io/api/v1/news"
        params = {"category": category, "token": api_key}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for item in data[:limit]:
            pub_date = datetime.utcnow()
            if item.get("datetime"):
                try:
                    pub_date = datetime.fromtimestamp(item["datetime"])
                except:
                    pass
            
            articles.append({
                "title": item.get("headline", ""),
                "url": item.get("url", ""),
                "summary": item.get("summary", "") or "",
                "source": item.get("source", "Finnhub"),
                "authors": [],
                "banner_image": item.get("image", ""),
                "time_published": pub_date.strftime("%Y%m%dT%H%M%S"),
                "time_formatted": _format_time_ago(pub_date),
                "sentiment_score": 0,
                "sentiment": SENTIMENT_LABELS['neutral'],
                "topics": [item.get("category", "Finance").title()],
                "ticker_sentiments": [],
                "provider": "Finnhub"
            })
        
        _set_cached(cache_key, articles)
        logger.info(f"Fetched {len(articles)} articles from Finnhub")
        return articles
    except Exception as e:
        logger.error(f"Finnhub error: {e}")
        return []


# ============== RSS Feeds (Free/Unlimited) ==============
RSS_FEEDS = {
    "healthcare": [
        ("https://www.fiercehealthcare.com/rss/xml", "Fierce Healthcare"),
        ("https://www.healthcarefinancenews.com/rss.xml", "Healthcare Finance"),
    ],
    "finance": [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US", "Yahoo Finance"),
        ("https://www.cnbc.com/id/10001147/device/rss/rss.html", "CNBC"),
    ],
    "real_estate": [
        ("https://www.inman.com/feed/", "Inman"),
    ],
    "business": [
        ("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC Business"),
        ("https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "NY Times Business"),
    ]
}


def fetch_rss_feed(url: str, source_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch articles from a single RSS feed"""
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "MedInvest/1.0"})
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        articles = []
        
        # Handle both RSS 2.0 and Atom formats
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        for item in items[:limit]:
            title = ""
            link = ""
            description = ""
            pub_date = datetime.utcnow()
            
            # RSS 2.0 format
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            date_elem = item.find("pubDate")
            
            # Atom format fallback
            if title_elem is None:
                title_elem = item.find("{http://www.w3.org/2005/Atom}title")
            if link_elem is None:
                link_elem = item.find("{http://www.w3.org/2005/Atom}link")
                if link_elem is not None:
                    link = link_elem.get("href", "")
            if desc_elem is None:
                desc_elem = item.find("{http://www.w3.org/2005/Atom}summary")
            
            title = title_elem.text if title_elem is not None and title_elem.text else ""
            if not link and link_elem is not None and link_elem.text:
                link = link_elem.text
            description = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            
            # Clean HTML from description
            if description:
                import re
                description = re.sub(r'<[^>]+>', '', description)[:300]
            
            # Parse date
            if date_elem is not None and date_elem.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(date_elem.text).replace(tzinfo=None)
                except:
                    pass
            
            if title and link:
                articles.append({
                    "title": title,
                    "url": link,
                    "summary": description,
                    "source": source_name,
                    "authors": [],
                    "banner_image": "",
                    "time_published": pub_date.strftime("%Y%m%dT%H%M%S"),
                    "time_formatted": _format_time_ago(pub_date),
                    "sentiment_score": 0,
                    "sentiment": SENTIMENT_LABELS['neutral'],
                    "topics": [],
                    "ticker_sentiments": [],
                    "provider": "RSS"
                })
        
        return articles
    except Exception as e:
        logger.debug(f"RSS feed error ({source_name}): {e}")
        return []


def fetch_rss_category(category: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch from multiple RSS feeds for a category"""
    cache_key = f"rss_{category}_{limit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    feeds = RSS_FEEDS.get(category, RSS_FEEDS.get("business", []))
    all_articles = []
    
    if not feeds:
        return []
    
    # Calculate per-feed limit, ensuring at least 3 per feed
    per_feed_limit = max(3, (limit + len(feeds) - 1) // len(feeds))
    
    for url, source_name in feeds:
        articles = fetch_rss_feed(url, source_name, limit=per_feed_limit)
        all_articles.extend(articles)
    
    # Sort by time and limit
    all_articles.sort(key=lambda x: x.get("time_published", ""), reverse=True)
    result = all_articles[:limit]
    
    if result:
        _set_cached(cache_key, result)
        logger.info(f"Fetched {len(result)} articles from RSS feeds")
    
    return result


# ============== Aggregator ==============

# Map categories to Alpha Vantage topics for specialized queries
ALPHA_VANTAGE_TOPICS = {
    "business": ["economy_macro", "finance"],
    "healthcare": ["life_sciences"],
    "finance": ["finance", "earnings"],
    "real_estate": ["real_estate"],
    "technology": ["technology"],
    "earnings": ["earnings", "finance"],
    "economy": ["economy_macro"],
}


def get_aggregated_news(
    category: str = "business",
    limit: int = 15,
    include_alpha_vantage: bool = True
) -> List[Dict[str, Any]]:
    """
    Aggregate news from all available sources
    Returns deduplicated, sorted articles
    """
    cache_key = f"aggregated_{category}_{limit}_{include_alpha_vantage}"
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    all_articles = []
    per_source_limit = max(5, (limit + 2) // 3)  # Ensure at least 5 per source
    
    # Map categories to source-specific categories
    category_map = {
        "business": {"newsapi": "business", "finnhub": "general", "rss": "business", "alpha": ["economy_macro", "finance"]},
        "healthcare": {"newsapi": "health", "finnhub": "general", "rss": "healthcare", "alpha": ["life_sciences"]},
        "finance": {"newsapi": "business", "finnhub": "general", "rss": "finance", "alpha": ["finance", "earnings"]},
        "real_estate": {"newsapi": "business", "finnhub": "general", "rss": "real_estate", "alpha": ["real_estate"]},
        "technology": {"newsapi": "technology", "finnhub": "technology", "rss": "business", "alpha": ["technology"]},
        "earnings": {"newsapi": "business", "finnhub": "general", "rss": "finance", "alpha": ["earnings"]},
    }
    cats = category_map.get(category, category_map["business"])
    
    # Fetch from all sources in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        
        # NewsAPI
        futures.append(executor.submit(fetch_newsapi, cats["newsapi"], per_source_limit))
        
        # Finnhub
        futures.append(executor.submit(fetch_finnhub, cats["finnhub"], per_source_limit))
        
        # RSS feeds (always available)
        futures.append(executor.submit(fetch_rss_category, cats["rss"], per_source_limit))
        
        # Alpha Vantage (if enabled and not rate limited)
        if include_alpha_vantage:
            from utils.news import fetch_news as fetch_alpha_vantage
            topics = cats.get("alpha", ["finance"])
            futures.append(executor.submit(fetch_alpha_vantage, None, topics, per_source_limit))
        
        for future in as_completed(futures):
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"Error fetching from source: {e}")
    
    # Deduplicate by title similarity
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        title_key = article.get("title", "").lower()[:50]
        if title_key and title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(article)
    
    # Sort by time (newest first)
    unique_articles.sort(key=lambda x: x.get("time_published", ""), reverse=True)
    
    result = unique_articles[:limit]
    
    if result:
        _set_cached(cache_key, result)
        logger.info(f"Aggregated {len(result)} unique articles from {len(all_articles)} total")
    
    return result


def get_medical_investment_news(limit: int = 15) -> List[Dict[str, Any]]:
    """Get news tailored for medical professionals interested in investing"""
    all_news = []
    
    # Get healthcare news
    healthcare = get_aggregated_news("healthcare", limit=limit // 2)
    all_news.extend(healthcare)
    
    # Get finance/investment news
    finance = get_aggregated_news("finance", limit=limit // 2)
    all_news.extend(finance)
    
    # Deduplicate and sort
    seen = set()
    unique = []
    for article in all_news:
        key = article.get("title", "").lower()[:50]
        if key and key not in seen:
            seen.add(key)
            unique.append(article)
    
    unique.sort(key=lambda x: x.get("time_published", ""), reverse=True)
    return unique[:limit]
