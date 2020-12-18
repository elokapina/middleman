import logging

# noinspection PyPackageRequirements
from nio import RoomSendResponse

from middleman.chat_functions import send_text_to_room
from middleman.utils import get_in_reply_to

logger = logging.getLogger(__name__)


class Message(object):
    def __init__(self, client, store, config, message_content, room, event):
        """Initialize a new Message

        Args:
            client (nio.AsyncClient): nio client used to interact with matrix

            store (Storage): Bot storage

            config (Config): Bot configuration parameters

            message_content (str): The body of the message

            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageText): The event defining the message
        """
        self.client = client
        self.store = store
        self.config = config
        self.message_content = message_content
        self.room = room
        self.event = event

    async def handle_management_room_message(self):
        reply_to = get_in_reply_to(self.event)
        if reply_to and self.message_content.find("!reply ") > -1:
            # Send back to original sender
            room = self.store.get_message_by_management_event_id(reply_to)
            if room:
                # Relay back to original sender
                # Send back anything after !reply
                reply_starts = self.message_content.index("!reply")
                reply_text = self.message_content[reply_starts + 7:]
                await send_text_to_room(
                    self.client,
                    room["room_id"],
                    reply_text,
                )
                if self.config.anonymise_senders:
                    management_room_text = "Message delivered back to the sender."
                else:
                    management_room_text = f"Message delivered back to the sender in room {room['room_id']}."
                # Confirm in management room
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    management_room_text,
                )
                logger.info(f"Message {self.event.event_id} relayed back to the original sender")
            else:
                logger.debug(
                    f"Skipping message {self.event.event_id} which is not a reply to one of our relay messages",
                )
        else:
            logger.debug(f"Skipping {self.event.event_id} which does not look like a reply")

    async def process(self):
        """
        Process messages.
        - if management room, identify replies and forward back to original messages.
        - anything else, relay to management room.
        """
        if self.room.room_id == self.config.management_room_id:
            await self.handle_management_room_message()
        else:
            await self.relay_to_management_room()

    async def relay_to_management_room(self):
        """Relay to the management room."""
        room_identifier = self.room.canonical_alias or self.room.room_id
        if self.config.anonymise_senders:
            text = f"anonymous: <i>{self.message_content}</i>"
        else:
            text = f"{self.event.sender} in {room_identifier}: <i>{self.message_content}</i>"
        response = await send_text_to_room(self.client, self.config.management_room, text)
        if type(response) == RoomSendResponse and response.event_id:
            self.store.store_message(
                self.event.event_id,
                response.event_id,
                self.room.room_id,
            )
            logger.info(f"Message {self.event.event_id} relayed to the management room")
        else:
            logger.error(f"Failed to relay message {self.event.event_id} to the management room")
