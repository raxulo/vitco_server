import sqlite3
import os

db_path = "storage/database/realtime_transfer.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check columns of route_master
cursor.execute("PRAGMA table_info(route_master);")
columns = [row[1] for row in cursor.fetchall()]

if "created_by" not in columns:
    print("Column 'created_by' is missing. Adding it...")
    cursor.execute("ALTER TABLE route_master ADD COLUMN created_by CHAR(36);")
    conn.commit()
    print("Column 'created_by' successfully added.")
else:
    print("Column 'created_by' already exists in route_master.")

conn.close()
