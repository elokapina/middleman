# noinspection PyProtectedMember
def migrate(store):
    if store.db_type == "postgres":
        store._execute("""
            CREATE TABLE encrypted_events (
                id SERIAL PRIMARY KEY,
                device_id text,
                event_id text unique,
                room_id text,
                session_id text,
                event text
            )
        """)
    else:
        store._execute("""
            CREATE TABLE encrypted_events (
                id INTEGER PRIMARY KEY autoincrement,
                device_id text,
                event_id text unique,
                room_id text,
                session_id text,
                event text
            )
        """)
    store._execute("""
        CREATE INDEX encrypted_events_session_id_idx on encrypted_events (session_id);
    """)
