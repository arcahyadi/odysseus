"""Test complet LLM via client mis à jour."""

import asyncio
import json
import sys

sys.path.insert(0, "/app")
from src.opencode_client import OpenCodeDaemonClient, SessionMode


async def check():
    c = OpenCodeDaemonClient()
    sess = await c.create_session(mode=SessionMode.CHAT)
    sid = sess.get("data", {}).get("id")
    print(f"Session: {sid}")

    print("\nSending message...")
    async for chunk in c.send_message(sid, "Say hello in 3 words.", stream=True):
        obj = json.loads(chunk.strip())
        t = obj.get("type", "")
        if t == "admitted":
            print(f"  ✓ Admitted: {obj.get('messageId')}")
        elif t == "text":
            print(f'  → Response text: "{obj.get("data")}"')
        elif t == "done":
            print("  ✓ Done")
        elif t == "timeout":
            print("  ✗ TIMEOUT")

    await c.close()


asyncio.run(check())
