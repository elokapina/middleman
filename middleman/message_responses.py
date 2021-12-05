import logging
from typing import List

# noinspection PyPackageRequirements
from nio import RoomSendResponse, RoomSendError

from middleman.chat_functions import send_text_to_room
from middleman.utils import get_in_reply_to, get_mentions, get_replaces

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
        replaces = get_replaces(self.event)
        if reply_to and self.message_content.find("!reply ") > -1:
            # Send back to original sender
            message = self.store.get_message_by_management_event_id(reply_to)
            if message:
                # Relay back to original sender
                # Send back anything after !reply
                reply_starts = self.message_content.index("!reply")
                reply_text = self.message_content[reply_starts + 7:]
                response = await send_text_to_room(
                    self.client,
                    message["room_id"],
                    reply_text,
                    False,
                    reply_to_event_id=message["event_id"],
                )
                if isinstance(response, RoomSendResponse):
                    # Store our outbound reply so we can reference it later
                    self.store.store_message(
                        event_id=response.event_id,
                        management_event_id=self.event.event_id,
                        room_id=message["room_id"],
                    )
                    if self.config.anonymise_senders:
                        management_room_text = "Message delivered back to the sender."
                    else:
                        management_room_text = f"Message delivered back to the sender in room {message['room_id']}."
                    logger.info(f"Message {self.event.event_id} relayed back to the original sender")
                elif isinstance(response, RoomSendError):
                    management_room_text = f"Failed to send message back to sender: {response.message}"
                    logger.warning(management_room_text)
                else:
                    management_room_text = f"Failed to send message back to sender: {response}"
                    logger.warning(management_room_text)
                # Confirm in management room
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    management_room_text,
                    True,
                )
            else:
                logger.debug(
                    f"Skipping message {self.event.event_id} which is not a reply to one of our relay messages",
                )
        elif replaces and self.message_content.find("!reply ") > -1:
            # Edit the already sent reply event
            message = self.store.get_message_by_management_event_id(replaces)
            if message:
                # Edit the previously sent event
                # Send back anything after !reply
                message_content = self.event.source.get("content", {}).get("m.new_content", {}).get("body")
                if message_content:
                    reply_starts = message_content.index("!reply")
                    reply_text = message_content[reply_starts + 7:]
                    response = await send_text_to_room(
                        self.client,
                        message["room_id"],
                        reply_text,
                        False,
                        replaces_event_id=message["event_id"],
                    )
                    if isinstance(response, RoomSendResponse):
                        # Store our outbound reply so we can reference it later
                        self.store.store_message(
                            event_id=response.event_id,
                            management_event_id=self.event.event_id,
                            room_id=message["room_id"],
                        )
                        if self.config.anonymise_senders:
                            management_room_text = "Edit delivered back to the sender."
                        else:
                            management_room_text = f"Edit delivered back to the sender in room {message['room_id']}."
                        logger.info(f"Edit {self.event.event_id} relayed back to the original sender")
                    elif isinstance(response, RoomSendError):
                        management_room_text = f"Failed to send edit back to sender: {response.message}"
                        logger.warning(management_room_text)
                    else:
                        management_room_text = f"Failed to send edit back to sender: {response}"
                        logger.warning(management_room_text)
                    # Confirm in management room
                    await send_text_to_room(
                        self.client,
                        self.room.room_id,
                        management_room_text,
                        True,
                    )
        else:
            logger.debug(f"Skipping {self.event.event_id} which does not look like a reply")

    def is_mention_only_room(self, identifiers: List[str], is_group: bool) -> bool:
        """
        Check if this room is only if mentioned.
        """
        if self.config.mention_only_always_for_groups and is_group:
            return True
        for identifier in identifiers:
            if identifier in self.config.mention_only_rooms:
                return True
        return False

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
        # First check if we want to relay this
        if self.is_mention_only_room([self.room.canonical_alias, self.room.room_id], self.room.is_group):
            # Did we get mentioned?
            mentioned = self.config.user_id in get_mentions(self.message_content) or \
                        self.message_content.lower().find(self.config.user_localpart.lower()) > -1
            if not mentioned:
                logger.debug("Skipping message %s in room %s as it's set to only relay on mention and we were not "
                             "mentioned.", self.event.event_id, self.room.room_id)
                return
            logger.info("Room %s marked as mentions only and we have been mentioned, so relaying %s",
                        self.room.room_id, self.event.event_id)

        if self.config.anonymise_senders:
            text = f"anonymous: <i>{self.message_content}</i>"
        else:
            text = f"{self.event.sender} in {self.room.display_name} (`{self.room.room_id}`): " \
                   f"{self.message_content}"
        response = await send_text_to_room(self.client, self.config.management_room, text, False)
        if type(response) == RoomSendResponse and response.event_id:
            self.store.store_message(
                self.event.event_id,
                response.event_id,
                self.room.room_id,
            )
            logger.info("Message %s relayed to the management room", self.event.event_id)
        else:
            logger.error("Failed to relay message %s to the management room", self.event.event_id)
