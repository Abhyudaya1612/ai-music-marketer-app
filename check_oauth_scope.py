import sqlite3

conn = sqlite3.connect('music_marketer.db')
cur = conn.cursor()

# Check the YouTube connection details
print("=== YouTube OAuth Connection ===\n")
connection = cur.execute("""
    SELECT provider, account_name, granted_scopes_json, status, connected_at, updated_at
    FROM v1_platform_connections
    WHERE owner_id = 'local-artist' AND provider = 'youtube'
""").fetchone()

if connection:
    provider, account_name, scopes, status, connected, updated = connection
    print(f"Account: {account_name}")
    print(f"Status: {status}")
    print(f"Scopes: {scopes}")
    print(f"Connected: {connected}")
    print(f"Updated: {updated}")
else:
    print("No YouTube connection found for local-artist")

conn.close()
