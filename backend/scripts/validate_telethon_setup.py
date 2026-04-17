from __future__ import annotations

import os
import sys

from telethon import __version__ as telethon_version
from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main() -> int:
    print(f"Python executable: {sys.executable}")
    print(f"Telethon version: {telethon_version}")
    print("Imported TelegramClient and StringSession successfully.")

    api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()

    if not api_id_raw or not api_hash:
        print("WARNING: TELEGRAM_API_ID and TELEGRAM_API_HASH are not both set.")
        print("Telethon is installed, but real Telegram API validation is not configured yet.")
        return 0

    try:
        api_id = int(api_id_raw)
    except ValueError:
        print("ERROR: TELEGRAM_API_ID must be an integer.")
        return 1

    client = TelegramClient(StringSession(), api_id, api_hash)
    print(f"Telethon client bootstrap succeeded: {client.__class__.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
