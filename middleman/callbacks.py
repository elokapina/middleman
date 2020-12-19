import logging

# noinspection PyPackageRequirements
from nio import JoinError

from middleman.bot_commands import Command
from middleman.chat_functions import send_text_to_room
from middleman.message_responses import Message
from middleman.utils import with_ratelimit

logger = logging.getLogger(__name__)


class Callbacks(object):
    def __init__(self, client, store, config):
        """
        Args:
            client (nio.AsyncClient): nio client used to interact with matrix

            store (Storage): Bot storage

            config (Config): Bot configuration parameters
        """
        self.client = client
        self.store = store
        self.config = config
        self.command_prefix = config.command_prefix

    async def message(self, room, event):
        """Callback for when a message event is received

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageText): The event defining the message

        """
        # Extract the message text
        msg = event.body

        # Ignore messages from ourselves
        if event.sender == self.client.user:
            return

        logger.debug(
            f"Bot message received for room {room.display_name} | "
            f"{room.user_name(event.sender)}: {msg}"
        )

        # Process as message if in a public room without command prefix
        has_command_prefix = msg.startswith(self.command_prefix)

        if has_command_prefix:
            # Remove the command prefix
            msg = msg[len(self.command_prefix):]

            command = Command(self.client, self.store, self.config, msg, room, event)
            await command.process()
        else:
            # General message listener
            message = Message(self.client, self.store, self.config, msg, room, event)
            await message.process()

    async def invite(self, room, event):
        """Callback for when an invite is received. Join the room specified in the invite"""
        logger.debug(f"Got invite to {room.room_id} from {event.sender}.")

        result = await with_ratelimit(self.client, "join", room.room_id)
        if type(result) == JoinError:
            logger.error("Unable to join room: %s", room.room_id)
            return

        logger.info(f"Joined {room.room_id}")

        if self.config.welcome_message and not self.client.rooms.get(room.room_id):
            # Add the room to the client list
            self.client.rooms[room.room_id] = room

            # Send welcome message
            await send_text_to_room(self.client, room.room_id, self.config.welcome_message)
