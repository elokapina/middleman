def migrate(store):
    """
    Recreate the messages table.
    """
    store._execute("""
        drop table messages
    """)
    if store.db_type == "postgres":
        store._execute("""
            CREATE TABLE messages (
                id SERIAL PRIMARY KEY,
                event_id text constraint message_event_id_unique_idx unique,
                management_event_id text constraint message_management_event_id_unique_idx unique,
                room_id text
            )
        """)
    else:
        store._execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY autoincrement,
                event_id text constraint message_event_id_unique_idx unique,
                management_event_id text constraint message_management_event_id_unique_idx unique,
                room_id text
            )
        """)
