"""Teams chat tools for MCP."""

from __future__ import annotations

import httpx
from mcp.server import Server
from tagent.mcp.tools._token import get_graph_token as _get_graph_token


def register_teams_tools(server: Server) -> None:
    """Register Teams tools (send message, post card, read channel)."""

    @server.tool()
    async def send_teams_message(team_id: str, channel_id: str, message: str) -> dict:
        """Send a message to a Teams channel."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages"
        payload = {
            "body": {
                "content": message,
                "contentType": "html"
            }
        }
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
            
        if r.status_code in (200, 201):
            return {"status": "ok", "message_id": r.json().get("id")}
        return {"status": "error", "message": r.text}

    @server.tool()
    async def send_direct_message(recipient_email: str, message: str) -> dict:
        """Send a 1:1 direct message to a user by email or display name."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}

        async with httpx.AsyncClient(timeout=30) as http:
            # 1. Resolve recipient: accept either an email address OR a display name
            is_email = "@" in recipient_email and "." in recipient_email.split("@")[-1]
            if is_email:
                r = await http.get(
                    "https://graph.microsoft.com/v1.0/users",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "$filter": f"mail eq '{recipient_email}' or userPrincipalName eq '{recipient_email}'",
                        "$select": "id,displayName",
                    },
                )
                if r.status_code != 200:
                    return {"status": "error", "message": f"Could not find user: {r.text}"}
                users = r.json().get("value", [])
            else:
                # Name-based lookup using $search (requires ConsistencyLevel: eventual header)
                r = await http.get(
                    "https://graph.microsoft.com/v1.0/users",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "ConsistencyLevel": "eventual",
                    },
                    params={
                        "$search": f'"displayName:{recipient_email}"',
                        "$select": "id,displayName,mail,userPrincipalName",
                        "$top": "5",
                        "$count": "true",
                    },
                )
                if r.status_code != 200:
                    # Fallback: startswith on first token
                    first = recipient_email.split()[0]
                    r = await http.get(
                        "https://graph.microsoft.com/v1.0/users",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "ConsistencyLevel": "eventual",
                        },
                        params={
                            "$filter": f"startswith(displayName,'{first}') or startswith(mail,'{first}')",
                            "$select": "id,displayName,mail,userPrincipalName",
                            "$top": "5",
                        },
                    )
                users = r.json().get("value", []) if r.status_code == 200 else []

            if not users:
                return {"status": "error", "message": f"No user found matching '{recipient_email}'. Try using their full email address."}

            user_id = users[0]["id"]
            resolved_name = users[0].get("displayName", recipient_email)

            # 2. Get signed-in user's own ID
            me_r = await http.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {token}"})
            me_id = me_r.json()["id"]

            # Guard: can't create a 1:1 chat with yourself
            if me_id == user_id:
                return {"status": "error", "message": f"{resolved_name} is your own account. You cannot send a message to yourself."}

            # 3. Create or retrieve the 1:1 chat
            chat_payload = {
                "chatType": "oneOnOne",
                "members": [
                    {"@odata.type": "#microsoft.graph.aadUserConversationMember", "roles": ["owner"], "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{me_id}')"},
                    {"@odata.type": "#microsoft.graph.aadUserConversationMember", "roles": ["owner"], "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')"}
                ]
            }
            chat_r = await http.post("https://graph.microsoft.com/v1.0/chats", headers={"Authorization": f"Bearer {token}"}, json=chat_payload)
            if chat_r.status_code not in (200, 201):
                return {"status": "error", "message": f"Could not create/find chat: {chat_r.text}"}

            chat_id = chat_r.json()["id"]

            # 4. Send the message
            msg_r = await http.post(
                f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"body": {"content": message, "contentType": "text"}},
            )
            if msg_r.status_code in (200, 201):
                return {"status": "ok", "message_id": msg_r.json().get("id"), "sent_to": resolved_name}
            return {"status": "error", "message": msg_r.text}

    @server.tool()
    async def post_adaptive_card(team_id: str, channel_id: str, card_json: dict) -> dict:
        """Post an Adaptive Card to a Teams channel."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages"
        payload = {
            "body": {
                "contentType": "html",
                "content": "<attachment id=\"card1\"></attachment>"
            },
            "attachments": [
                {
                    "id": "card1",
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": card_json,
                    "name": None,
                    "thumbnailUrl": None
                }
            ]
        }
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
            
        if r.status_code in (200, 201):
            return {"status": "ok", "message_id": r.json().get("id")}
        return {"status": "error", "message": r.text}
