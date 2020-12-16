import logging
from typing import Optional

from markdown import markdown
# noinspection PyPackageRequirements
from nio import SendRetryError, RoomSendResponse

from middleman.utils import with_ratelimit

logger = logging.getLogger(__name__)


async def send_text_to_room(client, room_id, message, notice=True, markdown_convert=True) -> Optional[RoomSendResponse]:
    """Send text to a matrix room

    Args:
        client (nio.AsyncClient): The client to communicate to matrix with

        room_id (str): The ID of the room to send the message to

        message (str): The message content

        notice (bool): Whether the message should be sent with an "m.notice" message type
            (will not ping users)

        markdown_convert (bool): Whether to convert the message content to markdown.
            Defaults to true.
    """
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
    except SendRetryError:
        logger.exception(f"Unable to send message response to {room_id}")
