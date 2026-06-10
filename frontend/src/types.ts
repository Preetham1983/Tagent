export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  toolName?: string;
  stepResults?: Array<{ step: string; status: string; output: string }>;
  brnValidation?: BrnValidation;
};

export type BrnValidation = {
  enabled: boolean;
  intent_check?: {
    passed: boolean | null;
    policy_name?: string | null;
    allowed?: string | null;
    auto_execute?: string | null;
  } | null;
  step_checks?: Array<{
    step: string;
    passed: boolean;
    allowed: string;
  }>;
};

export type OrchestrateResponse = {
  response: string;
  tool_results: Array<{ step: string; status: string; output: string }>;
  approval: {
    required: boolean;
    description: string | null;
    level: string | null;
    status: string | null;
  };
  brn_validation?: BrnValidation;
};

export type IntegrationType =
  | "jira"
  | "teams"
  | "calendar"
  | "memory"
  | "github"
  | "notion"
  | "google_calendar";

export type ToolId =
  | "list_jira_issues"
  | "search_jira_issues"
  | "search_closed_issues"
  | "list_jira_projects"
  | "list_project_members"
  | "create_jira_issue"
  // GitHub
  | "list_github_repos"
  | "list_github_prs"
  | "list_github_issues"
  | "create_github_issue"
  // Notion
  | "search_notion"
  | "list_notion_pages"
  | "create_notion_page"
  // Google Calendar
  | "list_google_calendar_events"
  | "create_google_calendar_event"
  // Microsoft 365 / Teams
  | "list_calendar_events"
  | "send_direct_message"
  | "schedule_meeting"
  | "get_user_info"
  | "search_user"
  | "list_recent_chats"
  | "read_chat_messages"
  | "get_meeting_attendance"
  | "get_meeting_transcript"
  | "analyze_meeting"
  // Smart Briefing
  | "get_daily_briefing"
  | "generate_standup"
  // Automation Tools
  | "nudge_colleague"
  | "chat_to_jira"
  | "negotiate_meeting"
  | "smart_ooo_handoff"
  | "analyze_onedrive_transcript"
  // DACL Business Rules
  | "validate_business_rule"
  | "list_available_policies";

export type UserSuggestion = {
  name: string;
  email: string;
  job_title?: string;
  department?: string;
};

export type CommandTool = {
  id: ToolId;
  label: string;
  icon: string;
  description: string;
  category: string;
  placeholderQuery?: string;
};

export type DirectToolRequest = {
  tool_name: ToolId;
  query?: string;
  jql?: string;
  title?: string;
  description?: string;
  priority?: string;
  user_id?: string;
};

export type DirectToolResponse = {
  status: string;
  tool: string;
  response: string;
  raw: unknown;
  brn_validation?: BrnValidation;
};

export type CalendarSettings = {
  timezone: string;
};

export type GoogleCalendarSettings = {
  credentials_path: string;
};

export type TeamsDeviceCodeResponse = {
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
  device_code: string;
};

export type TeamsAuthPollResponse = {
  status: "ok" | "pending" | "error";
  message?: string;
};

export type JiraSettings = {
  jira_base_url: string;
  jira_email: string;
  jira_api_token: string;
  jira_project_key: string;
};

export type IntegrationStatus = {
  jira: {
    configured: boolean;
    base_url: string;
    email: string;
    project_key: string;
  };
  teams: {
    configured: boolean;
    session_active: boolean;
    can_auth: boolean;
    tenant_id: string;
  };
  calendar: {
    configured: boolean;
    timezone: string;
  };
  github: {
    configured: boolean;
    owner: string;
    repo: string;
  };
  notion: {
    configured: boolean;
    database_id: string;
  };
  google_calendar: {
    configured: boolean;
    calendar_id: string;
  };
};

export type PendingApproval = {
  required: boolean;
  description: string | null;
  level: string | null;
  status: string | null;
};
