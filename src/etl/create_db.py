import sqlite3

DB_PATH = "db/nifty100.db"
SCHEMA_PATH = "db/schema.sql"

def create_database():
    conn = sqlite3.connect(DB_PATH)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
        schema = file.read()

    conn.executescript(schema)
    conn.commit()
    conn.close()

    print("Database schema created successfully")

if __name__ == "__main__":
    create_database()