"""
Reuse a single Angel One session across API requests to avoid rate limits.
"""
import threading
import time

from trading.broker import AngelOneClient

_lock = threading.Lock()
_client: AngelOneClient | None = None
_expires_at: float = 0

# Angel One sessions are valid for a while; refresh before typical expiry
SESSION_TTL_SECONDS = 50 * 60


def format_broker_error(exc: Exception) -> str:
    msg = str(exc)
    lower = msg.lower()
    if 'exceeding access rate' in lower or 'rate limit' in lower:
        return (
            'Angel One rate limit reached. Wait 10–15 minutes, then try again. '
            'Avoid rapidly opening Dashboard and Positions.'
        )
    if "couldn't parse the json" in lower and 'access denied' in lower:
        return (
            'Angel One rate limit reached. Wait 10–15 minutes, then try again.'
        )
    return msg


def invalidate_angel_client() -> None:
    global _client, _expires_at
    with _lock:
        _client = None
        _expires_at = 0


def get_angel_client(force_refresh: bool = False) -> AngelOneClient:
    """Return a logged-in AngelOneClient, reusing the cached session when possible."""
    global _client, _expires_at
    now = time.time()

    with _lock:
        if (
            not force_refresh
            and _client is not None
            and _client.smart_api is not None
            and now < _expires_at
        ):
            return _client

        client = AngelOneClient()
        try:
            client._initialize_smart_api()
        except Exception:
            invalidate_angel_client()
            raise

        _client = client
        _expires_at = now + SESSION_TTL_SECONDS
        return client
