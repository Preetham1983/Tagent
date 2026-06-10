import type { IntegrationStatus, IntegrationType } from "../../types";

type Props = {
  activeIntegration: IntegrationType | null;
  onSelectIntegration: (type: IntegrationType) => void;
  integrationStatus: IntegrationStatus | null;
  onNewConversation?: () => void;
};

const INTEGRATIONS: Array<{
  id: IntegrationType;
  name: string;
  icon: string;
  bg: string;
  description: string;
}> = [
  { id: "jira",             name: "Jira",             icon: "🔷", bg: "#0052CC", description: "Issues & projects" },
  { id: "github",           name: "GitHub",           icon: "🐙", bg: "#24292F", description: "Repos, PRs & issues" },
  { id: "notion",           name: "Notion",           icon: "📝", bg: "#374151", description: "Pages & databases" },
  { id: "google_calendar",  name: "Google Calendar",  icon: "🗓️", bg: "#1A73E8", description: "Events & scheduling" },
  { id: "teams",            name: "Microsoft Teams",  icon: "💬", bg: "#5059C9", description: "Messaging & calls" },
  { id: "calendar",         name: "MS Calendar",      icon: "📅", bg: "#0078D4", description: "Microsoft 365" },
  { id: "memory",           name: "Memory",           icon: "🧠", bg: "#7C3AED", description: "Agent context" },
];

function isConfigured(id: IntegrationType, status: IntegrationStatus | null): boolean {
  if (!status) return false;
  if (id === "jira")             return status.jira.configured;
  if (id === "teams")            return status.teams.configured;
  if (id === "calendar")         return status.calendar.configured;
  if (id === "github")           return status.github?.configured ?? false;
  if (id === "notion")           return status.notion?.configured ?? false;
  if (id === "google_calendar")  return status.google_calendar?.configured ?? false;
  if (id === "memory")           return true;
  return false;
}

function getStatusDetail(id: IntegrationType, status: IntegrationStatus | null): string {
  if (!status) return "Not connected";
  if (id === "jira") return status.jira.configured ? status.jira.base_url.replace("https://", "") : "Not configured";
  if (id === "teams") return status.teams.configured ? "Connected" : status.teams.can_auth ? "Click to connect" : "Not configured";
  if (id === "calendar") return status.calendar.configured ? status.calendar.timezone : "Needs Teams first";
  if (id === "github") return status.github?.configured ? `${status.github.owner}/${status.github.repo}` : "Set GITHUB_TOKEN";
  if (id === "notion") return status.notion?.configured ? "Connected" : "Set NOTION_TOKEN";
  if (id === "google_calendar") return status.google_calendar?.configured ? "Connected" : "Set credentials";
  if (id === "memory") return "Always active";
  return "";
}

export function Sidebar({
  activeIntegration,
  onSelectIntegration,
  integrationStatus,
  onNewConversation,
}: Props) {
  const connectedCount = INTEGRATIONS.filter((i) =>
    isConfigured(i.id, integrationStatus),
  ).length;

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

      {/* Workspace nav */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">Workspace</div>
        <div className="sidebar-item active-nav">
          <div
            className="sidebar-item-icon"
            style={{ background: "rgba(255,255,255,0.08)", color: "#fff" }}
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
      <div className="sidebar-section" style={{ flex: 1, overflowY: "auto" }}>
        <div className="sidebar-section-label">Integrations</div>
        {INTEGRATIONS.map((integration) => {
          const connected = isConfigured(integration.id, integrationStatus);
          const detail = getStatusDetail(integration.id, integrationStatus);
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
                  color: integration.bg === "#374151" ? "#9ca3af" : integration.bg,
                }}
              >
                {integration.icon}
              </div>
              <div className="sidebar-item-content">
                <div className="sidebar-item-name">{integration.name}</div>
                <div
                  className="sidebar-item-status"
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: 130,
                  }}
                  title={detail}
                >
                  {detail}
                </div>
              </div>
              <div className="status-dot-wrapper" title={connected ? "Connected" : "Disconnected"}>
                <div className={`status-dot ${connected ? "green" : "gray"}`} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        {integrationStatus ? (
          <div className="sidebar-footer-label">
            {connectedCount} of {INTEGRATIONS.length} integrations active
          </div>
        ) : (
          <div className="sidebar-footer-label">Loading integrations…</div>
        )}
        {onNewConversation && (
          <button className="sidebar-new-chat-btn" onClick={onNewConversation}>
            <span>+</span>
            <span>New Conversation</span>
          </button>
        )}
      </div>
    </aside>
  );
}
