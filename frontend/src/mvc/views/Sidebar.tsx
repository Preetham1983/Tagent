import type { IntegrationStatus, IntegrationType } from "../../types";

type Props = {
  activeIntegration: IntegrationType | null;
  onSelectIntegration: (type: IntegrationType) => void;
  integrationStatus: IntegrationStatus | null;
};

const INTEGRATIONS: Array<{
  id: IntegrationType;
  name: string;
  icon: string;
  bg: string;
  fg: string;
  description: string;
}> = [
  {
    id: "jira",
    name: "Jira",
    icon: "🔷",
    bg: "#0052CC",
    fg: "#0052CC",
    description: "Issues & projects",
  },
  {
    id: "github",
    name: "GitHub",
    icon: "🐙",
    bg: "#24292F",
    fg: "#24292F",
    description: "Repos, PRs & issues",
  },
  {
    id: "notion",
    name: "Notion",
    icon: "📝",
    bg: "#000000",
    fg: "#374151",
    description: "Pages & databases",
  },
  {
    id: "google_calendar",
    name: "Google Calendar",
    icon: "🗓️",
    bg: "#1A73E8",
    fg: "#1A73E8",
    description: "Events & scheduling",
  },
  {
    id: "teams",
    name: "Microsoft Teams",
    icon: "💬",
    bg: "#5059C9",
    fg: "#5059C9",
    description: "Messaging & calls",
  },
  {
    id: "calendar",
    name: "MS Calendar",
    icon: "📅",
    bg: "#0078D4",
    fg: "#0078D4",
    description: "Microsoft 365",
  },
  {
    id: "memory",
    name: "Memory",
    icon: "🧠",
    bg: "#7C3AED",
    fg: "#7C3AED",
    description: "Agent context",
  },
];

function getStatusColor(
  id: IntegrationType,
  status: IntegrationStatus | null,
): "green" | "gray" {
  if (!status) return "gray";
  if (id === "jira") return status.jira.configured ? "green" : "gray";
  if (id === "teams") return status.teams.configured ? "green" : "gray";
  if (id === "calendar") return status.calendar.configured ? "green" : "gray";
  if (id === "github") return status.github?.configured ? "green" : "gray";
  if (id === "notion") return status.notion?.configured ? "green" : "gray";
  if (id === "google_calendar") return status.google_calendar?.configured ? "green" : "gray";
  if (id === "memory") return "green";
  return "gray";
}

function getStatusLabel(
  id: IntegrationType,
  status: IntegrationStatus | null,
): string {
  if (!status) return "Not connected";
  if (id === "jira") return status.jira.configured ? "Connected" : "Not configured";
  if (id === "teams") return status.teams.configured ? "Connected" : "Not configured";
  if (id === "calendar") return status.calendar.configured ? "Connected" : "Not configured";
  if (id === "github") return status.github?.configured ? "Connected" : "Set GITHUB_TOKEN";
  if (id === "notion") return status.notion?.configured ? "Connected" : "Set NOTION_TOKEN";
  if (id === "google_calendar") return status.google_calendar?.configured ? "Connected" : "Set GCAL_MCP_OAUTH_CREDENTIALS";
  if (id === "memory") return "Always active";
  return "";
}

export function Sidebar({
  activeIntegration,
  onSelectIntegration,
  integrationStatus,
}: Props) {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">T</div>
        <div>
          <div className="sidebar-logo-text">Tagent</div>
          <div className="sidebar-logo-badge">ENTERPRISE AI</div>
        </div>
      </div>

      {/* Chat nav item */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">Workspace</div>
        <div className="sidebar-item active-nav">
          <div
            className="sidebar-item-icon"
            style={{ background: "#FFFFFF12", color: "#FFFFFF" }}
          >
            💬
          </div>
          <div className="sidebar-item-content">
            <div className="sidebar-item-name">Chat</div>
            <div className="sidebar-item-status">AI assistant</div>
          </div>
        </div>
      </div>

      {/* Integrations */}
      <div className="sidebar-section" style={{ flex: 1 }}>
        <div className="sidebar-section-label">Integrations</div>
        {INTEGRATIONS.map((integration) => {
          const color = getStatusColor(integration.id, integrationStatus);
          const label = getStatusLabel(integration.id, integrationStatus);
          const isActive = activeIntegration === integration.id;
          return (
            <div
              key={integration.id}
              className={`sidebar-item${isActive ? " active" : ""}`}
              onClick={() => onSelectIntegration(integration.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelectIntegration(integration.id)}
            >
              <div
                className="sidebar-item-icon"
                style={{
                  background: integration.bg + "22",
                  color: integration.fg,
                }}
              >
                {integration.icon}
              </div>
              <div className="sidebar-item-content">
                <div className="sidebar-item-name">{integration.name}</div>
                <div className="sidebar-item-status">{integration.description}</div>
              </div>
              <div
                className="status-dot-wrapper"
                title={label}
              >
                <div className={`status-dot ${color}`} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-footer-info">
          <div className="sidebar-footer-label">
            {integrationStatus
              ? `${[
                  integrationStatus.jira.configured,
                  integrationStatus.teams.configured,
                  integrationStatus.calendar.configured,
                  true,
                ].filter(Boolean).length} / 4 integrations active`
              : "Loading integrations…"}
          </div>
        </div>
      </div>
    </aside>
  );
}
