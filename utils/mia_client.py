"""
Market Inefficiency Agents (MIA) API Client

Provides integration with the marketinefficiencyagents.com platform
for receiving market alerts, triggers, and investment signals.

This is a PREMIUM feature - requires active subscription.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

MIA_BASE_URL = os.environ.get('MIA_API_URL', 'https://marketinefficiencyagents.com/api/v1')


class MIAClient:
    """Client for Market Inefficiency Agents API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = MIA_BASE_URL
        self.timeout = 30
    
    def _get_headers(self) -> Dict:
        """Get API request headers"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request to MIA platform"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code == 401:
                return {'success': False, 'error': 'Invalid API key or unauthorized'}
            elif response.status_code == 403:
                return {'success': False, 'error': 'Access denied - premium subscription required'}
            elif response.status_code == 404:
                return {'success': False, 'error': 'Resource not found'}
            elif response.status_code >= 500:
                return {'success': False, 'error': 'MIA service temporarily unavailable'}
            
            return {'success': True, 'data': response.json()}
            
        except requests.exceptions.Timeout:
            logger.error('MIA API request timed out')
            return {'success': False, 'error': 'Request timed out'}
        except requests.exceptions.ConnectionError:
            logger.error('Could not connect to MIA API')
            return {'success': False, 'error': 'Could not connect to MIA platform'}
        except Exception as e:
            logger.error(f'MIA API error: {e}')
            return {'success': False, 'error': str(e)}
    
    def validate_connection(self) -> Dict:
        """Validate API key and connection"""
        if not self.api_key:
            return {'success': False, 'error': 'No API key provided'}
        return self._make_request('GET', '/auth/validate')
    
    def get_agents(self) -> Dict:
        """Get list of available AI agents"""
        return self._make_request('GET', '/agents')
    
    def get_active_alerts(self, agent_ids: Optional[List[str]] = None) -> Dict:
        """Get active market alerts/triggers"""
        params = {}
        if agent_ids:
            params['agents'] = ','.join(agent_ids)
        return self._make_request('GET', '/alerts/active')
    
    def get_recent_signals(self, limit: int = 20, market_types: Optional[List[str]] = None) -> Dict:
        """Get recent market signals/triggers"""
        data = {'limit': limit}
        if market_types:
            data['markets'] = market_types
        return self._make_request('POST', '/signals/recent', data)
    
    def subscribe_to_triggers(self, trigger_types: List[str], callback_url: str) -> Dict:
        """Subscribe to real-time trigger notifications via webhook"""
        return self._make_request('POST', '/webhooks/subscribe', {
            'trigger_types': trigger_types,
            'callback_url': callback_url
        })
    
    def unsubscribe_webhook(self, webhook_id: str) -> Dict:
        """Unsubscribe from webhook notifications"""
        return self._make_request('DELETE', f'/webhooks/{webhook_id}')
    
    def get_market_summary(self) -> Dict:
        """Get current market inefficiency summary"""
        return self._make_request('GET', '/market/summary')


def get_mia_client_for_user(user) -> Optional[MIAClient]:
    """Get MIA client configured for a specific user"""
    from app import db
    from models import MIAConnection
    
    connection = MIAConnection.query.filter_by(
        user_id=user.id,
        is_active=True
    ).first()
    
    if connection and connection.api_key:
        return MIAClient(api_key=connection.api_key)
    return None


def fetch_mia_feed_items(user, limit: int = 10) -> List[Dict]:
    """Fetch MIA triggers/alerts for user's feed
    
    Returns empty list if:
    - User is not premium
    - User has no active MIA connection
    - API call fails
    """
    if not user.is_premium:
        return []
    
    client = get_mia_client_for_user(user)
    if not client:
        return []
    
    try:
        from models import MIAConnection
        connection = MIAConnection.query.filter_by(
            user_id=user.id,
            is_active=True
        ).first()
        
        if not connection:
            return []
        
        market_types = None
        if connection.enabled_markets:
            market_types = json.loads(connection.enabled_markets)
        
        result = client.get_recent_signals(limit=limit, market_types=market_types)
        
        if result.get('success') and result.get('data'):
            signals = result['data'].get('signals', [])
            return [
                {
                    'id': f"mia_{s.get('id', '')}",
                    'type': 'mia_trigger',
                    'title': s.get('title', 'Market Alert'),
                    'content': s.get('description', ''),
                    'severity': s.get('severity', 'info'),
                    'market': s.get('market', 'Unknown'),
                    'agent': s.get('agent_name', 'AI Agent'),
                    'confidence': s.get('confidence', 0),
                    'created_at': s.get('created_at', datetime.utcnow().isoformat()),
                    'source': 'Market Inefficiency Agents'
                }
                for s in signals
            ]
        return []
        
    except Exception as e:
        logger.error(f'Failed to fetch MIA feed items: {e}')
        return []


DEMO_MIA_ALERTS = [
    {
        'id': 'mia_demo_1',
        'type': 'mia_trigger',
        'title': 'Healthcare REIT Arbitrage Opportunity',
        'content': 'Detected 3.2% price discrepancy between Medical Properties Trust (MPW) and peer group average. Historical reversion timeline: 5-8 trading days.',
        'severity': 'high',
        'market': 'Real Estate',
        'agent': 'REIT Analyzer',
        'confidence': 87,
        'created_at': datetime.utcnow().isoformat(),
        'source': 'Market Inefficiency Agents'
    },
    {
        'id': 'mia_demo_2',
        'type': 'mia_trigger',
        'title': 'Biotech Sector Rotation Signal',
        'content': 'Institutional flow analysis indicates rotation from large-cap pharma to mid-cap biotech. Potential 8-12% sector outperformance.',
        'severity': 'medium',
        'market': 'Healthcare Equities',
        'agent': 'Flow Tracker',
        'confidence': 74,
        'created_at': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        'source': 'Market Inefficiency Agents'
    },
    {
        'id': 'mia_demo_3',
        'type': 'mia_trigger',
        'title': 'Treasury Yield Curve Anomaly',
        'content': 'Unusual spread compression between 2Y and 10Y treasuries. Consider adjusting fixed income allocation.',
        'severity': 'info',
        'market': 'Fixed Income',
        'agent': 'Bond Analyst',
        'confidence': 91,
        'created_at': (datetime.utcnow() - timedelta(hours=5)).isoformat(),
        'source': 'Market Inefficiency Agents'
    }
]


def get_demo_mia_items() -> List[Dict]:
    """Get demo MIA items for preview/upsell"""
    return DEMO_MIA_ALERTS
