import sqlite3

conn = sqlite3.connect('music_marketer.db')
cur = conn.cursor()

# Find platform-related tables
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%platform%'").fetchall()
print("Platform tables:", [t[0] for t in tables])

# Check if connection exists
for table_name in [t[0] for t in tables]:
    try:
        rows = cur.execute(f"SELECT * FROM {table_name} WHERE provider = 'youtube' LIMIT 1").fetchall()
        if rows:
            print(f"\nYouTube connection in {table_name}:")
            cols = [desc[0] for desc in cur.description]
            for col, val in zip(cols, rows[0]):
                print(f"  {col}: {val}")
    except Exception as e:
        print(f"Error checking {table_name}: {e}")

conn.close()
