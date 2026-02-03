import urllib.parse
import logging
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class TokenAuthMiddleware:
    """ASGI middleware that looks for a ?token=<access_token> query param on
    WebSocket connections and, if present, authenticates the scope's user using
    SimpleJWT's AccessToken. Falls back to whatever the inner app provides if
    token is missing or invalid.

    This middleware is intended to be placed *inside* AuthMiddlewareStack so
    session auth runs first and this middleware can override the user when a
    token is present.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only apply for websockets
        if scope.get('type') == 'websocket':
            query_string = scope.get('query_string', b'').decode()
            qs = urllib.parse.parse_qs(query_string)
            token = None
            if 'token' in qs:
                token = qs['token'][0]
            if token:
                try:
                    access = AccessToken(token)
                    user_id = access.get('user_id')
                    if user_id is not None:
                        User = get_user_model()
                        user = await sync_to_async(User.objects.get)(id=user_id)
                        scope['user'] = user
                        logger.debug('TokenAuthMiddleware: authenticated user %s via token', user_id)
                except Exception as exc:
                    logger.debug('TokenAuthMiddleware: token invalid or user lookup failed: %s', exc)
        return await self.app(scope, receive, send)
