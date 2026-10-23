import sqlite3

conn = sqlite3.connect('music_marketer.db')
cur = conn.cursor()

# Check what video render jobs exist
print("=== Recent Video Render Jobs ===\n")
jobs = cur.execute("""
    SELECT task_type, status, stage, error_code, created_at, updated_at, finished_at
    FROM v1_jobs 
    WHERE task_type LIKE '%video%' OR task_type LIKE '%render%'
    ORDER BY created_at DESC 
    LIMIT 5
""").fetchall()

if not jobs:
    print("No video render jobs found")
else:
    for job in jobs:
        task_type, status, stage, error_code, created, updated, finished = job
        print(f"Task: {task_type}")
        print(f"Status: {status}")
        print(f"Stage: {stage}")
        print(f"Error: {error_code}")
        print(f"Created: {created}")
        print(f"Updated: {updated}")
        print(f"Finished: {finished}")
        print("-" * 50)

conn.close()
