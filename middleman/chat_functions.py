import logging
from typing import Union

from commonmark import commonmark
# noinspection PyPackageRequirements
from nio import SendRetryError, RoomSendResponse, RoomSendError, LocalProtocolError, AsyncClient

logger = logging.getLogger(__name__)


async def send_text_to_room(
    client: AsyncClient, room: str, message: str, notice: bool = True, markdown_convert: bool = True,
    reply_to_event_id: str = None, replaces_event_id: str = None,
) -> Union[RoomSendResponse, RoomSendError, str]:
    """Send text to a matrix room

    Args:
        client (nio.AsyncClient): The client to communicate to matrix with

        room (str): The ID or alias of the room to send the message to

        message (str): The message content

        notice (bool): Whether the message should be sent with an "m.notice" message type
            (will not ping users)

        markdown_convert (bool): Whether to convert the message content to markdown.
            Defaults to true.

        reply_to_event_id (str): Optional event ID that this message is a reply to.

        replaces_event_id (str): Optional event ID that this message replaces.
    """
    if room.startswith("#"):
        response = await client.room_resolve_alias(room)
        if getattr(response, "room_id", None):
            room_id = response.room_id
            logger.debug(f"Room '{room}' resolved to {room_id}")
        else:
            logger.warning(f"Could not resolve '{room}' to a room ID")
            return "Unknown room alias"
    elif room.startswith("!"):
        room_id = room
    elif room.startswith("@"):
        room_id = await self.get_dm(room)
    else:
        logger.warning(f"Unknown type of room identifier: {room}")
        return "Unknown room identifier"

    # Determine whether to ping room members or not
    msgtype = "m.notice" if notice else "m.text"

    content = {
        "msgtype": msgtype,
        "format": "org.matrix.custom.html",
        "body": message,
    }

    if markdown_convert:
        content["formatted_body"] = commonmark(message)

    if replaces_event_id:
        content["m.relates_to"] = {
            "rel_type": "m.replace",
            "event_id": replaces_event_id,
        }
        content["m.new_content"] = {
            "msgtype": msgtype,
            "format": "org.matrix.custom.html",
            "body": message,
        }
        if markdown_convert:
            content["m.new_content"]["formatted_body"] = commonmark(message)
    # We don't store the original message content so cannot provide the fallback, unfortunately
    elif reply_to_event_id:
        content["m.relates_to"] = {
            "m.in_reply_to": {
                "event_id": reply_to_event_id,
            },
        }

    try:
        return await client.room_send(
            room_id,
            "m.room.message",
            content,
            ignore_unverified_devices=True,
        )
    except (LocalProtocolError, SendRetryError) as ex:
        logger.exception(f"Unable to send message response to {room_id}")
        return f"Failed to send message: {ex}"

async def get_dm(client: AsyncClient, user: str): 
    room_id = self.store.get_dm(user_id=user)
    if not room_id:
        resp = await client.room_create(
            is_direct=True,
            invite=[user]
        )
        room_id = resp.room_id
        self.store.store_dm(user_id=user, room_id=room_id)
    return room_id


async def send_reaction(
    client: AsyncClient, room: str, event_id: str, reaction_key: str
) -> Union[RoomSendResponse, RoomSendError, str]:
    """Send reaction to event

    Args:
        client (nio.AsyncClient): The client to communicate to matrix with

        room (str): The ID or alias of the room to send the message to

        event_id (str): Event ID that this reaction is a reply to.

        reaction_key (str): The reaction symbol
    """
    if room.startswith("#"):
        response = await client.room_resolve_alias(room)
        if getattr(response, "room_id", None):
            room_id = response.room_id
            logger.debug(f"Room '{room}' resolved to {room_id}")
        else:
            logger.warning(f"Could not resolve '{room}' to a room ID")
            return "Unknown room alias"
    elif room.startswith("!"):
        room_id = room
    else:
        logger.warning(f"Unknown type of room identifier: {room}")
        return "Unknown room identifier"

    content = {
        "m.relates_to": {
            "rel_type": "m.annotation",
            "event_id": event_id,
            "key": reaction_key,
        }
    }

    try:
        return await client.room_send(
            room_id,
            "m.reaction",
            content,
            ignore_unverified_devices=True,
        )
    except (LocalProtocolError, SendRetryError) as ex:
        logger.exception(f"Unable to send reaction to {event_id}")
        return f"Failed to send reaction: {ex}"
