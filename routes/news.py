"""
News Routes - Business news feeds from multiple sources
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from utils.news_aggregator import (
    get_aggregated_news,
    get_medical_investment_news,
)
from utils.news import get_news_by_ticker

news_bp = Blueprint('news', __name__, url_prefix='/news')


@news_bp.route('/')
@login_required
def news_feed():
    """Main news feed page with aggregated news from multiple sources"""
    topic = request.args.get('topic', 'for_you')
    ticker = request.args.get('ticker', '')
    
    if ticker:
        articles = get_news_by_ticker(ticker, limit=20)
        page_title = f"News for {ticker.upper()}"
    elif topic == 'for_you':
        articles = get_medical_investment_news(limit=20)
        page_title = "News For You"
    elif topic == 'trending':
        articles = get_aggregated_news("business", limit=20)
        page_title = "Trending Market News"
    elif topic == 'real_estate':
        articles = get_aggregated_news("real_estate", limit=20)
        page_title = "Real Estate News"
    elif topic == 'healthcare':
        articles = get_aggregated_news("healthcare", limit=20)
        page_title = "Healthcare & Life Sciences"
    elif topic == 'earnings':
        articles = get_aggregated_news("earnings", limit=20)
        page_title = "Earnings News"
    elif topic == 'technology':
        articles = get_aggregated_news("technology", limit=20)
        page_title = "Technology News"
    else:
        articles = get_aggregated_news("business", limit=20)
        page_title = f"{topic.replace('_', ' ').title()} News"
    
    topics = [
        {'id': 'for_you', 'name': 'For You', 'icon': 'magic'},
        {'id': 'trending', 'name': 'Trending', 'icon': 'fire'},
        {'id': 'real_estate', 'name': 'Real Estate', 'icon': 'home'},
        {'id': 'healthcare', 'name': 'Healthcare', 'icon': 'heartbeat'},
        {'id': 'earnings', 'name': 'Earnings', 'icon': 'chart-line'},
        {'id': 'technology', 'name': 'Technology', 'icon': 'microchip'},
    ]
    
    return render_template('news/feed.html',
                         articles=articles,
                         topics=topics,
                         current_topic=topic,
                         current_ticker=ticker,
                         page_title=page_title)


@news_bp.route('/api/articles')
@login_required
def api_articles():
    """API endpoint for fetching news articles (for infinite scroll)"""
    topic = request.args.get('topic', 'for_you')
    ticker = request.args.get('ticker', '')
    limit = request.args.get('limit', 15, type=int)
    
    if ticker:
        articles = get_news_by_ticker(ticker, limit=limit)
    elif topic == 'for_you':
        articles = get_medical_investment_news(limit=limit)
    elif topic == 'trending':
        articles = get_aggregated_news("business", limit=limit)
    elif topic == 'real_estate':
        articles = get_aggregated_news("real_estate", limit=limit)
    elif topic == 'healthcare':
        articles = get_aggregated_news("healthcare", limit=limit)
    else:
        articles = get_aggregated_news("business", limit=limit)
    
    return jsonify({'articles': articles})


@news_bp.route('/widget')
@login_required
def news_widget():
    """Small news widget for sidebar"""
    articles = get_medical_investment_news(limit=5)
    return render_template('news/widget.html', articles=articles)
