import logging
from typing import Union

from commonmark import commonmark
# noinspection PyPackageRequirements
from nio import SendRetryError, RoomSendResponse, RoomSendError, LocalProtocolError, AsyncClient

from middleman.utils import get_room_id

logger = logging.getLogger(__name__)


async def send_text_to_room(
    client: AsyncClient, room: str, message: str, notice: bool = True, markdown_convert: bool = True,
    reply_to_event_id: str = None, replaces_event_id: str = None, notify_room_on_failure: str = None,
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

        notify_room_on_failure (str): Optional room ID to notify on failure.
    """
    try:
        room_id = await get_room_id(client, room, logger)
    except ValueError as ex:
        return str(ex)

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

        if notify_room_on_failure:
            # Try to notify the sender of this failure
            try:
                await send_text_to_room(
                    client=client,
                    room=notify_room_on_failure,
                    message="Message did not get delivered due to an error. Please try again.",
                )
            except (LocalProtocolError, SendRetryError):
                logger.exception(f"Failed to notify sender in {notify_room_on_failure} of failed message send")

        return f"Failed to send message: {ex}"


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
    try:
        room_id = await get_room_id(client, room, logger)
    except ValueError as ex:
        return str(ex)

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


async def send_media_to_room(
    client: AsyncClient, room: str, media_type: str, body: str, media_url: str = None,
    media_file: dict = None, media_info: dict = None, reply_to_event_id: str = None,
) -> Union[RoomSendResponse, RoomSendError, str]:
    """Send media to a matrix room

    Args:
        client (nio.AsyncClient): The client to communicate to matrix with

        room (str): The ID or alias of the room to send the message to

        media_type (str): The media type

        body (str): The media body

        media_url (str): The media url

        media_file (dict): The media metadata

        media_info (dict): The media url and metadata

        reply_to_event_id (str): Optional event ID that this message is a reply to.
    """
    try:
        room_id = await get_room_id(client, room, logger)
    except ValueError as ex:
        return str(ex)

    if not (media_url or media_file):
        logger.warning(f"Empty media url for room identifier: {room}")
        return "Empty media url"

    content = {
        "msgtype": media_type,
        "body": body,
    }

    if media_url:
        content.update({"url": media_url})

    if media_file:
        content.update({"file": media_file})

    if media_info:
        content.update({"info": media_info})

    # We don't store the original message content so cannot provide the fallback, unfortunately
    if reply_to_event_id:
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
        logger.exception(f"Unable to send media response to {room_id}")
        return f"Failed to send media: {ex}"
