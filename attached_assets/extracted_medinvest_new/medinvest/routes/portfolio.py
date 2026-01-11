"""
Portfolio Routes - Portfolio tracking and analysis
"""
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import PortfolioSnapshot

portfolio_bp = Blueprint('portfolio', __name__, url_prefix='/portfolio')


@portfolio_bp.route('/')
@login_required
def index():
    """Portfolio dashboard"""
    # Get latest snapshot
    latest = PortfolioSnapshot.query.filter_by(user_id=current_user.id)\
                                    .order_by(PortfolioSnapshot.snapshot_date.desc()).first()
    
    # Get historical snapshots for chart
    snapshots = PortfolioSnapshot.query.filter_by(user_id=current_user.id)\
                                       .order_by(PortfolioSnapshot.snapshot_date.asc())\
                                       .limit(365).all()
    
    return render_template('portfolio/index.html',
                         latest=latest,
                         snapshots=snapshots)


@portfolio_bp.route('/analysis')
@login_required
def analysis():
    """Portfolio analysis and recommendations"""
    latest = PortfolioSnapshot.query.filter_by(user_id=current_user.id)\
                                    .order_by(PortfolioSnapshot.snapshot_date.desc()).first()
    
    if not latest or not latest.total_value:
        return render_template('portfolio/analysis.html',
                             has_data=False,
                             allocation={},
                             recommendations=[])
    
    total = latest.total_value
    
    # Calculate allocation percentages
    allocation = {
        'stocks': (latest.stocks or 0) / total * 100,
        'bonds': (latest.bonds or 0) / total * 100,
        'real_estate': (latest.real_estate or 0) / total * 100,
        'cash': (latest.cash or 0) / total * 100,
        'crypto': (latest.crypto or 0) / total * 100,
        'other': (latest.other or 0) / total * 100
    }
    
    # Generate recommendations
    recommendations = []
    
    if allocation['cash'] > 20:
        recommendations.append({
            'type': 'warning',
            'title': 'High Cash Allocation',
            'message': 'Consider investing excess cash to combat inflation.'
        })
    
    if allocation['stocks'] > 80:
        recommendations.append({
            'type': 'warning',
            'title': 'High Stock Concentration',
            'message': 'Consider diversifying into bonds or real estate.'
        })
    
    if allocation['bonds'] < 10 and total > 500000:
        recommendations.append({
            'type': 'info',
            'title': 'Low Bond Allocation',
            'message': 'As your portfolio grows, consider adding bonds for stability.'
        })
    
    if allocation['crypto'] > 10:
        recommendations.append({
            'type': 'warning',
            'title': 'High Crypto Exposure',
            'message': 'Crypto volatility may add risk to your portfolio.'
        })
    
    if not recommendations:
        recommendations.append({
            'type': 'success',
            'title': 'Looking Good!',
            'message': 'Your portfolio appears well-balanced.'
        })
    
    return render_template('portfolio/analysis.html',
                         has_data=True,
                         latest=latest,
                         allocation=allocation,
                         recommendations=recommendations)


@portfolio_bp.route('/sync', methods=['POST'])
@login_required
def sync_portfolio():
    """Sync portfolio (demo: creates sample data)"""
    # In production, integrate with Plaid or similar
    
    # Create sample snapshot
    snapshot = PortfolioSnapshot(
        user_id=current_user.id,
        snapshot_date=datetime.utcnow().date(),
        total_value=500000,
        stocks=300000,
        bonds=100000,
        real_estate=50000,
        cash=40000,
        crypto=10000,
        other=0
    )
    
    db.session.add(snapshot)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Portfolio synced! (Demo data added)'
    })


@portfolio_bp.route('/update', methods=['POST'])
@login_required
def update_portfolio():
    """Manually update portfolio values"""
    data = request.get_json()
    
    snapshot = PortfolioSnapshot(
        user_id=current_user.id,
        snapshot_date=datetime.utcnow().date(),
        stocks=float(data.get('stocks', 0)),
        bonds=float(data.get('bonds', 0)),
        real_estate=float(data.get('real_estate', 0)),
        cash=float(data.get('cash', 0)),
        crypto=float(data.get('crypto', 0)),
        other=float(data.get('other', 0))
    )
    
    snapshot.total_value = (
        snapshot.stocks + snapshot.bonds + snapshot.real_estate +
        snapshot.cash + snapshot.crypto + snapshot.other
    )
    
    db.session.add(snapshot)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'total_value': snapshot.total_value
    })
