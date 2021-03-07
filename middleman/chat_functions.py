import logging
from typing import Union

from markdown import markdown
# noinspection PyPackageRequirements
from nio import SendRetryError, RoomSendResponse, RoomSendError

from middleman.utils import with_ratelimit

logger = logging.getLogger(__name__)


async def send_text_to_room(
    client, room, message, notice=True, markdown_convert=True,
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
    """
    if room.startswith("#"):
        response = await with_ratelimit(client, "room_resolve_alias", room)
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

    # Determine whether to ping room members or not
    msgtype = "m.notice" if notice else "m.text"

    content = {
        "msgtype": msgtype,
        "format": "org.matrix.custom.html",
        "body": message,
    }

    if markdown_convert:
        content["formatted_body"] = markdown(message)

    try:
        return await with_ratelimit(
            client,
            "room_send",
            room_id,
            "m.room.message",
            content,
            ignore_unverified_devices=True,
        )
    except SendRetryError as ex:
        logger.exception(f"Unable to send message response to {room_id}")
        return f"Failed to send message: {ex}"
