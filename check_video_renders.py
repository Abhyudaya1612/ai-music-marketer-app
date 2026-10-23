import sqlite3

conn = sqlite3.connect('music_marketer.db')
cur = conn.cursor()

# Check what video renders exist
print("=== Recent Video Renders ===\n")
# First check what columns exist
schema = cur.execute("PRAGMA table_info(v1_video_renders)").fetchall()
print("Columns:", [col[1] for col in schema])
print()

renders = cur.execute("""
    SELECT id, status, stage, created_at, completed_at
    FROM v1_video_renders 
    ORDER BY created_at DESC 
    LIMIT 5
""").fetchall()

if not renders:
    print("No video renders found")
else:
    for render in renders:
        render_id, status, stage, created, completed = render
        print(f"ID: {render_id[:8]}...")
        print(f"Status: {status}")
        print(f"Stage: {stage}")
        print(f"Created: {created}")
        print(f"Completed: {completed}")
        print("-" * 60)

conn.close()
