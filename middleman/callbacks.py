import json
import logging

# noinspection PyPackageRequirements
from nio import (
    JoinError, MatrixRoom, Event, RoomKeyEvent, RoomMessageText, MegolmEvent, LocalProtocolError,
    RoomKeyRequestError, RoomMemberEvent,
)

from middleman.bot_commands import Command
from middleman.chat_functions import send_text_to_room
from middleman.media_responses import Media
from middleman.message_responses import Message
from middleman.utils import with_ratelimit

logger = logging.getLogger(__name__)

DUPLICATES_CACHE_SIZE = 1000


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
        self.received_events = []
        self.welcome_message_sent_to_room = []

    async def decrypted_callback(self, room_id: str, event: RoomMessageText):
        if isinstance(event, RoomMessageText):
            await self.message(self.client.rooms[room_id], event)
        else:
            logger.warning(f"Unknown event %s passed to decrypted_callback" % event)

    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent):
        """Callback for when an event fails to decrypt."""
        message = f"Failed to decrypt event {event.event_id} in room {room.name} ({room.canonical_alias} / " \
                  f"{room.room_id}) from {event.sender} (session {event.session_id} - decrypting " \
                  f"if keys arrive."
        logger.warning(message)

        # Store for later
        self.store.store_encrypted_event(event)

        waiting_for_keys = self.store.get_encrypted_events_for_user(event.sender)
        logger.info(
            "Waiting to decrypt %s events from sender %s",
            len(waiting_for_keys), event.sender,
        )

        # Send a request for the key
        response = None
        try:
            response = await self.client.request_room_key(event)
        except LocalProtocolError as ex:
            if str(ex) != "A key sharing request is already sent out for this session id.":
                logger.warning(f"Failed to request room key for event {event.event_id}: {ex}")
        if isinstance(response, RoomKeyRequestError):
            logger.warning("RoomKeyRequestError: %s (%s)", response.message, response.status_code)

        # Send a message to the management room if
        # * matrix logging is not enabled
        # * room is not named (ie dm normally)
        if not self.config.matrix_logging_room or not room.is_named:
            await send_text_to_room(
                client=self.client,
                room=self.config.management_room_id,
                message=f"{message} Warning! The room is a direct message.",
                notice=True,
            )

    def trim_duplicates_caches(self):
        if len(self.received_events) > DUPLICATES_CACHE_SIZE:
            self.received_events = self.received_events[:DUPLICATES_CACHE_SIZE]
        if len(self.welcome_message_sent_to_room) > DUPLICATES_CACHE_SIZE:
            self.welcome_message_sent_to_room = self.welcome_message_sent_to_room[:DUPLICATES_CACHE_SIZE]

    async def member(self, room: MatrixRoom, event: RoomMemberEvent) -> None:
        """Callback for when a room member event is received.

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMemberEvent): The event
        """
        if self.config.matrix_logging_room and room.room_id == self.config.matrix_logging_room:
            # Don't react to anything in the logging room
            return

        self.trim_duplicates_caches()
        if self.should_process(event.event_id) is False:
            return
        logger.debug(
            f"Received a room member event for {room.display_name} | "
            f"{event.sender}: {event.membership}"
        )

        # Ignore if it was not us joining the room
        if event.sender != self.client.user:
            return

        # Ignore if we didn't join
        if event.membership != "join" or (
            hasattr(event, "prev_content") and event.prev_content.get("membership") == "join"
        ):
            return

        # Send welcome message if configured
        if self.config.welcome_message and room.is_group:
            if room.room_id in self.welcome_message_sent_to_room:
                logger.debug(f"Not sending welcome message to room {room.room_id} - it's been sent already!")
                return
            # Send welcome message
            logger.info(f"Sending welcome message to room {room.room_id}")
            self.welcome_message_sent_to_room.insert(0, room.room_id)
            await send_text_to_room(self.client, room.room_id, self.config.welcome_message, True)

        # Notify the management room for visibility
        logger.info(f"Notifying management room of room join to {room.room_id}")
        await send_text_to_room(
            self.client,
            self.config.management_room_id,
            f"I have joined room {room.display_name} (`{room.room_id}`).",
            True,
        )

    async def message(self, room, event):
        """Callback for when a message event is received

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageText): The event defining the message

        """
        if self.config.matrix_logging_room and room.room_id == self.config.matrix_logging_room:
            # Don't react to anything in the logging room
            return

        self.trim_duplicates_caches()
        if self.should_process(event.event_id) is False:
            return

        # Extract the message text
        msg = event.body

        # Ignore messages from ourselves
        if event.sender == self.client.user:
            return

        # If this looks like an edit, strip the edit prefix
        if msg.startswith(" * "):
            msg = msg[3:]

        logger.debug(
            f"Bot message received for room {room.display_name} | "
            f"{room.user_name(event.sender)} (named: {room.is_named}, name: {room.name}, "
            f"alias: {room.canonical_alias}): {msg}"
        )

        # Process as message if in a public room without command prefix
        has_command_prefix = msg.startswith(self.command_prefix) or msg.startswith("!message")

        if has_command_prefix:
            if msg.startswith("!message"):
                msg = msg[1:]
            else:
                # Remove the command prefix
                msg = msg[len(self.command_prefix):]

            command = Command(self.client, self.store, self.config, msg, room, event)
            await command.process()
        else:
            # General message listener
            message = Message(self.client, self.store, self.config, msg, room, event)
            await message.process()

    async def media(self, room, event):
        """Callback for when a media event is received

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageMedia): The event defining the media

        """
        if self.config.matrix_logging_room and room.room_id == self.config.matrix_logging_room:
            # Don't react to anything in the logging room
            return

        self.trim_duplicates_caches()
        if self.should_process(event.event_id) is False:
            return

        # Ignore medias from ourselves
        if event.sender == self.client.user:
            return

        # Extract media type
        msgtype = event.source.get("content").get("msgtype")

        # Extract media body
        body = event.body

        # Extract media url
        media_url = event.source.get("content").get("url")

        # Extract media file
        media_file = event.source.get("content").get("file")

        # Extract media info
        media_info = event.source.get("content").get("info")

        logger.debug(
            f"Bot media received for room {room.display_name} | "
            f"{room.user_name(event.sender)} (named: {room.is_named}, name: {room.name}, "
            f"alias: {room.canonical_alias}): {body}"
        )

        # General media listener
        media = Media(
            self.client, self.store, self.config, msgtype, body, media_url, media_file, media_info, room, event,
        )
        await media.process()

    async def invite(self, room, event):
        """Callback for when an invitation is received. Join the room specified in the invite"""
        if self.should_process(event.source.get("event_id")) is False:
            return
        logger.debug(f"Got invite to {room.room_id} from {event.sender}.")

        result = await with_ratelimit(self.client, "join", room.room_id)
        if type(result) == JoinError:
            logger.error("Unable to join room: %s", room.room_id)
            return

        logger.info(f"Joined {room.room_id}")

    async def room_key(self, event: RoomKeyEvent):
        """Callback for ToDevice events like room key events."""
        events = self.store.get_encrypted_events(event.session_id)
        waiting_for_keys = self.store.get_encrypted_events_for_user(event.sender)
        if len(events):
            log_func = logger.info
        else:
            log_func = logger.debug
        log_func(
            "Got room key event for session %s, user %s, matched sessions: %s",
            event.session_id, event.sender, len(events),
        )
        log_func(
            "Waiting to decrypt %s events from sender %s",
            len(waiting_for_keys), event.sender,
        )

        if not events:
            return

        for encrypted_event in events:
            try:
                event_dict = json.loads(encrypted_event["event"])
                params = event_dict["source"]
                params["room_id"] = event_dict["room_id"]
                params["transaction_id"] = event_dict["transaction_id"]
                megolm_event = MegolmEvent.from_dict(params)
            except Exception as ex:
                logger.warning("Failed to restore MegolmEvent for %s: %s", encrypted_event["event_id"], ex)
                continue
            try:
                # noinspection PyTypeChecker
                decrypted = self.client.decrypt_event(megolm_event)
            except Exception as ex:
                logger.warning("Error decrypting event %s: %s", megolm_event.event_id, ex)
                continue
            if isinstance(decrypted, Event):
                logger.info("Successfully decrypted stored event %s", decrypted.event_id)
                parsed_event = Event.parse_event(decrypted.source)
                logger.info("Parsed event: %s", parsed_event)
                self.store.remove_encrypted_event(decrypted.event_id)
                # noinspection PyTypeChecker
                await self.decrypted_callback(encrypted_event["room_id"], parsed_event)
            else:
                logger.warning("Failed to decrypt event %s", decrypted.event_id)

    def should_process(self, event_id: str) -> bool:
        logger.debug("Callback received event: %s", event_id)
        if event_id in self.received_events:
            logger.debug("Skipping %s as it's already processed", event_id)
            return False
        self.received_events.insert(0, event_id)
        return True
