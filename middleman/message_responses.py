import logging
from typing import List

# noinspection PyPackageRequirements
from nio import RoomSendResponse, RoomSendError

from middleman.chat_functions import send_reaction, send_text_to_room
from middleman.utils import get_in_reply_to, get_mentions, get_replaces, get_reply_msg

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

        reply_section = get_reply_msg(self.event, reply_to, replaces)
        if not reply_section:
            logger.debug(
                f"Skipping {self.event.event_id} which does not look like a reply"
            )
            return
        elif reply_to:
            # Send back to original sender
            message = self.store.get_message_by_management_event_id(reply_to)
            if not message:
                logger.debug(
                    f"Skipping message {self.event.event_id} which is not a reply to one of our relay messages",
                )
                return
            # Relay back to original sender
            # Send back anything after !reply
            reply_text = reply_section[reply_section.find("!reply ") + 7:]
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
                if self.config.confirm_reaction:
                    management_room_text = self.config.confirm_reaction_success
                elif self.config.anonymise_senders:
                    management_room_text = "Message delivered back to the sender."
                else:
                    management_room_text = f"Message delivered back to the sender in room {message['room_id']}."
                logger.info(f"Message {self.event.event_id} relayed back to the original sender")
            elif isinstance(response, RoomSendError):
                if self.config.confirm_reaction:
                    management_room_text = self.config.confirm_reaction_fail
                else:
                    management_room_text = f"Failed to send message back to sender: {response.message}"
                logger.warning(management_room_text)
            else:
                if self.config.confirm_reaction:
                    management_room_text = self.config.confirm_reaction_fail
                else:
                    management_room_text = f"Failed to send message back to sender: {response}"
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
        elif replaces:
            # Edit the already sent reply event
            message = self.store.get_message_by_management_event_id(replaces)
            if not message:
                logger.debug(
                    f"Skipping message {self.event.event_id} which is not an edit to one of our reply messages",
                )
                return
            # Edit the previously sent event
            # Send back anything after !reply
            reply_text = reply_section[reply_section.find("!reply ") + 7:]
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
                    management_room_text = f"Edit delivered back to the sender in " \
                                            f"room {message['room_id']}."
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
        if self.is_mention_only_room([self.room.canonical_alias, self.room.room_id], self.room.is_named):
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
            text = f"anonymous: <i>{self.message_content}</i>".replace("\n", "  \n")
        else:
            text = f"{self.event.sender} in {self.room.display_name} (`{self.room.room_id}`): " \
                   f"{self.message_content}".replace("\n", "  \n")
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
