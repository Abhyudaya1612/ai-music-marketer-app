"""Test actual video upload to YouTube."""
import sqlite3
import sys
import os
from cryptography.fernet import Fernet

# Load encryption key and YouTube credentials
from backend.config import settings

encryption_key_secret = settings.token_encryption_key
encryption_key = encryption_key_secret.get_secret_value().strip() if hasattr(encryption_key_secret, 'get_secret_value') else str(encryption_key_secret).strip()

conn = sqlite3.connect('music_marketer.db')
cursor = conn.cursor()

cursor.execute('''
SELECT access_token_encrypted, refresh_token_encrypted
FROM v1_platform_connections
WHERE provider = 'youtube' AND status = 'connected' AND owner_id = 'local-artist'
LIMIT 1
''')

row = cursor.fetchone()
if not row:
    print("ERROR: No YouTube connection found")
    sys.exit(1)

access_token_encrypted, refresh_token_encrypted = row

# Decrypt tokens
cipher = Fernet(encryption_key.encode("ascii"))
access_token = cipher.decrypt(access_token_encrypted.encode("ascii")).decode()
refresh_token = cipher.decrypt(refresh_token_encrypted.encode("ascii")).decode() if refresh_token_encrypted else None

print(f"✓ Access token ready ({len(access_token)} chars)")
print(f"✓ Refresh token ready ({len(refresh_token) if refresh_token else 0} chars)")

# Get a video render to upload
cursor.execute('''
SELECT id, metadata_json
FROM v1_video_renders
WHERE owner_id = 'local-artist' AND status = 'succeeded'
LIMIT 1
''')

render_row = cursor.fetchone()
if not render_row:
    print("ERROR: No succeeded video render found")
    sys.exit(1)

render_id, metadata_json = render_row
print(f"\nVideo render: {render_id[:8]}...")

# Get the video file path
from backend.services.job_runner import render_output_path

video_file_path = str(render_output_path(render_id))
print(f"Video file path: {video_file_path}")
print(f"File exists: {os.path.exists(video_file_path)}")

if not os.path.exists(video_file_path):
    print("ERROR: Video file not found!")
    sys.exit(1)

file_size = os.path.getsize(video_file_path)
print(f"File size: {file_size:,.0f} bytes ({file_size / (1024*1024):.1f} MB)")

# Test the publish_to_youtube function
print("\nTesting publish_to_youtube()...")
from backend.services.youtube_publisher import publish_to_youtube
import json

if metadata_json:
    try:
        metadata = json.loads(metadata_json)
        print(f"  Title: {metadata.get('title', 'Unknown')}")
        print(f"  Description: {metadata.get('description', 'Unknown')[:50]}...")
        print(f"  Tags: {metadata.get('tags', [])}")
    except:
        metadata = {'title': 'Test Video', 'description': 'Test', 'tags': ['music']}

try:
    video = publish_to_youtube(
        access_token=access_token,
        refresh_token=refresh_token,
        title=metadata.get('title', 'Test Video'),
        description=metadata.get('description', 'Test upload'),
        tags=metadata.get('tags', ['music']),
        is_public=False,
        video_file_path=video_file_path,
    )
    print(f"\n✓ Upload successful!")
    print(f"  Video ID: {video.video_id}")
    print(f"  URL: {video.url}")
except Exception as e:
    print(f"\n✗ Upload failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

conn.close()
