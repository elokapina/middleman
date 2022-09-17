import logging
from typing import List

# noinspection PyPackageRequirements
from nio import RoomSendResponse, RoomSendError

from middleman.chat_functions import send_media_to_room, send_reaction, send_text_to_room
from middleman.utils import get_in_reply_to

logger = logging.getLogger(__name__)

media_name = {
    "m.image": "image",
    "m.audio": "audio",
    "m.video": "video",
    "m.file": "file",
}

class Media(object):
    def __init__(self, client, store, config, media_type, body, media_url, media_file, media_info, room, event):
        """Initialize a new Media

        Args:
            client (nio.AsyncClient): nio client used to interact with matrix

            store (Storage): Bot storage

            config (Config): Bot configuration parameters

            media_type (str): The type of the media

            body (str): The body of the media

            media_url (str): The url of the media

            media_file (str): The url of the encrypted media

            media_info (str): The metadata of the media

            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageMedia): The event defining the media
        """
        self.client = client
        self.store = store
        self.config = config
        self.room = room
        self.event = event
        self.media_type = media_type
        self.body = body
        self.media_url = media_url
        self.media_file = media_file
        self.media_info = media_info


    async def handle_management_room_media(self):
        reply_to = get_in_reply_to(self.event)

        if reply_to and self.config.relay_management_media:
            # Send back to original sender
            message = self.store.get_message_by_management_event_id(reply_to)
            if message:
                # Relay back to original sender
                response = await send_media_to_room(
                    self.client,
                    message["room_id"],
                    self.media_type,
                    self.body,
                    self.media_url,
                    self.media_file,
                    self.media_info,
                    reply_to_event_id=message["event_id"],
                )
                if isinstance(response, RoomSendResponse):
                    # Store our outbound reply so we can reference it later
                    self.store.store_message(
                        event_id=response.event_id,
                        management_event_id=self.event.event_id,
                        room_id=message["room_id"],
                    )
                    if self.config.confirm_reaction:
                        management_room_text = self.config.confirm_reaction_success
                    elif self.config.anonymise_senders:
                        management_room_text = f"{media_name[self.media_type]} delivered back to the sender."
                    else:
                        management_room_text = f"{media_name[self.media_type]} delivered back to the sender in room {message['room_id']}."
                    logger.info(f"{media_name[self.media_type]} {self.event.event_id} relayed back to the original sender")
                else:
                    if self.config.confirm_reaction:
                        management_room_text = self.config.confirm_reaction_fail
                    else:
                        management_room_text = f"Failed to send {media_name[self.media_type]} back to sender:" \
                            f"{response.message if isinstance(response, RoomSendError) else response}"
                    logger.warning(management_room_text)
                # Confirm in management room
                if self.config.confirm_reaction:
                    await send_reaction(
                        self.client,
                        self.room.room_id,
                        self.event.event_id,
                        management_room_text
                    )
                else:
                    await send_text_to_room(
                        self.client,
                        self.room.room_id,
                        management_room_text,
                        True,
                    )
            else:
                logger.debug(
                    f"Skipping {media_name[self.media_type]} {self.event.event_id} which is not a reply to one of our relay messages",
                )
        else:
            logger.debug(f"Skipping {self.event.event_id} reply {media_name[self.media_type]}")

    def is_mention_only_room(self, identifiers: List[str], is_named: bool) -> bool:
        """
        Check if this room is only if mentioned.
        """
        if self.config.mention_only_always_for_named and is_named:
            return True
        for identifier in identifiers:
            if identifier in self.config.mention_only_rooms:
                return True
        return False

    async def process(self):
        """
        Process media.
        - if management room, identify replies and forward back to original messages.
        - anything else, relay to management room.
        """
        if self.room.room_id == self.config.management_room_id:
            await self.handle_management_room_media()
        else:
            await self.relay_to_management_room()

    async def relay_to_management_room(self):
        """Relay to the management room."""
        # First check if we want to relay this
        if self.is_mention_only_room([self.room.canonical_alias, self.room.room_id], self.room.is_named):
            # skip media in mention only rooms for now
            logger.debug(f"Skipping {media_name[self.media_type]} %s in room %s as it's set to only relay on mention and we were "
                         "not mentioned.", self.event.event_id, self.room.room_id)
            return

        if self.config.anonymise_senders:
            text = f"anonymous sent {media_name[self.media_type]}:"
        else:
            text = f"{self.event.sender} in {self.room.display_name} (`{self.room.room_id}`) sent {media_name[self.media_type]} " \
                   f"{self.body}:"
        response = await send_text_to_room(self.client, self.config.management_room, text, notice=True)
        if type(response) == RoomSendResponse and response.event_id:
            response = await send_media_to_room(
                self.client,
                self.config.management_room,
                self.media_type,
                self.body,
                self.media_url,
                self.media_file,
                self.media_info,
                reply_to_event_id=response.event_id
            )

            if type(response) == RoomSendResponse and response.event_id:
                self.store.store_message(
                    self.event.event_id,
                    response.event_id,
                    self.room.room_id,
                )
                logger.info(f"{media_name[self.media_type]} %s relayed to the management room", self.event.event_id)
            else:
                logger.error(f"Failed to relay {media_name[self.media_type]} %s to the management room", self.event.event_id)
        else:
            logger.error(f"Failed to relay {media_name[self.media_type]} %s to the management room", self.event.event_id)
