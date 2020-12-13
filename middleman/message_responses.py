import logging

from middleman.chat_functions import send_text_to_room

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

    async def process(self):
        """Store message metadata and relay to management room."""
        self.store.store_message(
            self.event.event_id,
            self.room.room_id,
            self.event.sender,
        )
        await self.relay_to_management_room()

    async def relay_to_management_room(self):
        """Relay to the management room."""
        room_identifier = self.room.canonical_alias or self.room.room_id
        text = f"{self.event.sender} in {room_identifier}: <i>{self.message_content}</i>"
        await send_text_to_room(self.client, self.config.management_room, text)
