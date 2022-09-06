from logging import Logger
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


def get_replaces(event: nio.Event) -> Optional[str]:
    """
    Get the replaces relation, if any.
    """
    rel_type = event.source.get("content", {}).get("m.relates_to", {}).get("rel_type")
    if rel_type == "m.replace":
        return event.source.get("content").get("m.relates_to").get("event_id")


async def get_room_id(client: nio.AsyncClient, room: str, logger: Logger) -> str:
    if room.startswith("#"):
        response = await client.room_resolve_alias(room)
        if getattr(response, "room_id", None):
            logger.debug(f"Room '{room}' resolved to {response.room_id}")
            return response.room_id
        else:
            logger.warning(f"Could not resolve '{room}' to a room ID")
            raise ValueError(message="Unknown room alias")
    elif room.startswith("!"):
        return room
    else:
        logger.warning(f"Unknown type of room identifier: {room}")
        raise ValueError(message="Unknown room identifier")


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
