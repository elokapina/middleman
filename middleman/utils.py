import re
import time

from typing import Optional, List

# noinspection PyPackageRequirements
import nio


# Domain part from https://stackoverflow.com/a/106223/1489738
USER_ID_REGEX = r"@[a-z0-9_=\/\-\.]*:(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9]" \
                r"[A-Za-z0-9\-]*[A-Za-z0-9])*"


def get_in_reply_to(event: nio.Event) -> Optional[str]:
    """
    Pulls an in reply to event ID from an event, if any.
    """
    return event.source.get("content", {}).get("m.relates_to", {}).get("m.in_reply_to", {}).get("event_id")


def get_mentions(text: str) -> List[str]:
    """
    Get mentions in a message.
    """
    matches = re.finditer(USER_ID_REGEX, text, re.MULTILINE)
    return list({match.group() for match in matches})


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
