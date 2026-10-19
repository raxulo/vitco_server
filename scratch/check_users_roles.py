import sqlite3

conn = sqlite3.connect('storage/database/realtime_transfer.db')
cursor = conn.cursor()

res = cursor.execute("SELECT id, name, email, role FROM users").fetchall()
for row in res:
    print(f"User: {row[1]}, Email: {row[2]}, Role: {row[3]} (type: {type(row[3])})")
