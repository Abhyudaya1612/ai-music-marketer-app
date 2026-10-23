import sqlite3

conn = sqlite3.connect('music_marketer.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check latest video render
cursor.execute('SELECT * FROM v1_video_renders ORDER BY created_at DESC LIMIT 3')
rows = cursor.fetchall()
print('=== LATEST VIDEO RENDERS ===')
for row in rows:
    d = dict(row)
    print(f"ID: {d['id']}")
    print(f"Status: {d['status']}, Publish Status: {d['publish_status']}")
    print(f"Platform URLs: {d['platform_urls']}")
    print(f"Error Code: {d['error_code']}, Publish Error: {d['publish_error']}")
    print()

# Check jobs for youtube_publish
cursor.execute('SELECT * FROM v1_jobs WHERE task_type = ? ORDER BY created_at DESC LIMIT 3', ('youtube_publish',))
rows = cursor.fetchall()
print('\n=== YOUTUBE PUBLISH JOBS ===')
for row in rows:
    d = dict(row)
    print(f"ID: {d['id']}")
    print(f"Status: {d['status']}, Stage: {d['stage']}")
    print(f"Error Code: {d['error_code']}")
    print(f"Started At: {d['started_at']}, Finished At: {d['finished_at']}")
    print()

# Check platform connections
cursor.execute('SELECT * FROM v1_platform_connections')
rows = cursor.fetchall()
print('\n=== PLATFORM CONNECTIONS ===')
for row in rows:
    d = dict(row)
    print(f"Provider: {d['provider']}")
    print(f"Account: {d['account_name']} (ID: {d['account_id']})")
    print(f"Status: {d['status']}")
    print(f"Access Token Encrypted: {bool(d['access_token_encrypted'])}")
    print()

conn.close()
