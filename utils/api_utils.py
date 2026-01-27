"""
API Utilities - Pagination, compression, caching headers, and performance optimization
"""
import gzip
import json
import logging
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple
from flask import request, jsonify, make_response, g
from datetime import datetime

logger = logging.getLogger(__name__)


class CursorPagination:
    """Cursor-based pagination for efficient mobile API performance"""
    
    @staticmethod
    def encode_cursor(last_id: int, last_timestamp: datetime = None) -> str:
        """Encode pagination cursor"""
        import base64
        
        data = {'id': last_id}
        if last_timestamp:
            data['ts'] = last_timestamp.isoformat()
        
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    
    @staticmethod
    def decode_cursor(cursor: str) -> Dict[str, Any]:
        """Decode pagination cursor"""
        import base64
        
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if 'ts' in data:
                data['ts'] = datetime.fromisoformat(data['ts'])
            return data
        except Exception as e:
            logger.warning(f"Failed to decode cursor: {e}")
            return {}
    
    @staticmethod
    def paginate_query(query, cursor: str = None, limit: int = 20, id_column=None, timestamp_column=None):
        """
        Apply cursor-based pagination to a SQLAlchemy query
        
        Args:
            query: SQLAlchemy query object
            cursor: Encoded cursor string
            limit: Number of items per page
            id_column: Column to use for ID-based pagination
            timestamp_column: Optional column for timestamp-based ordering
            
        Returns:
            (items, next_cursor, has_more)
        """
        if id_column is None:
            raise ValueError("id_column is required for cursor pagination")
        
        if cursor:
            cursor_data = CursorPagination.decode_cursor(cursor)
            if 'id' in cursor_data:
                if timestamp_column is not None and 'ts' in cursor_data:
                    query = query.filter(
                        (timestamp_column < cursor_data['ts']) |
                        ((timestamp_column == cursor_data['ts']) & (id_column < cursor_data['id']))
                    )
                else:
                    query = query.filter(id_column < cursor_data['id'])
        
        if timestamp_column is not None:
            query = query.order_by(timestamp_column.desc(), id_column.desc())
        else:
            query = query.order_by(id_column.desc())
        
        items = query.limit(limit + 1).all()
        
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]
        
        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            last_id = getattr(last_item, id_column.key)
            last_ts = getattr(last_item, timestamp_column.key) if timestamp_column is not None else None
            next_cursor = CursorPagination.encode_cursor(last_id, last_ts)
        
        return items, next_cursor, has_more


def compress_response(f):
    """Decorator to gzip compress response if client supports it"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        response = f(*args, **kwargs)
        
        if isinstance(response, tuple):
            body, status = response[0], response[1] if len(response) > 1 else 200
            headers = response[2] if len(response) > 2 else {}
        else:
            body = response
            status = 200
            headers = {}
        
        accept_encoding = request.headers.get('Accept-Encoding', '')
        
        if 'gzip' not in accept_encoding.lower():
            return response
        
        if isinstance(body, dict):
            body = json.dumps(body)
        elif hasattr(body, 'get_data'):
            body = body.get_data(as_text=True)
        elif not isinstance(body, (str, bytes)):
            return response
        
        if isinstance(body, str):
            body = body.encode('utf-8')
        
        if len(body) < 500:
            return response
        
        compressed = gzip.compress(body)
        
        resp = make_response(compressed, status)
        resp.headers['Content-Encoding'] = 'gzip'
        resp.headers['Content-Length'] = len(compressed)
        resp.headers['Vary'] = 'Accept-Encoding'
        
        for key, value in headers.items():
            resp.headers[key] = value
        
        return resp
    
    return wrapper


def add_cache_headers(max_age: int = 60, private: bool = True, no_store: bool = False):
    """Decorator to add caching headers to response"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            response = f(*args, **kwargs)
            
            if hasattr(response, 'headers'):
                if no_store:
                    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
                    response.headers['Pragma'] = 'no-cache'
                else:
                    cache_control = f"{'private' if private else 'public'}, max-age={max_age}"
                    response.headers['Cache-Control'] = cache_control
                
                response.headers['Vary'] = 'Accept, Accept-Encoding, Authorization'
            
            return response
        return wrapper
    return decorator


def json_response(data: Any, status: int = 200, headers: Dict = None) -> Tuple:
    """Create a JSON response with proper headers"""
    resp = jsonify(data)
    
    if headers:
        for key, value in headers.items():
            resp.headers[key] = value
    
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    return resp, status


def paginated_response(items: List, next_cursor: str = None, has_more: bool = False, 
                       total: int = None, meta: Dict = None) -> Dict:
    """Create a standardized paginated response"""
    response = {
        'data': items,
        'pagination': {
            'has_more': has_more,
            'next_cursor': next_cursor
        }
    }
    
    if total is not None:
        response['pagination']['total'] = total
    
    if meta:
        response['meta'] = meta
    
    return response


def lazy_load_images(items: List[Dict], image_fields: List[str] = None) -> List[Dict]:
    """
    Convert image URLs to thumbnail URLs for lazy loading
    
    Args:
        items: List of dict items with image URLs
        image_fields: List of field names containing image URLs
        
    Returns:
        Items with thumbnail URLs added
    """
    if image_fields is None:
        image_fields = ['image_url', 'avatar_url', 'media_url']
    
    for item in items:
        for field in image_fields:
            if field in item and item[field]:
                original_url = item[field]
                item[f'{field}_thumbnail'] = create_thumbnail_url(original_url)
    
    return items


def create_thumbnail_url(original_url: str, size: str = '200x200') -> str:
    """Create a thumbnail URL from original image URL"""
    if not original_url:
        return original_url
    
    if 'replit.app' in original_url or 'repl.co' in original_url:
        return f"{original_url}?w=200&h=200&fit=crop"
    
    if 'cloudinary.com' in original_url:
        parts = original_url.split('/upload/')
        if len(parts) == 2:
            return f"{parts[0]}/upload/w_200,h_200,c_fill/{parts[1]}"
    
    return original_url


def api_error(message: str, code: str = 'error', status: int = 400, details: Dict = None) -> Tuple:
    """Create a standardized API error response"""
    error_response = {
        'error': {
            'code': code,
            'message': message
        }
    }
    
    if details:
        error_response['error']['details'] = details
    
    return jsonify(error_response), status


def validate_request_json(*required_fields):
    """Decorator to validate required JSON fields in request"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return api_error('Request must be JSON', 'invalid_content_type', 415)
            
            data = request.get_json()
            
            missing = [field for field in required_fields if field not in data]
            if missing:
                return api_error(
                    f'Missing required fields: {", ".join(missing)}',
                    'validation_error',
                    400,
                    {'missing_fields': missing}
                )
            
            g.request_data = data
            return f(*args, **kwargs)
        return wrapper
    return decorator


def serialize_model(model, fields: List[str] = None, exclude: List[str] = None) -> Dict:
    """
    Serialize a SQLAlchemy model to dict
    
    Args:
        model: SQLAlchemy model instance
        fields: List of fields to include (None = all)
        exclude: List of fields to exclude
        
    Returns:
        Dictionary representation
    """
    if exclude is None:
        exclude = ['password_hash', 'totp_secret', '_sa_instance_state']
    
    result = {}
    
    for column in model.__table__.columns:
        if column.name in exclude:
            continue
        if fields is not None and column.name not in fields:
            continue
        
        value = getattr(model, column.name)
        
        if isinstance(value, datetime):
            value = value.isoformat()
        
        result[column.name] = value
    
    return result
