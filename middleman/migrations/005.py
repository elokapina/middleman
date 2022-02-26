# noinspection PyProtectedMember
def migrate(store):
    store._execute("""
        ALTER TABLE encrypted_events ADD COLUMN user_id text default '';
    """)
    store._execute("""
        CREATE INDEX encrypted_events_user_id_idx ON encrypted_events (user_id);
    """)
