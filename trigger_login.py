"""Simple device-code login — caches MS Graph token for all MCP tools."""

import asyncio
import json
import os
import sys
import time

import httpx

# ── Load credentials from orchestrator .env ──────────────────────────────
_ENV_FILE = os.path.join(
    os.path.dirname(__file__),
    "backend", "services", "orchestrator-service", ".env",
)

def _load_env() -> dict[str, str]:
    env = {}
    try:
        with open(_ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    env[key.strip()] = val.strip()
    except FileNotFoundError:
        print(f"ERROR: .env not found at {_ENV_FILE}")
        sys.exit(1)
    return env


async def device_code_login():
    env = _load_env()
    tenant_id = env.get("MS_TENANT_ID", "")
    client_id = env.get("MS_CLIENT_ID", "")
    client_secret = env.get("MS_CLIENT_SECRET", "")

    if not tenant_id or not client_id:
        print("ERROR: MS_TENANT_ID and MS_CLIENT_ID must be set in .env")
        sys.exit(1)

    scopes = "User.Read User.ReadBasic.All Chat.ReadWrite Calendars.ReadWrite OnlineMeetings.Read offline_access"
    login_base = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"

    async with httpx.AsyncClient(timeout=30) as http:
        # Step 1: Request device code
        print("Requesting device code...\n")
        resp = await http.post(
            f"{login_base}/devicecode",
            data={"client_id": client_id, "scope": scopes},
        )
        resp.raise_for_status()
        dc = resp.json()

        print("=" * 60)
        print("  SIGN IN REQUIRED")
        print(f"  {dc['message']}")
        print("=" * 60)
        print()

        # Step 2: Poll for token
        interval = dc.get("interval", 5)
        device_code = dc["device_code"]
        deadline = time.time() + dc.get("expires_in", 900)

        while time.time() < deadline:
            await asyncio.sleep(interval)
            print("  Polling...", end="\r")

            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_code,
            }
            # For Public Clients (which device code usually is), the secret should not be sent.
            # If the app is registered as a 'Web' app, it might require it, but device flow
            # is typically for Public Clients.
            if client_secret and not env.get("FORCE_PUBLIC_CLIENT", "").lower() == "true":
                data["client_secret"] = client_secret

            poll_resp = await http.post(
                f"{login_base}/token",
                data=data,
            )
            poll_data = poll_resp.json()

            if "access_token" in poll_data:
                # SUCCESS — save token
                cache_dir = os.path.join(os.path.expanduser("~"), ".tagent")
                os.makedirs(cache_dir, exist_ok=True)
                cache_file = os.path.join(cache_dir, "ms_graph_token_cache.json")

                payload = {
                    "tenant_id": tenant_id,
                    "client_id": client_id,
                    "scopes": scopes,
                    "access_token": poll_data["access_token"],
                    "refresh_token": poll_data.get("refresh_token", ""),
                    "token_expiry": time.time() + poll_data.get("expires_in", 3600),
                    "updated_at": int(time.time()),
                }
                with open(cache_file, "w") as f:
                    json.dump(payload, f, indent=2)

                print(f"\n✅ Login successful! Token cached at {cache_file}")

                # Verify by calling /me
                me_resp = await http.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {poll_data['access_token']}"},
                    params={"$select": "displayName,mail,userPrincipalName,jobTitle"},
                )
                if me_resp.status_code == 200:
                    me = me_resp.json()
                    print(f"\n👤 Signed in as: {me.get('displayName')} ({me.get('mail') or me.get('userPrincipalName')})")
                    print(f"   Job Title: {me.get('jobTitle', 'N/A')}")
                else:
                    print(f"\n⚠️  Token obtained but /me returned {me_resp.status_code}")

                return

            error = poll_data.get("error", "")
            if error == "authorization_pending":
                continue
            if error in ("authorization_declined", "expired_token", "bad_verification_code"):
                print(f"\n❌ Login failed: {error}")
                return

    print("\n❌ Login timed out")


if __name__ == "__main__":
    asyncio.run(device_code_login())
