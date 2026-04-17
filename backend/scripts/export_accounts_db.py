"""Export twscrape_accounts.db as a base64 string for sharing via .env.

Run this once on the machine that has the working accounts DB:

    python backend/scripts/export_accounts_db.py

Then copy the printed TWSCRAPE_DB_B64=... line into your shared .env file.
Teammates who have that .env will have the accounts automatically restored
when the backend starts.
"""
import base64
import os
import sys

CANDIDATES = [
    "/app/twscrape_accounts.db",
    os.path.join(os.path.dirname(__file__), "../../twscrape_accounts.db"),
    os.path.join(os.path.dirname(__file__), "../../../twscrape_accounts.db"),
]

db_path = next((p for p in CANDIDATES if os.path.exists(p)), None)

if not db_path:
    print("ERROR: twscrape_accounts.db not found. Looked in:")
    for p in CANDIDATES:
        print(f"  {p}")
    sys.exit(1)

with open(db_path, "rb") as fh:
    data = fh.read()

b64 = base64.b64encode(data).decode()

print(f"\nFound DB: {db_path} ({len(data):,} bytes)\n")
print("Add this line to your .env file (and share it with teammates):\n")
print(f"TWSCRAPE_DB_B64={b64}")
print("\nDone. Teammates who have this .env will get the accounts automatically on startup.")
