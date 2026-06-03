"""Quick test to verify MS Graph credentials and permissions."""
import asyncio
from tagent.infrastructure.adapters.ms_graph_adapter import get_graph_adapter


async def main():
    graph = get_graph_adapter()

    # 1. Get token (will prompt device code flow)
    try:
        token = await graph._get_token()
        print("✓ Token acquired:", token[:30], "...")
    except Exception as e:
        print("✗ Token error:", e)
        return

    # 2. Try /me
    try:
        me = await graph.get_me()
        print(f"\n✓ Your profile:")
        print(f"  Name: {me.get('displayName')}")
        print(f"  Email: {me.get('mail') or me.get('userPrincipalName')}")
        print(f"  Job: {me.get('jobTitle', 'N/A')}")
        print(f"  Dept: {me.get('department', 'N/A')}")
        print(f"  ID: {me.get('id')}")
    except Exception as e:
        print(f"\n✗ /me error: {e}")
        return

    # 3. Try calendar
    user_id = me.get("id", "")
    print(f"\n--- Today's calendar ---")
    try:
        ctx = await graph.get_standup_context(user_id)
        meetings = ctx.get("meetings", [])
        print(f"✓ Meetings found: {len(meetings)}")
        for m in meetings:
            subj = m.get("subject", "(no subject)")
            start = (m.get("start") or {}).get("dateTime", "")[:16]
            attendees = [(a.get("emailAddress") or {}).get("name", "") for a in (m.get("attendees") or [])]
            print(f"  • {subj} [{start}] — {', '.join(attendees) or 'N/A'}")
        if ctx.get("transcript"):
            print(f"\n--- Transcript snippet ---")
            print(ctx["transcript"][:500])
    except Exception as e:
        print(f"✗ Calendar error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
