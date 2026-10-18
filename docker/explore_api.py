"""Debug : voir le format exact des messages retournés."""

import asyncio
import json
import sys

sys.path.insert(0, "/app")
import httpx


async def check():
    base = "http://opencode-daemon:9888/api"
    auth = httpx.BasicAuth("opencode", "opencode")

    async with httpx.AsyncClient() as client:
        # Créer session
        r = await client.post(f"{base}/session", json={"mode": "chat"}, auth=auth)
        sid = r.json().get("data", {}).get("id", "")
        print(f"Session: {sid}")

        # Envoyer prompt
        r = await client.post(
            f"{base}/session/{sid}/prompt", json={"prompt": {"text": "Say hello in 3 words."}}, auth=auth
        )
        print(f"Prompt: {r.json().get('data', {}).get('id', '')}")

        # Attendre et poller les messages
        print("\nPolling messages...")
        for i in range(20):
            await asyncio.sleep(1)
            r = await client.get(f"{base}/session/{sid}/message", auth=auth)
            msgs = r.json().get("data", [])
            print(f"  [{i + 1}s] {len(msgs)} msgs")
            for m in msgs:
                t = m.get("type", "?")
                role = m.get("role", "?")
                # Voir la structure complète de chaque message
                print(f"    msg: type={t} role={role}")
                content = m.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        print(f"      content item: {json.dumps(c, indent=2)[:200]}")
                elif isinstance(content, str):
                    print(f"      content text: {content[:200]}")
                else:
                    print(f"      content raw: {json.dumps(content, indent=2)[:200]}")
            if len(msgs) >= 2:
                break


asyncio.run(check())
