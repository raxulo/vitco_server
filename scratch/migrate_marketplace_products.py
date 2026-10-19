import sqlite3
import os

db_path = os.path.join("storage", "database", "realtime_transfer.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(marketplace_products)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    print("Existing columns:", existing_cols)
    
    new_cols = [
        ("price", "NUMERIC(12,2)"),
        ("compare_at_price", "NUMERIC(12,2)"),
        ("badge", "VARCHAR(80)"),
        ("unit", "VARCHAR(50)"),
        ("image_url", "VARCHAR(500)"),
        ("images", "JSON"),
    ]
    
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            print(f"Adding column {col_name} ({col_type})...")
            cursor.execute(f"ALTER TABLE marketplace_products ADD COLUMN {col_name} {col_type}")
            
    conn.commit()
    conn.close()
    print("Migration complete!")
else:
    print("DB path not found at:", db_path)
