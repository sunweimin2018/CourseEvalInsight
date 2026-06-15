from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from .redis_client import is_blacklisted


class RedisBlacklistJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        jti = validated_token.get('jti')
        if jti and is_blacklisted(jti):
            raise InvalidToken('Token is blacklisted')
        return user, validated_token
