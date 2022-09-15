import importlib
import json
import logging
from dataclasses import asdict
from typing import Optional, List

# noinspection PyPackageRequirements
from nio import MegolmEvent

# The latest migration version of the database.
#
# Database migrations are applied starting from the number specified in the database's
# `migration_version` table + 1 (or from 0 if this table does not yet exist) up until
# the version specified here.
#
# When a migration is performed, the `migration_version` table should be incremented.

latest_migration_version = 5

logger = logging.getLogger(__name__)


class Storage(object):
    def __init__(self, database_config):
        """Setup the database

        Runs an initial setup or migrations depending on whether a database file has already
        been created

        Args:
            database_config: a dictionary containing the following keys:
                * type: A string, one of "sqlite" or "postgres"
                * connection_string: A string, featuring a connection string that
                    be fed to each respective db library's `connect` method
        """
        self.conn = self._get_database_connection(
            database_config["type"], database_config["connection_string"]
        )
        self.cursor = self.conn.cursor()
        self.db_type = database_config["type"]

        # Try to check the current migration version
        migration_level = 0
        # noinspection PyBroadException
        try:
            self._execute("SELECT version FROM migration_version")
            row = self.cursor.fetchone()
            migration_level = row[0]
        except Exception:
            self._initial_setup()
        finally:
            if migration_level < latest_migration_version:
                self._run_migrations(migration_level)

        logger.info(f"Database initialization of type '{self.db_type}' complete")

    @staticmethod
    def _get_database_connection(database_type: str, connection_string: str):
        if database_type == "sqlite":
            import sqlite3

            # Initialize a connection to the database, with autocommit on
            return sqlite3.connect(connection_string, isolation_level=None)
        elif database_type == "postgres":
            # noinspection PyUnresolvedReferences
            import psycopg2

            conn = psycopg2.connect(connection_string)

            # Autocommit on
            conn.set_isolation_level(0)

            return conn

    def _initial_setup(self):
        """Initial setup of the database"""
        logger.info("Performing initial database setup...")

        # Set up the migration_version table
        self._execute(
            """
            CREATE TABLE migration_version (
                version INTEGER PRIMARY KEY
            )
        """
        )

        # Initially set the migration version to 0
        self._execute(
            """
            INSERT INTO migration_version (
                version
            ) VALUES (?)
        """,
            (0,),
        )

        # Set up any other necessary database tables here

        logger.info("Database setup complete")

    def _run_migrations(self, current_migration_version: int):
        """Execute database migrations. Migrates the database to the
        `latest_migration_version`

        Args:
            current_migration_version: The migration version that the database is
                currently at
        """
        logger.debug("Checking for necessary database migrations...")

        while current_migration_version < latest_migration_version:
            next_migration_version = current_migration_version + 1
            logger.info(
                f"Migrating the database from v{current_migration_version} to v{next_migration_version}...",
            )

            migration = importlib.import_module(f".migrations.{str(next_migration_version).rjust(3, '0')}", "middleman")
            # noinspection PyUnresolvedReferences
            migration.migrate(self)

            # Update the stored migration version
            self._execute("UPDATE migration_version SET version = ?", (next_migration_version,))

            logger.info(f"Database migrated to v{next_migration_version}")
            current_migration_version += 1

    def _execute(self, *args):
        """A wrapper around cursor.execute that transforms placeholder ?'s to %s for postgres
        """
        if self.db_type == "postgres":
            self.cursor.execute(args[0].replace("?", "%s"), *args[1:])
        else:
            self.cursor.execute(*args)

    def get_encrypted_events(self, session_id: str) -> List:
        self._execute("""
            select id, device_id, room_id, session_id, event, user_id from encrypted_events where session_id = ?;
        """, (session_id,))
        events = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "device_id": row[1],
                "room_id": row[2],
                "session_id": row[3],
                "event": row[4],
                "user_id": row[5],
            } for row in events
        ]

    def get_encrypted_events_for_user(self, user_id: str) -> List:
        self._execute("""
            select id, device_id, room_id, session_id, event, user_id from encrypted_events where user_id = ?;
        """, (user_id,))
        events = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "device_id": row[1],
                "room_id": row[2],
                "session_id": row[3],
                "event": row[4],
                "user_id": row[5],
            } for row in events
        ]

    def get_message_by_management_event_id(self, management_event_id: str) -> Optional[dict]:
        self._execute("SELECT room_id, event_id FROM messages where management_event_id = ?", (management_event_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                "room_id": row[0],
                "event_id": row[1],
            }

    def remove_encrypted_event(self, event_id: str):
        self._execute("""
            delete from encrypted_events where event_id = ?;
        """, (event_id,))

    def store_encrypted_event(self, event: MegolmEvent):
        try:
            event_dict = asdict(event)
            event_json = json.dumps(event_dict)
            self._execute("""
                insert into encrypted_events
                    (device_id, event_id, room_id, session_id, event, user_id) values
                    (?, ?, ?, ?, ?, ?)
            """, (event.device_id, event.event_id, event.room_id, event.session_id, event_json, event.sender))
        except Exception as ex:
            logger.error("Failed to store encrypted event %s: %s" % (event.event_id, ex))

    def store_message(self, event_id: str, management_event_id: str, room_id: str):
        self._execute("""
            insert into messages (event_id, management_event_id, room_id) values (?, ?, ?)
        """, (event_id, management_event_id, room_id))

    def store_dm(self, user_id: str, room_id: str):
        self._execute("""
            insert into directs (user_id, room_id) values (?, ?)        
        """, (user_id, room_id))
    
    def get_dm(self, user_id: str) -> room_id:
        self._execute("SELECT room_id FROM directs where user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        else:
            return "0"