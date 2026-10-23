import sqlite3
from datetime import datetime, timedelta

print("\n" + "="*60)
print("🧪 COMPREHENSIVE SYSTEM TEST")
print("="*60)

conn = sqlite3.connect('music_marketer.db')
cur = conn.cursor()

# Test 1: YouTube Connection
print("\n1️⃣  YOUTUBE OAUTH CONNECTION:")
yt_conn = cur.execute("""
    SELECT provider, account_name, granted_scopes_json, status
    FROM v1_platform_connections
    WHERE owner_id = 'local-artist' AND provider = 'youtube'
""").fetchone()

if yt_conn:
    provider, account, scopes, status = yt_conn
    print(f"   ✅ Account: {account}")
    print(f"   ✅ Status: {status}")
    print(f"   ✅ Scopes: {scopes}")
else:
    print("   ❌ No YouTube connection found")

# Test 2: Video Renders
print("\n2️⃣  VIDEO RENDERING:")
renders = cur.execute("""
    SELECT COUNT(*) FROM v1_video_renders 
    WHERE status = 'succeeded'
""").fetchone()[0]
print(f"   ✅ Successful renders: {renders}")

recent_render = cur.execute("""
    SELECT id, status, created_at, completed_at
    FROM v1_video_renders
    ORDER BY created_at DESC
    LIMIT 1
""").fetchone()

if recent_render:
    render_id, status, created, completed = recent_render
    print(f"   ✅ Latest render: {render_id[:8]}... - Status: {status}")
    if completed:
        created_dt = datetime.fromisoformat(created)
        completed_dt = datetime.fromisoformat(completed)
        duration = (completed_dt - created_dt).total_seconds()
        print(f"   ✅ Render time: {duration:.1f} seconds")

# Test 3: Audio Analysis
print("\n3️⃣  AUDIO ANALYSIS:")
analyses = cur.execute("""
    SELECT COUNT(*) FROM v1_analyses 
    WHERE status = 'succeeded'
""").fetchone()[0]
print(f"   ✅ Successful analyses: {analyses}")

# Test 4: Jobs
print("\n4️⃣  JOB QUEUE STATUS:")
video_jobs = cur.execute("""
    SELECT status, COUNT(*) as count
    FROM v1_jobs
    WHERE task_type LIKE '%video%'
    GROUP BY status
""").fetchall()

if video_jobs:
    for status, count in video_jobs:
        print(f"   📊 Video jobs ({status}): {count}")
else:
    print("   ℹ️  No video jobs yet")

youtube_jobs = cur.execute("""
    SELECT status, COUNT(*) as count
    FROM v1_jobs
    WHERE task_type = 'youtube_publish'
    GROUP BY status
""").fetchall()

if youtube_jobs:
    for status, count in youtube_jobs:
        print(f"   📊 YouTube jobs ({status}): {count}")
else:
    print("   ℹ️  No YouTube publish jobs yet")

# Test 5: Songs
print("\n5️⃣  SONGS IN SYSTEM:")
songs = cur.execute("""
    SELECT COUNT(*) FROM v1_songs
    WHERE owner_id = 'local-artist'
""").fetchone()[0]
print(f"   ✅ Total songs: {songs}")

recent_song = cur.execute("""
    SELECT id, title, created_at
    FROM v1_songs
    WHERE owner_id = 'local-artist'
    ORDER BY created_at DESC
    LIMIT 1
""").fetchone()

if recent_song:
    song_id, title, created = recent_song
    print(f"   ✅ Latest song: {title}")

# Test 6: FFmpeg Detection
print("\n6️⃣  FFMPEG/FFPROBE PATHS:")
from pathlib import Path
from backend.config import settings

ffmpeg_path = Path(settings.ffmpeg_path)
ffprobe_path = Path(settings.ffprobe_path)

ffmpeg_ok = ffmpeg_path.exists() and ffmpeg_path.is_file()
ffprobe_ok = ffprobe_path.exists() and ffprobe_path.is_file()

print(f"   {'✅' if ffmpeg_ok else '❌'} FFmpeg: {ffmpeg_path.name} ({ffmpeg_path.stat().st_size / 1024 / 1024:.1f} MB)" if ffmpeg_ok else f"   ❌ FFmpeg not found: {settings.ffmpeg_path}")
print(f"   {'✅' if ffprobe_ok else '❌'} FFprobe: {ffprobe_path.name} ({ffprobe_path.stat().st_size / 1024 / 1024:.1f} MB)" if ffprobe_ok else f"   ❌ FFprobe not found: {settings.ffprobe_path}")

print("\n" + "="*60)
print("✅ SYSTEM TEST COMPLETE")
print("="*60 + "\n")

conn.close()
