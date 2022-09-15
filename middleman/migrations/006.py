def migrate(store):
    if store.db_type == "postgres":
        store._execute("""
            CREATE TABLE directs (
                id SERIAL PRIMARY KEY,
                user_id text unique,
                room_id text
            )
        """)
    else:
        store._execute("""
            CREATE TABLE directs (
                id INTEGER PRIMARY KEY autoincrement,
                event_id text unique,
                room_id text
            )
        """)