"""
One-time script to generate a Telethon StringSession.
Run this ONCE on your local machine (not inside Docker):

    pip install telethon
    python backend/scripts/gen_telegram_session.py

It will prompt for your phone number and the code Telegram sends you.
Copy the printed SESSION_STRING into backend/.env as TELEGRAM_SESSION_STRING=...
"""
import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("TELEGRAM_API_ID") or input("Enter your api_id: ").strip())
API_HASH = os.environ.get("TELEGRAM_API_HASH") or input("Enter your api_hash: ").strip()


async def main() -> None:
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_string = client.session.save()
        print("\n" + "=" * 60)
        print("SESSION_STRING — copy this into backend/.env:")
        print("TELEGRAM_SESSION_STRING=" + session_string)
        print("=" * 60 + "\n")


asyncio.run(main())
