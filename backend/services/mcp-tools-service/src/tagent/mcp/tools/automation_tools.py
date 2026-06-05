"""Automation workflows for Tagent."""

from __future__ import annotations

import base64
import json
import os

import httpx
from mcp.server import Server

from tagent.mcp.tools._token import get_graph_token as _get_graph_token


async def _resolve_user_chat(token: str, recipient_name: str) -> dict:
    """Helper to resolve a user by name and create/find a 1:1 chat."""
    async with httpx.AsyncClient(timeout=30) as http:
        # 1. Handle explicit email
        is_email = "@" in recipient_name and "." in recipient_name.split("@")[-1]
        
        if is_email:
            r = await http.get(
                "https://graph.microsoft.com/v1.0/users",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "$filter": f"mail eq '{recipient_name}' or userPrincipalName eq '{recipient_name}'",
                    "$select": "id,displayName,mail,userPrincipalName",
                },
            )
        else:
            # 2. Search by display name
            r = await http.get(
                "https://graph.microsoft.com/v1.0/users",
                headers={
                    "Authorization": f"Bearer {token}",
                    "ConsistencyLevel": "eventual",
                },
                params={
                    "$search": f'"displayName:{recipient_name}"',
                    "$select": "id,displayName,mail,userPrincipalName",
                    "$top": "5",
                    "$count": "true",
                },
            )
            if r.status_code != 200 or not r.json().get("value"):
                # Fallback: startswith on first token
                first = recipient_name.split()[0] if recipient_name else ""
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
            return {"error": f"No user found matching '{recipient_name}'."}

        user_id = users[0]["id"]
        resolved_name = users[0].get("displayName", recipient_name)

        # Get my ID
        me_r = await http.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {token}"})
        if me_r.status_code != 200:
            return {"error": "Failed to get your profile."}
        me_id = me_r.json()["id"]

        if me_id == user_id:
            return {"error": "Cannot interact with yourself."}

        # Create/Get chat
        chat_payload = {
            "chatType": "oneOnOne",
            "members": [
                {"@odata.type": "#microsoft.graph.aadUserConversationMember", "roles": ["owner"], "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{me_id}')"},
                {"@odata.type": "#microsoft.graph.aadUserConversationMember", "roles": ["owner"], "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')"}
            ]
        }
        chat_r = await http.post("https://graph.microsoft.com/v1.0/chats", headers={"Authorization": f"Bearer {token}"}, json=chat_payload)
        
        if chat_r.status_code not in (200, 201):
            return {"error": f"Failed to open chat: {chat_r.text}"}
            
        return {"chat_id": chat_r.json()["id"], "resolved_name": resolved_name, "user_id": user_id, "email": users[0].get("mail") or users[0].get("userPrincipalName", "")}


def register_automation_tools(server: Server) -> None:
    @server.tool()
    async def nudge_colleague(colleague_name: str, item_id: str, item_type: str = "Jira Ticket") -> dict:
        """Send a polite Teams DM to a colleague asking for an update on a blocked item."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        chat_info = await _resolve_user_chat(token, colleague_name)
        if "error" in chat_info:
            return {"status": "error", "message": chat_info["error"]}
            
        chat_id = chat_info["chat_id"]
        name = chat_info["resolved_name"].split()[0]
        
        # Craft a polite message
        message = f"Hi {name}, I'm Tagent (AI Assistant). I'm following up on {item_type} **{item_id}**. Do you have a few minutes to take a look at it today? Thank you!"
        
        async with httpx.AsyncClient(timeout=15) as http:
            msg_r = await http.post(
                f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"body": {"content": message, "contentType": "html"}},
            )
            
        if msg_r.status_code in (200, 201):
            return {"status": "ok", "message": f"Successfully nudged {chat_info['resolved_name']} about {item_id}."}
        return {"status": "error", "message": msg_r.text}

    @server.tool()
    async def chat_to_jira(colleague_name: str) -> dict:
        """Read recent 1:1 chat with a colleague and prepare a Jira ticket context from it."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        chat_info = await _resolve_user_chat(token, colleague_name)
        if "error" in chat_info:
            return {"status": "error", "message": chat_info["error"]}
            
        chat_id = chat_info["chat_id"]
        resolved_name = chat_info["resolved_name"]
        
        async with httpx.AsyncClient(timeout=15) as http:
            msgs_r = await http.get(
                f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"$top": "15", "$orderby": "createdDateTime desc"},
            )
            
        if msgs_r.status_code != 200:
            return {"status": "error", "message": f"Failed to fetch chat messages: {msgs_r.text}"}
            
        import re as _re
        chat_messages = []
        raw_msgs = msgs_r.json().get("value", [])
        for m in reversed(raw_msgs):
            content = (m.get("body") or {}).get("content", "")
            plain = _re.sub(r"<[^>]+>", "", content).strip()
            if not plain:
                continue
            sender = (m.get("from") or {}).get("user", {}).get("displayName", "System")
            chat_messages.append(f"{sender}: {plain}")
            
        if not chat_messages:
            return {"status": "error", "message": f"No recent messages found with {resolved_name}."}
            
        # We return the chat context. The LLM (Orchestrator) will summarize this and call the real create_jira_issue tool.
        return {
            "status": "ok", 
            "colleague": resolved_name,
            "chat_context": "\n".join(chat_messages)
        }

    @server.tool()
    async def negotiate_meeting(colleague_name: str, topic: str = "Quick Sync") -> dict:
        """Find a mutual free 30-min slot with a colleague today/tomorrow and DM them to propose it."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        chat_info = await _resolve_user_chat(token, colleague_name)
        if "error" in chat_info:
            return {"status": "error", "message": chat_info["error"]}
            
        email = chat_info["email"]
        chat_id = chat_info["chat_id"]
        name = chat_info["resolved_name"].split()[0]
        
        from datetime import datetime, timezone, timedelta
        
        # Use findMeetingTimes API
        payload = {
            "attendees": [{"type": "required", "emailAddress": {"address": email}}],
            "meetingDuration": "PT30M",
            "maxCandidates": 1,
        }
        
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                "https://graph.microsoft.com/v1.0/me/findMeetingTimes",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
            
        slot_text = "sometime today or tomorrow"
        if r.status_code == 200:
            suggestions = r.json().get("meetingTimeSuggestions", [])
            if suggestions:
                ts = suggestions[0].get("meetingTimeSlot", {}).get("start", {}).get("dateTime", "")
                if ts:
                    # Convert UTC to IST (+05:30)
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    dt_ist = dt + timedelta(hours=5, minutes=30)
                    hour = dt_ist.hour % 12 or 12
                    ampm = "AM" if dt_ist.hour < 12 else "PM"
                    slot_text = f"at {hour}:{dt_ist.minute:02d} {ampm} IST"
                    
        message = f"Hi {name}, Preetham wants to chat about **{topic}**. I am his AI assistant. It looks like you're both free {slot_text}. Should I send a calendar invite?"
        
        async with httpx.AsyncClient(timeout=15) as http:
            msg_r = await http.post(
                f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"body": {"content": message, "contentType": "html"}},
            )
            
        if msg_r.status_code in (200, 201):
            return {"status": "ok", "message": f"Successfully proposed a meeting to {chat_info['resolved_name']} for {slot_text}."}
        return {"status": "error", "message": msg_r.text}

    @server.tool()
    async def smart_ooo_handoff(backup_colleague_name: str, start_date: str = "today", end_date: str = "soon") -> dict:
        """Hand off active Jira tickets and send a Teams DM to the backup colleague."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        chat_info = await _resolve_user_chat(token, backup_colleague_name)
        if "error" in chat_info:
            return {"status": "error", "message": f"Could not find colleague on Teams: {chat_info['error']}"}
            
        chat_id = chat_info["chat_id"]
        email = chat_info["email"]
        resolved_name = chat_info["resolved_name"]
        
        from tagent.mcp.tools.jira_tools import _get_jira_config, _get_jira_headers
        jira_cfg = _get_jira_config()
        if not jira_cfg["base_url"]:
            return {"status": "error", "message": "Jira credentials not configured."}
            
        headers = _get_jira_headers(jira_cfg)
        
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.get(f"{jira_cfg['base_url']}/rest/api/3/user/search", headers=headers, params={"query": email})
            jira_users = r.json() if r.status_code == 200 else []
            if not jira_users:
                r = await http.get(f"{jira_cfg['base_url']}/rest/api/3/user/search", headers=headers, params={"query": resolved_name})
                jira_users = r.json() if r.status_code == 200 else []
                
            if not jira_users:
                return {"status": "error", "message": f"Found {resolved_name} in Teams, but could not find them in Jira."}
                
            backup_account_id = jira_users[0]["accountId"]
            
            jql = "assignee = currentUser() AND statusCategory != Done"
            r = await http.post(
                f"{jira_cfg['base_url']}/rest/api/3/search/jql",
                headers=headers,
                json={"jql": jql, "fields": ["summary", "status"]}
            )
            
            if r.status_code != 200:
                return {"status": "error", "message": f"Failed to fetch active tickets: {r.text}"}
                
            issues = r.json().get("issues", [])
            handoff_keys = []
            for issue in issues:
                key = issue["key"]
                summary = issue["fields"]["summary"]
                
                await http.put(
                    f"{jira_cfg['base_url']}/rest/api/3/issue/{key}",
                    headers=headers,
                    json={"fields": {"assignee": {"accountId": backup_account_id}}}
                )
                
                comment_payload = {
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": f"I am OOO from {start_date} to {end_date}. Handing this ticket over to {resolved_name} for coverage."}]
                            }
                        ]
                    }
                }
                await http.post(
                    f"{jira_cfg['base_url']}/rest/api/3/issue/{key}/comment",
                    headers=headers,
                    json=comment_payload
                )
                handoff_keys.append(f"{key}: {summary}")
                
        ticket_list_html = "".join([f"<li>{k}</li>" for k in handoff_keys]) if handoff_keys else "<li>No active tickets found!</li>"
        message = f"Hi {resolved_name.split()[0]}, I am heading out of office from {start_date} to {end_date}. I've reassigned the following Jira tickets to you for coverage:<ul>{ticket_list_html}</ul>Thanks!"
        
        async with httpx.AsyncClient(timeout=15) as http:
            msg_r = await http.post(
                f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"body": {"content": message, "contentType": "html"}},
            )
            
        return {
            "status": "ok",
            "message": f"Successfully handed off {len(handoff_keys)} tickets to {resolved_name} and sent them a Teams DM.",
            "tickets": handoff_keys
        }

    @server.tool()
    async def analyze_onedrive_transcript(meeting_name: str) -> dict:
        """Search OneDrive for a meeting transcript and extract its text for analysis."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}
            
        async with httpx.AsyncClient(timeout=30) as http:
            # 1. Search OneDrive for the meeting name
            search_url = f"https://graph.microsoft.com/v1.0/me/drive/root/search(q='{meeting_name}')"
            r = await http.get(search_url, headers={"Authorization": f"Bearer {token}"})
            
            if r.status_code != 200:
                return {"status": "error", "message": f"Failed to search OneDrive: {r.text}"}
                
            items = r.json().get("value", [])
            
            # Find the best match (prioritize .vtt, then .docx, then .txt)
            transcript_item = None
            for ext in [".vtt", ".docx", ".txt"]:
                for item in items:
                    if item.get("name", "").lower().endswith(ext):
                        transcript_item = item
                        break
                if transcript_item:
                    break
                    
            if not transcript_item:
                return {
                    "status": "error", 
                    "message": f"Could not find any transcript file (.vtt, .docx) matching '{meeting_name}' in OneDrive."
                }
                
            item_id = transcript_item["id"]
            file_name = transcript_item["name"]
            
            # 2. Download the file content
            dl_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content"
            dl_r = await http.get(dl_url, headers={"Authorization": f"Bearer {token}"}, follow_redirects=True)
            
            if dl_r.status_code != 200:
                return {"status": "error", "message": f"Failed to download transcript {file_name}: {dl_r.text}"}
                
            raw_bytes = dl_r.content
            extracted_text = ""
            
            # 3. Parse content based on file type
            if file_name.lower().endswith(".docx"):
                import zipfile
                import xml.etree.ElementTree as ET
                import io
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as docx:
                        xml_content = docx.read('word/document.xml')
                        tree = ET.fromstring(xml_content)
                        # Extract all text nodes
                        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                        texts = []
                        for node in tree.iterfind('.//w:t', namespaces):
                            if node.text:
                                texts.append(node.text)
                        extracted_text = " ".join(texts)
                except Exception as e:
                    return {"status": "error", "message": f"Failed to parse docx transcript: {str(e)}"}
            else:
                # .vtt or .txt
                try:
                    extracted_text = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    extracted_text = raw_bytes.decode("latin-1", errors="ignore")
                    
                if file_name.lower().endswith(".vtt"):
                    import re
                    # Remove WEBVTT header and timestamps
                    extracted_text = re.sub(r'WEBVTT.*?\n', '', extracted_text, flags=re.IGNORECASE)
                    extracted_text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}.*?\n', '', extracted_text)
                    # Clean up empty lines
                    extracted_text = "\n".join([line for line in extracted_text.split('\n') if line.strip()])
                    
            if not extracted_text.strip():
                return {"status": "error", "message": "Transcript file was empty or could not be parsed."}
                
            return {
                "status": "ok",
                "meeting_name": meeting_name,
                "file_found": file_name,
                "transcript": extracted_text[:25000]  # Cap length to avoid huge token usage
            }
