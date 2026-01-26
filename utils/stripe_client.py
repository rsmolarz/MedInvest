"""
Stripe Client - Connects to Stripe using Replit connection API
Integration: stripe connector
"""
import os
import stripe
import requests
import logging

logger = logging.getLogger(__name__)

_cached_credentials = None

def get_stripe_credentials():
    """Fetch Stripe credentials from Replit connection API"""
    global _cached_credentials
    
    if _cached_credentials:
        return _cached_credentials
    
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    
    repl_identity = os.environ.get('REPL_IDENTITY')
    web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
    
    if repl_identity:
        x_replit_token = f'repl {repl_identity}'
    elif web_repl_renewal:
        x_replit_token = f'depl {web_repl_renewal}'
    else:
        raise ValueError('X_REPLIT_TOKEN not found for repl/depl')
    
    is_production = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    target_environment = 'production' if is_production else 'development'
    
    url = f'https://{hostname}/api/v2/connection'
    params = {
        'include_secrets': 'true',
        'connector_names': 'stripe',
        'environment': target_environment
    }
    
    try:
        response = requests.get(url, params=params, headers={
            'Accept': 'application/json',
            'X_REPLIT_TOKEN': x_replit_token
        })
        response.raise_for_status()
        data = response.json()
        
        connection = data.get('items', [{}])[0]
        settings = connection.get('settings', {})
        
        if not settings.get('publishable') or not settings.get('secret'):
            raise ValueError(f'Stripe {target_environment} connection not found')
        
        _cached_credentials = {
            'publishable_key': settings['publishable'],
            'secret_key': settings['secret']
        }
        
        return _cached_credentials
        
    except Exception as e:
        logger.error(f"Failed to fetch Stripe credentials: {e}")
        raise


def get_stripe_client():
    """Get configured Stripe client"""
    creds = get_stripe_credentials()
    stripe.api_key = creds['secret_key']
    return stripe


def get_publishable_key():
    """Get Stripe publishable key for frontend"""
    creds = get_stripe_credentials()
    return creds['publishable_key']


SUBSCRIPTION_TIERS = {
    'free': {
        'name': 'Free',
        'price_monthly': 0,
        'price_yearly': 0,
        'features': [
            'Basic feed access',
            'Join investment rooms',
            'View deals (limited)',
            'Community forums',
        ]
    },
    'pro': {
        'name': 'Pro',
        'price_monthly': 29,
        'price_yearly': 290,
        'features': [
            'Everything in Free',
            'Unlimited deal access',
            'Premium courses',
            'Expert AMAs',
            'Priority support',
            'Advanced analytics',
        ]
    },
    'elite': {
        'name': 'Elite',
        'price_monthly': 99,
        'price_yearly': 990,
        'features': [
            'Everything in Pro',
            '1:1 Mentorship matching',
            'Private investment groups',
            'Early deal access',
            'Exclusive events',
            'Dedicated account manager',
        ]
    }
}


def create_stripe_products():
    """Create subscription products and prices in Stripe (run once to seed)"""
    stripe_client = get_stripe_client()
    
    products_created = []
    
    for tier_key, tier_info in SUBSCRIPTION_TIERS.items():
        if tier_key == 'free':
            continue
        
        existing = stripe_client.Product.search(query=f"name:'{tier_info['name']} Subscription'")
        if existing.data:
            logger.info(f"Product {tier_info['name']} already exists")
            products_created.append(existing.data[0])
            continue
        
        product = stripe_client.Product.create(
            name=f"{tier_info['name']} Subscription",
            description=f"MedInvest {tier_info['name']} tier membership",
            metadata={'tier': tier_key}
        )
        
        stripe_client.Price.create(
            product=product.id,
            unit_amount=tier_info['price_monthly'] * 100,
            currency='usd',
            recurring={'interval': 'month'},
            metadata={'tier': tier_key, 'interval': 'month'}
        )
        
        stripe_client.Price.create(
            product=product.id,
            unit_amount=tier_info['price_yearly'] * 100,
            currency='usd',
            recurring={'interval': 'year'},
            metadata={'tier': tier_key, 'interval': 'year'}
        )
        
        products_created.append(product)
        logger.info(f"Created product: {product.name}")
    
    return products_created


def get_subscription_prices():
    """Get all active subscription prices from Stripe"""
    try:
        stripe_client = get_stripe_client()
        prices = stripe_client.Price.list(active=True, expand=['data.product'], limit=100)
        
        subscription_prices = []
        for price in prices.data:
            if price.recurring and hasattr(price, 'product') and price.product:
                product = price.product if isinstance(price.product, stripe.Product) else stripe_client.Product.retrieve(price.product)
                if product.active:
                    subscription_prices.append({
                        'id': price.id,
                        'product_id': product.id,
                        'product_name': product.name,
                        'tier': product.metadata.get('tier', 'unknown'),
                        'amount': price.unit_amount / 100,
                        'currency': price.currency.upper(),
                        'interval': price.recurring.interval,
                    })
        
        return subscription_prices
    except Exception as e:
        logger.error(f"Failed to get prices: {e}")
        return []
