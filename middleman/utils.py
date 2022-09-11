from logging import Logger
import re
import time

from typing import Optional, List

# noinspection PyPackageRequirements
import nio


# Domain part from https://stackoverflow.com/a/106223/1489738
USER_ID_REGEX = r"@[a-z0-9_=\/\-\.]*:(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9]" \
                r"[A-Za-z0-9\-]*[A-Za-z0-9])*"

reply_regex = re.compile(r"<mx-reply><blockquote>.*</blockquote></mx-reply>(.*)", flags=re.RegexFlag.DOTALL)


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


def _get_reply_msg(event: nio.Event) -> Optional[str]:
    # first check if this is edit
    if get_replaces(event):
        msg_plain = event.source.get("content", {}).get("m.new_content", {}).get("body")
        msg_formatted = event.source.get("content", {}).get("m.new_content", {}).get("formatted_body")
    else:
        msg_plain = event.source.get("content", {}).get("body")
        msg_formatted = event.source.get("content", {}).get("formatted_body")

    if msg_formatted and (reply_msg := reply_regex.findall(msg_formatted)):
        return reply_msg[0]
    elif msg_formatted:
        return msg_formatted
    else:
        #revert to old method
        message_parts = msg_plain.split('\n\n', 1)
        if len(message_parts) > 1:
            return '\n\n'.join(message_parts[1:])
        return msg_plain


def get_reply_msg(event: nio.Event, reply_to: Optional[str], replaces: Optional[str]) -> Optional[str]:
    if reply_to or replaces:
        if reply_section := _get_reply_msg(event):
            if any([reply_section.startswith(x) for x in ("!reply ", "<p>!reply ")]):
                return reply_section


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
