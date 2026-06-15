import type { CommandTool } from "../../types";

const JIRA_TOOLS: CommandTool[] = [
  {
    id: "list_jira_issues",
    label: "List all issues",
    icon: "🔷",
    description: "Show all open issues in your Jira project",
    category: "Jira",
    placeholderQuery: "",
  },
  {
    id: "search_closed_issues",
    label: "List closed/done issues",
    icon: "✅",
    description: "Show issues with status Done or Closed",
    category: "Jira",
    placeholderQuery: "",
  },
  {
    id: "search_jira_issues",
    label: "Search issues",
    icon: "🔍",
    description: "Search by keyword or JQL query",
    category: "Jira",
    placeholderQuery: "e.g. bug in login  or  status = 'In Progress'",
  },
  {
    id: "list_jira_projects",
    label: "List projects",
    icon: "📁",
    description: "Show all accessible Jira projects",
    category: "Jira",
    placeholderQuery: "",
  },
  {
    id: "list_project_members",
    label: "List project members",
    icon: "👥",
    description: "Show all users assigned to a Jira project",
    category: "Jira",
    placeholderQuery: "e.g. ITP  (leave blank for default project)",
  },
  {
    id: "create_jira_issue",
    label: "Create issue",
    icon: "➕",
    description: "Create a new Jira task / bug",
    category: "Jira",
    placeholderQuery: "e.g. Fix login bug — high priority",
  },
];

const GITHUB_TOOLS: CommandTool[] = [
  {
    id: "list_github_repos",
    label: "List repositories",
    icon: "📦",
    description: "Show your GitHub repos (or a specific user's)",
    category: "GitHub",
    placeholderQuery: "e.g. octocat  (leave blank for your account)",
  },
  {
    id: "list_github_prs",
    label: "List pull requests",
    icon: "🔀",
    description: "Show open PRs for the default repo",
    category: "GitHub",
    placeholderQuery: "open / closed / all  (default: open)",
  },
  {
    id: "list_github_issues",
    label: "List GitHub issues",
    icon: "⚠️",
    description: "Show issues for the default repo",
    category: "GitHub",
    placeholderQuery: "open / closed / all  (default: open)",
  },
  {
    id: "create_github_issue",
    label: "Create GitHub issue",
    icon: "➕",
    description: "Create a new issue in the default repo",
    category: "GitHub",
    placeholderQuery: "e.g. Fix broken login page",
  },
];

const NOTION_TOOLS: CommandTool[] = [
  {
    id: "search_notion",
    label: "Search Notion",
    icon: "🔍",
    description: "Full-text search across all Notion pages",
    category: "Notion",
    placeholderQuery: "e.g. sprint retrospective",
  },
  {
    id: "list_notion_pages",
    label: "List Notion pages",
    icon: "📋",
    description: "List pages in the default Notion database",
    category: "Notion",
    placeholderQuery: "",
  },
  {
    id: "create_notion_page",
    label: "Create Notion page",
    icon: "✏️",
    description: "Create a new page in the default database",
    category: "Notion",
    placeholderQuery: "e.g. Q3 Retrospective notes",
  },
];

const GCAL_TOOLS: CommandTool[] = [
  {
    id: "list_google_calendar_events",
    label: "Today's Google Calendar",
    icon: "🗓️",
    description: "Show today's events from Google Calendar",
    category: "Google Calendar",
    placeholderQuery: "e.g. 2026-05-20  (leave blank for today)",
  },
  {
    id: "create_google_calendar_event",
    label: "Create calendar event",
    icon: "⏰",
    description: "Add an event to Google Calendar",
    category: "Google Calendar",
    placeholderQuery: "e.g. Team standup 2026-05-20T09:00:00",
  },
];

const MS_TEAMS_365_TOOLS: CommandTool[] = [
  {
    id: "list_calendar_events",
    label: "Today's Schedule (Teams/365)",
    icon: "📅",
    description: "Show today's meetings from your MS 365 calendar",
    category: "Microsoft 365",
    placeholderQuery: "",
  },
  {
    id: "join_meeting_as_bot",
    label: "Join Meeting as Bot",
    icon: "🤖",
    description: "Join a Teams meeting as Tagent Note-Taker and scrape live captions",
    category: "Microsoft 365",
    placeholderQuery: "Paste Teams meeting URL here",
  },
  {
    id: "send_direct_message",
    label: "Send Teams Message",
    icon: "💬",
    description: "Send a direct message to a user via Teams",
    category: "Microsoft 365",
    placeholderQuery: "e.g. user@example.com - Hello there!",
  },
  {
    id: "schedule_meeting",
    label: "Schedule Meeting (Teams)",
    icon: "⏰",
    description: "Schedule a new Teams meeting",
    category: "Microsoft 365",
    placeholderQuery: "e.g. user@example.com - Project Sync at 2pm",
  },
  {
    id: "get_user_info",
    label: "My Profile (Teams/365)",
    icon: "👤",
    description: "Show your current Microsoft Teams profile and reporting manager",
    category: "Microsoft 365",
    placeholderQuery: "",
  },
  {
    id: "search_user",
    label: "Find Colleague",
    icon: "🔎",
    description: "Search for a colleague by name and get their email",
    category: "Microsoft 365",
    placeholderQuery: "e.g. Aasrith  or  Preetham",
  },
  {
    id: "list_recent_chats",
    label: "Recent Chats",
    icon: "🗨️",
    description: "Show your most recent Teams conversations",
    category: "Microsoft 365",
    placeholderQuery: "",
  },
  {
    id: "read_chat_messages",
    label: "Read Chat Messages",
    icon: "📨",
    description: "Read messages from a Teams chat (paste chat ID from Recent Chats)",
    category: "Microsoft 365",
    placeholderQuery: "paste chat ID here",
  },
  {
    id: "get_meeting_attendance",
    label: "Meeting Attendance",
    icon: "📋",
    description: "See who attended a recent Teams meeting",
    category: "Microsoft 365",
    placeholderQuery: "e.g. Sprint Review  (leave blank for latest)",
  },
  {
    id: "get_daily_briefing",
    label: "Smart Daily Briefing",
    icon: "✨",
    description: "Personalised morning briefing — meetings, Jira issues, PRs and Teams chats in one view",
    category: "Microsoft 365",
    placeholderQuery: "",
  },
  {
    id: "generate_standup",
    label: "Auto Standup Generator",
    icon: "🚀",
    description: "Generate your daily standup — yesterday's wins, today's tasks, blockers",
    category: "Microsoft 365",
    placeholderQuery: "",
  },
  {
    id: "get_meeting_transcript",
    label: "Meeting Transcript",
    icon: "🎙️",
    description: "Fetch transcript of a recent Teams meeting (requires admin permission)",
    category: "Microsoft 365",
    placeholderQuery: "e.g. Sprint Review  (leave blank for latest)",
  },
  {
    id: "analyze_meeting",
    label: "AI Meeting Analysis (Chat)",
    icon: "🧠",
    description: "Analyze a meeting — reads chat, attendees & generates AI summary with action items",
    category: "Microsoft 365",
    placeholderQuery: "e.g. Sprint Review  (leave blank for latest meeting)",
  },
  {
    id: "analyze_onedrive_transcript",
    label: "AI Meeting Analysis (OneDrive Transcript)",
    icon: "📄",
    description: "Analyze a meeting by downloading its raw .vtt/.docx transcript from your OneDrive",
    category: "Microsoft 365",
    placeholderQuery: "e.g. Sprint Review",
  },
];

export const AUTOMATION_TOOLS: CommandTool[] = [
  {
    id: "nudge_colleague",
    label: "Polite Nudger (Teams)",
    icon: "⏰",
    description: "Send a polite follow-up DM to a colleague about a blocker (Jira/GitHub)",
    category: "Automation",
    placeholderQuery: "e.g. Alex, PR-42",
  },
  {
    id: "chat_to_jira",
    label: "Chat to Jira (Summarize)",
    icon: "📥",
    description: "Turn your recent 1:1 chat with a colleague into a Jira ticket",
    category: "Automation",
    placeholderQuery: "e.g. Alex",
  },
  {
    id: "negotiate_meeting",
    label: "Find The Gap (Meet)",
    icon: "🔀",
    description: "Find mutual free time with a colleague and DM them to propose it",
    category: "Automation",
    placeholderQuery: "e.g. Alex, Deployment discussion",
  },
  {
    id: "smart_ooo_handoff",
    label: "Smart OOO Handoff",
    icon: "🏖️",
    description: "Reassign your active Jira tickets to a colleague and DM them",
    category: "Automation",
    placeholderQuery: "e.g. Alex, tomorrow, next week",
  },
];

export const DACL_TOOLS: CommandTool[] = [
  {
    id: "validate_business_rule",
    label: "Validate Business Rule",
    icon: "⚖️",
    description: "Run a business rule check against the DACL engine (premium, eligibility, policy)",
    category: "Business Rules",
    placeholderQuery: 'e.g. {"age": 24, "tier": "BASIC", "pre_existing_conditions": 0, "product": "health_insurance"}',
  },
  {
    id: "list_available_policies",
    label: "List Available Policies",
    icon: "📋",
    description: "Show all business rule policies registered in the DACL engine",
    category: "Business Rules",
    placeholderQuery: "",
  },
];

export const ALL_TOOLS: CommandTool[] = [
  ...JIRA_TOOLS,
  ...GITHUB_TOOLS,
  ...NOTION_TOOLS,
  ...GCAL_TOOLS,
  ...MS_TEAMS_365_TOOLS,
  ...AUTOMATION_TOOLS,
  ...DACL_TOOLS,
];

type Props = {
  filter: string;
  onSelect: (tool: CommandTool) => void;
  onClose: () => void;
  anchorBottom?: number;
};

export function CommandPalette({ filter, onSelect, onClose, anchorBottom }: Props) {
  const lower = filter.toLowerCase();
  const filtered = ALL_TOOLS.filter(
    (t) =>
      t.label.toLowerCase().includes(lower) ||
      t.description.toLowerCase().includes(lower) ||
      t.category.toLowerCase().includes(lower),
  );

  return (
    <div
      className="cmd-palette"
      style={anchorBottom !== undefined ? { bottom: anchorBottom } : undefined}
    >
      <div className="cmd-palette-header">
        <span className="cmd-palette-hint">
          Select a tool — Tagent will call it directly
        </span>
        <button className="cmd-palette-close" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="cmd-palette-list">
        {filtered.length === 0 && (
          <div className="cmd-palette-empty">No matching tools</div>
        )}

        {filtered.map((tool) => (
          <div
            key={tool.id}
            className="cmd-palette-item"
            onClick={() => onSelect(tool)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onSelect(tool)}
          >
            <span className="cmd-palette-item-icon">{tool.icon}</span>
            <div className="cmd-palette-item-body">
              <div className="cmd-palette-item-label">
                <span className="cmd-palette-category">{tool.category}</span>
                {" · "}
                {tool.label}
              </div>
              <div className="cmd-palette-item-desc">{tool.description}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
