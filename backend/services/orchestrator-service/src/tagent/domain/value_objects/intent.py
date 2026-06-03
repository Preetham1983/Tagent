from __future__ import annotations

from enum import Enum


class Intent(Enum):
    SUMMARIZE_MEETING = "summarize_meeting"
    SCHEDULE_MEETING = "schedule_meeting"
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    QUERY_TASKS = "query_tasks"
    QUERY_CALENDAR = "query_calendar"
    SEND_MESSAGE = "send_message"
    GET_USER_INFO = "get_user_info"
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"
