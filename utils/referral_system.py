"""
Referral System with Commission Tracking.
Handles referral codes, tracking, and commission calculations.
"""
import secrets
from datetime import datetime
from typing import Optional, Dict, List
from app import db


COMMISSION_TIERS = {
    'bronze': {'min_referrals': 1, 'max_referrals': 4, 'rate': 0.10},
    'silver': {'min_referrals': 5, 'max_referrals': 9, 'rate': 0.15},
    'gold': {'min_referrals': 10, 'max_referrals': 24, 'rate': 0.20},
    'platinum': {'min_referrals': 25, 'max_referrals': float('inf'), 'rate': 0.25},
}

SUBSCRIPTION_VALUES = {
    'pro_monthly': 29.00,
    'pro_yearly': 290.00,
    'elite_monthly': 99.00,
    'elite_yearly': 990.00,
}


def generate_referral_code(user_id: int = None, prefix: str = "MED") -> str:
    """Generate a unique referral code."""
    random_part = secrets.token_hex(4).upper()
    if user_id:
        return f"{prefix}{user_id:04d}{random_part[:4]}"
    return f"{prefix}{random_part}"


def get_user_referral_tier(successful_referrals: int) -> str:
    """Determine the user's commission tier based on successful referrals."""
    for tier_name, tier_info in COMMISSION_TIERS.items():
        if tier_info['min_referrals'] <= successful_referrals <= tier_info['max_referrals']:
            return tier_name
    return 'bronze'


def calculate_commission(subscription_type: str, referrer_tier: str) -> float:
    """Calculate commission amount for a referral."""
    base_value = SUBSCRIPTION_VALUES.get(subscription_type, 0)
    commission_rate = COMMISSION_TIERS.get(referrer_tier, {}).get('rate', 0.10)
    return base_value * commission_rate


class ReferralManager:
    """Manager class for referral operations."""
    
    def __init__(self, user):
        self.user = user
    
    def get_referral_code(self) -> str:
        """Get or generate the user's referral code."""
        if not self.user.referral_code:
            self.user.referral_code = generate_referral_code(self.user.id)
            db.session.commit()
        return self.user.referral_code
    
    def get_referral_url(self, base_url: str = None) -> str:
        """Get the full referral URL."""
        code = self.get_referral_code()
        if base_url:
            return f"{base_url}/ref/{code}"
        return f"/ref/{code}"
    
    def get_stats(self) -> Dict:
        """Get referral statistics for the user."""
        from models import Referral
        
        referrals = Referral.query.filter_by(referrer_id=self.user.id).all()
        
        total = len(referrals)
        successful = sum(1 for r in referrals if r.status == 'converted')
        pending = sum(1 for r in referrals if r.status == 'pending')
        total_earnings = sum(r.commission_amount or 0 for r in referrals if r.status == 'converted')
        
        return {
            'total_referrals': total,
            'successful_referrals': successful,
            'pending_referrals': pending,
            'total_earnings': total_earnings,
            'tier': get_user_referral_tier(successful),
            'commission_rate': COMMISSION_TIERS.get(get_user_referral_tier(successful), {}).get('rate', 0.10)
        }
    
    def get_referrals(self) -> List:
        """Get all referrals made by this user."""
        from models import Referral
        return Referral.query.filter_by(referrer_id=self.user.id).order_by(Referral.created_at.desc()).all()


def process_referral_signup(referred_user, referral_code: str) -> Optional[int]:
    """
    Process a new user signup with a referral code.
    Returns the referral ID if successful.
    """
    from models import User, Referral
    
    if not referral_code:
        return None
    
    referrer = User.query.filter_by(referral_code=referral_code).first()
    if not referrer or referrer.id == referred_user.id:
        return None
    
    existing = Referral.query.filter_by(referred_id=referred_user.id).first()
    if existing:
        return None
    
    referral = Referral(
        referrer_id=referrer.id,
        referred_id=referred_user.id,
        status='pending',
        created_at=datetime.utcnow()
    )
    db.session.add(referral)
    db.session.commit()
    
    return referral.id


def process_referral_conversion(user_id: int, subscription_type: str) -> Optional[float]:
    """
    Process a referral conversion when a referred user subscribes.
    Returns the commission amount if successful.
    """
    from models import Referral
    
    referral = Referral.query.filter_by(
        referred_id=user_id,
        status='pending'
    ).first()
    
    if not referral:
        return None
    
    stats = ReferralManager(referral.referrer).get_stats()
    tier = get_user_referral_tier(stats['successful_referrals'])
    
    commission = calculate_commission(subscription_type, tier)
    
    referral.status = 'converted'
    referral.converted_at = datetime.utcnow()
    referral.commission_amount = commission
    referral.subscription_type = subscription_type
    
    referral.referrer.add_points(50)
    
    db.session.commit()
    
    return commission
