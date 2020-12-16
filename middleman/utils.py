import time

from typing import Optional

# noinspection PyPackageRequirements
import nio


def get_in_reply_to(event: nio.Event) -> Optional[str]:
    """
    Pulls an in reply to event ID from an event, if any.
    """
    return event.source.get("content", {}).get("m.relates_to", {}).get("m.in_reply_to", {}).get("event_id")


async def with_ratelimit(client, method, *args, **kwargs):
    """
    Call a client method with 3s backoff if rate limited.
    """
    func = getattr(client, method)
    response = await func(*args, **kwargs)
    if getattr(response, "status_code", None) == "M_LIMIT_EXCEEDED":
        time.sleep(3)
        return with_ratelimit(client, method, *args, **kwargs)
    return response
