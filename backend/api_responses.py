"""
Standardized API response helpers for consistent error/success envelopes.
All endpoints should use these instead of raw jsonify().
"""
from flask import jsonify


def success(data=None, message=None, status=200):
    """Standard success response: {ok: true, ...data, message: ...}
    Dict data is spread into top level for backward compat with frontend.
    """
    body = {'ok': True}
    if message:
        body['message'] = message
    if data is not None:
        if isinstance(data, dict):
            body.update(data)  # Spread into top level for backward compat
        else:
            body['data'] = data
    return jsonify(body), status


def error(message, status=400, code=None, details=None):
    """Standard error response: {ok: false, error: {message, code, details}}"""
    body = {
        'ok': False,
        'error': message,  # Keep top-level 'error' key for backward compat
    }
    if code:
        body['error_code'] = code
    if details:
        body['error_details'] = details
    return jsonify(body), status


# Error code constants
NOT_FOUND = 'NOT_FOUND'
VALIDATION_ERROR = 'VALIDATION_ERROR'
CONFLICT = 'CONFLICT'
INVALID_TRANSITION = 'INVALID_TRANSITION'
AUTH_REQUIRED = 'AUTH_REQUIRED'
INTERNAL_ERROR = 'INTERNAL_ERROR'
