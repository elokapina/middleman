#!/usr/bin/env python3
import asyncio
import logging
import sys
from time import sleep

# noinspection PyPackageRequirements
from aiohttp import ClientConnectionError, ServerDisconnectedError
# noinspection PyPackageRequirements
from nio import (
    AsyncClient,
    AsyncClientConfig,
    InviteMemberEvent,
    JoinError,
    LocalProtocolError,
    LoginError,
    RoomMessageText,
    RoomResolveAliasResponse,
)

from middleman.callbacks import Callbacks
from middleman.config import Config
from middleman.storage import Storage
from middleman.utils import with_ratelimit

logger = logging.getLogger(__name__)


async def main():
    # Read config file

    # A different config file path can be specified as the first command line argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "config.yaml"
    config = Config(config_path)

    # Configure the database
    store = Storage(config.database)

    # Configuration options for the AsyncClient
    client_config = AsyncClientConfig(
        max_limit_exceeded=0,
        max_timeouts=0,
        store_sync_tokens=True,
        encryption_enabled=True,
    )

    # Initialize the matrix client
    client = AsyncClient(
        config.homeserver_url,
        config.user_id,
        device_id=config.device_id,
        store_path=config.store_path,
        config=client_config,
    )

    if config.user_token:
        client.access_token = config.user_token
        client.user_id = config.user_id

    # Set up event callbacks
    callbacks = Callbacks(client, store, config)
    # noinspection PyTypeChecker
    client.add_event_callback(callbacks.message, (RoomMessageText,))
    # noinspection PyTypeChecker
    client.add_event_callback(callbacks.invite, (InviteMemberEvent,))

    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        try:
            if config.user_token:
                # Use token to log in
                client.load_store()

                # Sync encryption keys with the server
                if client.should_upload_keys:
                    await client.keys_upload()
            else:
                # Try to login with the configured username/password
                try:
                    login_response = await client.login(
                        password=config.user_password, device_name=config.device_name,
                    )

                    # Check if login failed
                    if type(login_response) == LoginError:
                        logger.error("Failed to login: %s", login_response.message)
                        return False
                except LocalProtocolError as e:
                    # There's an edge case here where the user hasn't installed the correct C
                    # dependencies. In that case, a LocalProtocolError is raised on login.
                    logger.fatal(
                        "Failed to login. Have you installed the correct dependencies? "
                        "https://github.com/poljar/matrix-nio#installation "
                        "Error: %s",
                        e,
                    )
                    return False

                # Login succeeded!

            # Join the management room or fail
            response = await with_ratelimit(client, "join", config.management_room)
            if type(response) == JoinError:
                logger.fatal("Could not join the management room, aborting.")
                return False
            else:
                logger.info(f"Management room membership is good")

            # Resolve management room ID if not known
            if config.management_room.startswith('#'):
                # Resolve the room ID
                response = await with_ratelimit(client, "room_resolve_alias", config.management_room)
                if type(response) == RoomResolveAliasResponse:
                    config.management_room_id = response.room_id
                else:
                    logger.fatal("Could not resolve the management room ID from alias, aborting")
                    return False

            logger.info(f"Logged in as {config.user_id}")
            await client.sync_forever(timeout=30000, full_state=True)

        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")

            # Sleep so we don't bombard the server with login requests
            sleep(15)
        finally:
            # Make sure to close the client connection on disconnect
            await client.close()


asyncio.get_event_loop().run_until_complete(main())
