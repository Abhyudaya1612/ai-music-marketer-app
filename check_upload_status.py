import sqlite3
import json

conn = sqlite3.connect('music_marketer.db')
cur = conn.cursor()

# First check what columns exist
print("=== Table Schema ===")
schema = cur.execute("PRAGMA table_info(v1_jobs)").fetchall()
for col in schema:
    print(f"{col[1]} ({col[2]})")

print("\n=== Recent YouTube Upload Jobs ===\n")
jobs = cur.execute("""
    SELECT *
    FROM v1_jobs 
    WHERE task_type = 'youtube_publish'
    ORDER BY created_at DESC 
    LIMIT 3
""").fetchall()

cols = [desc[0] for desc in cur.description]

for job in jobs:
    print("Job Details:")
    for col, val in zip(cols, job):
        if col == 'result' and val:
            try:
                result_json = json.loads(val)
                print(f"  {col}: {json.dumps(result_json, indent=4)}")
            except:
                print(f"  {col}: {val}")
        else:
            print(f"  {col}: {val}")
    print("-" * 60)

conn.close()
