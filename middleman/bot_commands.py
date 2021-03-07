import logging

# noinspection PyPackageRequirements
from nio import RoomSendResponse

from middleman import commands_help
from middleman.chat_functions import send_text_to_room

logger = logging.getLogger(__name__)


class Command(object):
    def __init__(self, client, store, config, command, room, event):
        """A command made by a user

        Args:
            client (nio.AsyncClient): The client to communicate to matrix with

            store (Storage): Bot storage

            config (Config): Bot configuration parameters

            command (str): The command and arguments

            room (nio.rooms.MatrixRoom): The room the command was sent in

            event (nio.events.room_events.RoomMessageText): The event describing the command
        """
        self.client = client
        self.store = store
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]

    async def process(self):
        """Process the command"""
        if self.command.startswith("echo"):
            await self._echo()
        elif self.command.startswith("help"):
            await self._show_help()
        elif self.command.startswith("message"):
            await self._message()
        else:
            await self._unknown_command()

    async def _echo(self):
        """Echo back the command's arguments"""
        response = " ".join(self.args)
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = (
                "Hello, I am a bot made with matrix-nio! Use `help commands` to view "
                "available commands."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "rules":
            text = "These are the rules!"
        elif topic == "commands":
            text = "Available commands"
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )

    async def _message(self):
        """
        Write a m.text message to a room.
        """
        if self.room.room_id != self.config.management_room_id:
            # Only allow sending messages from the management room
            return

        if len(self.args) < 2:
            await send_text_to_room(self.client, self.room.room_id, commands_help.COMMAND_WRITE)
            return

        room = self.args[0]
        text = ' '.join(self.args[1:])

        response = await send_text_to_room(self.client, room, text, False)

        if type(response) == RoomSendResponse and response.event_id:
            logger.info(f"Processed sending message to room {room}")
            await send_text_to_room(self.client, self.room.room_id, f"Message was delivered to {room}")
            return

        error_message = response if type(response == str) else getattr(response, "message", "Unknown error")
        await send_text_to_room(
            self.client, self.room.room_id, f"Failed to deliver message to {room}! Error: {error_message}",
        )
