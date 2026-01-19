algorithms=[MobileAPIConfig.JWT_ALGORITHM]
)
        return payload
except jwt.ExpiredSignatureError:
        return None
except jwt.InvalidTokenError:
        return None

def token_required(f):
      """Decorator to require JWT token for mobile endpoints"""""
      @wraps(f)
      def decorated(*args, **kwargs):
                token = None

        # Check for token in headers
                if 'Authorization' in request.headers:
                              auth_header = request.headers['Authorization']
                              try:
                                                token = auth_header.split(" ")[1]
except IndexError:
                return jsonify({'error': 'Invalid authorization header'}), 401

        if not token:
                      return jsonify({'error': 'Token is missing'}), 401

        payload = verify_jwt_token(token)
        if not payload:
                      return jsonify({'error': 'Invalid or expired token'}), 401

        return f(payload, *args, **kwargs)

    return decorated

def api_response(data=None, message="Success", status_code=200, errors=None):
      """Standard response format for mobile API"""""
      response = {
                'success': status_code < 400,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'version': MobileAPIConfig.API_VERSION
      }

      if data is not None:
                response['data'] = data

      if errors:
                response['errors'] = errors

      return jsonify(response), status_code

  def validate_api_key(f):
        """Decorator to validate API key for mobile clients"""""
        @wraps(f)
        def decorated(*args, **kwargs):
                  api_key = request.headers.get('X-API-Key')

        # TODO: Implement API key validation against database
        # For now, just check if it exists
        if not api_key:
                      return api_response(
                                        message="API key is required",
                                        status_code=401,
                                        errors={'api_key': 'Missing'}
                                    )

                  return f(*args, **kwargs)

    return decorated

# Mobile-specific error handlers
def mobile_error_handler(app):
      """Register mobile API error handlers"""""
          
    @app.errorhandler(404)
    def not_found(error):
              return api_response(
                            message="Endpoint not found",
                            status_code=404,
                            errors={'endpoint': 'Not found'}
              )

              @app.errorhandler(500)
          def internal_error(error):
                    return api_response(
                                  message="Internal server error",
                                              status_code=500,
                                  errors={'server': 'Internal error'}
                    )

                    @app.errorhandler(403)
                def forbidden(error):
                        return api_response(
                                    message="Access forbidden",
                                      status_code=403,
                                                  errors={'access': 'Forbidden'}
                        )
                  p
                        )
                    )
                      )
      }