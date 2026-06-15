import redis
from django.conf import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
    return _client


def add_to_blacklist(jti, ttl):
    r = get_client()
    r.setex(f'bl:{jti}', ttl, '1')


def is_blacklisted(jti):
    r = get_client()
    return r.exists(f'bl:{jti}')


def store_refresh_token(user_id, jti, ttl):
    r = get_client()
    r.setex(f'refresh:{user_id}:{jti}', ttl, '1')


def validate_refresh_token(user_id, jti):
    r = get_client()
    return r.exists(f'refresh:{user_id}:{jti}')


def revoke_user_tokens(user_id):
    r = get_client()
    pattern = f'refresh:{user_id}:*'
    keys = list(r.scan_iter(match=pattern, count=100))
    if keys:
        r.delete(*keys)
