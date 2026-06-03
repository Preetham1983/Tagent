import { useState, useEffect, useRef } from "react";
import type { IntegrationType, IntegrationStatus, JiraSettings, CalendarSettings, GoogleCalendarSettings, TeamsDeviceCodeResponse } from "../../types";

type Props = {
  type: IntegrationType;
  integrationStatus: IntegrationStatus | null;
  onSaveJira: (settings: JiraSettings) => Promise<void>;
  onSaveCalendar: (settings: CalendarSettings) => Promise<void>;
  onSaveGoogleCalendar: (settings: GoogleCalendarSettings) => Promise<void>;
  onStartTeamsAuth: () => Promise<TeamsDeviceCodeResponse>;
  onPollTeamsAuth: (deviceCode: string) => Promise<{ status: string; message?: string }>;
  onClose: () => void;
};

// ── Jira Panel ────────────────────────────────────────────────────────────────

function JiraPanel({
  status,
  onSave,
  onClose,
}: {
  status: IntegrationStatus["jira"] | null;
  onSave: (s: JiraSettings) => Promise<void>;
  onClose: () => void;
}) {
  const [baseUrl, setBaseUrl] = useState(status?.base_url ?? "");
  const [email, setEmail] = useState(status?.email ?? "");
  const [apiToken, setApiToken] = useState("");
  const [projectKey, setProjectKey] = useState(status?.project_key ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!baseUrl.trim() || !email.trim() || !apiToken.trim()) {
      setError("Base URL, email, and API token are all required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave({
        jira_base_url: baseUrl.trim(),
        jira_email: email.trim(),
        jira_api_token: apiToken,
        jira_project_key: projectKey.trim().toUpperCase(),
      });
      setSaved(true);
    } catch {
      setError("Failed to save. Make sure the orchestrator service is running.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-body">
      {status?.configured && !saved && (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>
            Connected to <strong>{status.base_url}</strong>
          </span>
        </div>
      )}
      {saved && (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>Jira credentials saved — integration is now active.</span>
        </div>
      )}
      {error && (
        <div className="status-banner error">
          <span className="status-banner-icon">⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Jira Base URL</label>
        <input
          className="form-input"
          type="url"
          placeholder="https://yourcompany.atlassian.net"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          autoComplete="off"
        />
        <p className="form-hint">Your Atlassian workspace URL</p>
      </div>

      <div className="form-group">
        <label className="form-label">Email Address</label>
        <input
          className="form-input"
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <p className="form-hint">
          The email associated with your Atlassian account
        </p>
      </div>

      <div className="form-group">
        <label className="form-label">API Token</label>
        <input
          className="form-input"
          type="password"
          placeholder="••••••••••••••••••••"
          value={apiToken}
          onChange={(e) => setApiToken(e.target.value)}
          autoComplete="new-password"
        />
        <p className="form-hint">
          Generate at{" "}
          <a
            href="https://id.atlassian.com/manage-profile/security/api-tokens"
            target="_blank"
            rel="noopener noreferrer"
          >
            id.atlassian.com → Security → API Tokens
          </a>
        </p>
      </div>

      <div className="form-group">
        <label className="form-label">
          Default Project Key{" "}
          <span className="form-label-optional">(optional)</span>
        </label>
        <input
          className="form-input"
          type="text"
          placeholder="e.g. PROJ"
          value={projectKey}
          onChange={(e) => setProjectKey(e.target.value.toUpperCase())}
          maxLength={20}
        />
        <p className="form-hint">
          Default project for creating issues (e.g.&nbsp;<code>PROJ</code>)
        </p>
      </div>

      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>
          Cancel
        </button>
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Connecting…" : "Connect Jira"}
        </button>
      </div>
    </div>
  );
}

// ── Teams Panel ───────────────────────────────────────────────────────────────

type TeamsStep = "idle" | "starting" | "waiting" | "polling" | "success" | "error";

function TeamsPanel({
  status,
  onStart,
  onPoll,
  onClose,
}: {
  status: IntegrationStatus["teams"] | null;
  onStart: () => Promise<TeamsDeviceCodeResponse>;
  onPoll: (deviceCode: string) => Promise<{ status: string; message?: string }>;
  onClose: () => void;
}) {
  const [step, setStep] = useState<TeamsStep>("idle");
  const [deviceInfo, setDeviceInfo] = useState<TeamsDeviceCodeResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [copied, setCopied] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isConnected = status?.session_active ?? false;
  const canAuth = status?.can_auth ?? true;

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (countRef.current) { clearInterval(countRef.current); countRef.current = null; }
  };

  useEffect(() => () => stopPolling(), []);

  const handleStart = async () => {
    setStep("starting");
    setErrorMsg("");
    try {
      const info = await onStart();
      setDeviceInfo(info);
      setSecondsLeft(info.expires_in);
      setStep("waiting");

      // Countdown timer
      countRef.current = setInterval(() => {
        setSecondsLeft((s) => {
          if (s <= 1) { stopPolling(); setStep("error"); setErrorMsg("Code expired. Please try again."); return 0; }
          return s - 1;
        });
      }, 1000);

      // Poll every interval seconds
      const intervalMs = Math.max((info.interval ?? 5), 5) * 1000;
      pollRef.current = setInterval(async () => {
        setStep("polling");
        try {
          const res = await onPoll(info.device_code);
          if (res.status === "ok") {
            stopPolling();
            setStep("success");
          } else if (res.status === "error") {
            stopPolling();
            setStep("error");
            setErrorMsg(res.message ?? "Authentication failed.");
          } else {
            setStep("waiting"); // still pending
          }
        } catch {
          // network hiccup — keep polling
          setStep("waiting");
        }
      }, intervalMs);
    } catch (e: unknown) {
      setStep("error");
      setErrorMsg(e instanceof Error ? e.message : "Could not start sign-in.");
    }
  };

  const handleCopy = () => {
    if (deviceInfo?.user_code) {
      navigator.clipboard.writeText(deviceInfo.user_code).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  const handleRetry = () => {
    stopPolling();
    setDeviceInfo(null);
    setStep("idle");
    setErrorMsg("");
  };

  const fmtTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="modal-body">
      {/* ── Connected ── */}
      {isConnected && step !== "success" && (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>
            Signed in to Microsoft Teams
            {status?.tenant_id && (
              <span className="status-banner-meta">&nbsp;· Tenant <code>{status.tenant_id}</code></span>
            )}
          </span>
        </div>
      )}

      {/* ── Not connected / app not configured ── */}
      {!isConnected && step === "idle" && !canAuth && (
        <div className="status-banner warning">
          <span className="status-banner-icon">⚠</span>
          <span>
            Teams app credentials (<code>MS_TENANT_ID</code>, <code>MS_CLIENT_ID</code>) are not configured on the server. Contact your admin.
          </span>
        </div>
      )}

      {!isConnected && step === "idle" && canAuth && (
        <div className="status-banner warning">
          <span className="status-banner-icon">⚠</span>
          <span>Not signed in — click below to connect your Microsoft account.</span>
        </div>
      )}

      {/* ── Success ── */}
      {step === "success" && (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>Microsoft Teams connected successfully!</span>
        </div>
      )}

      {/* ── Error ── */}
      {step === "error" && (
        <div className="status-banner error">
          <span className="status-banner-icon">⚠</span>
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ── Device code UI ── */}
      {(step === "waiting" || step === "polling") && deviceInfo && (
        <div className="info-card" style={{ textAlign: "center" }}>
          <p className="info-card-text" style={{ marginBottom: 8 }}>
            Open the link below and enter your code to sign in:
          </p>
          <a
            href={deviceInfo.verification_uri}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            style={{ display: "inline-block", marginBottom: 16, textDecoration: "none" }}
          >
            Open Microsoft sign-in ↗
          </a>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 8 }}>
            <span style={{ fontSize: 28, fontWeight: 700, letterSpacing: 6, fontFamily: "monospace" }}>
              {deviceInfo.user_code}
            </span>
            <button
              className="btn-secondary"
              style={{ padding: "4px 10px", fontSize: 13 }}
              onClick={handleCopy}
            >
              {copied ? "Copied ✓" : "Copy"}
            </button>
          </div>
          <p className="form-hint" style={{ marginTop: 4 }}>
            {step === "polling" ? "Checking…" : `Waiting for sign-in · expires in ${fmtTime(secondsLeft)}`}
          </p>
        </div>
      )}

      {/* ── Idle capabilities list ── */}
      {(step === "idle" || step === "success") && (
        <div className="capability-list">
          <div className="capability-item">
            <span className="capability-icon">💬</span>
            <div>
              <div className="capability-name">Send direct messages</div>
              <div className="capability-desc">Message anyone in your org by name or email</div>
            </div>
          </div>
          <div className="capability-item">
            <span className="capability-icon">📋</span>
            <div>
              <div className="capability-name">Read channels &amp; chats</div>
              <div className="capability-desc">Fetch recent activity and conversation history</div>
            </div>
          </div>
          <div className="capability-item">
            <span className="capability-icon">🔍</span>
            <div>
              <div className="capability-name">Search users</div>
              <div className="capability-desc">Look up colleagues across your directory</div>
            </div>
          </div>
        </div>
      )}

      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>
          {step === "success" ? "Done" : "Cancel"}
        </button>
        {(step === "idle" || step === "success") && canAuth && !isConnected && (
          <button className="btn-primary" onClick={handleStart}>
            Sign in with Microsoft
          </button>
        )}
        {(step === "idle") && canAuth && isConnected && (
          <button className="btn-secondary" onClick={handleStart}>
            Re-authenticate
          </button>
        )}
        {step === "error" && (
          <button className="btn-primary" onClick={handleRetry}>
            Try Again
          </button>
        )}
        {(step === "waiting" || step === "polling") && (
          <button className="btn-secondary" onClick={handleRetry}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

// ── Calendar Panel ────────────────────────────────────────────────────────────

const TIMEZONE_OPTIONS = [
  { value: "India Standard Time",       label: "India (IST, UTC+5:30)" },
  { value: "UTC",                        label: "UTC (UTC+0)" },
  { value: "Eastern Standard Time",     label: "US Eastern (EST, UTC-5)" },
  { value: "Central Standard Time",     label: "US Central (CST, UTC-6)" },
  { value: "Mountain Standard Time",    label: "US Mountain (MST, UTC-7)" },
  { value: "Pacific Standard Time",     label: "US Pacific (PST, UTC-8)" },
  { value: "GMT Standard Time",         label: "UK (GMT, UTC+0)" },
  { value: "W. Europe Standard Time",   label: "Western Europe (CET, UTC+1)" },
  { value: "Arab Standard Time",        label: "Riyadh (AST, UTC+3)" },
  { value: "Arabian Standard Time",     label: "Gulf (GST, UTC+4)" },
  { value: "Pakistan Standard Time",    label: "Pakistan (PKT, UTC+5)" },
  { value: "Bangladesh Standard Time",  label: "Bangladesh (BST, UTC+6)" },
  { value: "SE Asia Standard Time",     label: "SE Asia (ICT, UTC+7)" },
  { value: "China Standard Time",       label: "China (CST, UTC+8)" },
  { value: "Tokyo Standard Time",       label: "Japan (JST, UTC+9)" },
  { value: "AUS Eastern Standard Time", label: "Australia Eastern (AEST, UTC+10)" },
];

function CalendarPanel({
  status,
  onSave,
  onClose,
}: {
  status: IntegrationStatus["calendar"] | null;
  onSave: (s: CalendarSettings) => Promise<void>;
  onClose: () => void;
}) {
  const [timezone, setTimezone] = useState(
    status?.timezone ?? "India Standard Time"
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({ timezone });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-body">
      {status?.configured ? (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>Connected via Microsoft Graph API</span>
        </div>
      ) : (
        <div className="status-banner warning">
          <span className="status-banner-icon">⚠</span>
          <span>Calendar shares credentials with Teams. Configure Teams first.</span>
        </div>
      )}

      {saved && (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>Timezone saved — calendar events will now display in {TIMEZONE_OPTIONS.find(o => o.value === timezone)?.label ?? timezone}.</span>
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Display Timezone</label>
        <select
          className="form-input"
          value={timezone}
          onChange={(e) => { setTimezone(e.target.value); setSaved(false); }}
        >
          {TIMEZONE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <p className="form-hint">
          Calendar events will be shown in this timezone regardless of your Exchange mailbox setting.
        </p>
      </div>

      <div className="capability-list">
        <div className="capability-item">
          <span className="capability-icon">📅</span>
          <div><div className="capability-name">View calendar</div><div className="capability-desc">Today's events and upcoming schedule</div></div>
        </div>
        <div className="capability-item">
          <span className="capability-icon">🕐</span>
          <div><div className="capability-name">Find free slots</div><div className="capability-desc">Check availability across attendees</div></div>
        </div>
        <div className="capability-item">
          <span className="capability-icon">📬</span>
          <div><div className="capability-name">Book meetings</div><div className="capability-desc">Schedule and send calendar invites</div></div>
        </div>
      </div>

      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save Timezone"}
        </button>
      </div>
    </div>
  );
}

// ── GitHub Panel ─────────────────────────────────────────────────────────────

function GitHubPanel({
  status,
  onClose,
}: {
  status: IntegrationStatus["github"] | null;
  onClose: () => void;
}) {
  return (
    <div className="modal-body">
      {status?.configured ? (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>
            Connected — default repo:{" "}
            <strong>
              {status.owner}/{status.repo}
            </strong>
          </span>
        </div>
      ) : (
        <div className="status-banner warning">
          <span className="status-banner-icon">⚠</span>
          <span>GitHub token not configured. Set GITHUB_TOKEN on the server.</span>
        </div>
      )}
      <div className="info-card">
        <p className="info-card-text">
          Set the following environment variables in the orchestrator <code>.env</code>:
        </p>
        <ul className="info-card-list">
          <li><code>GITHUB_TOKEN</code> — Personal Access Token (repo scope)</li>
          <li><code>GITHUB_DEFAULT_OWNER</code> — Default GitHub username or org</li>
          <li><code>GITHUB_DEFAULT_REPO</code> — Default repository name</li>
        </ul>
      </div>
      <div className="capability-list">
        <div className="capability-item"><span className="capability-icon">📦</span><div><div className="capability-name">List repos & issues</div><div className="capability-desc">Browse your repositories and open issues</div></div></div>
        <div className="capability-item"><span className="capability-icon">🔀</span><div><div className="capability-name">Review pull requests</div><div className="capability-desc">See open PRs with author and branch info</div></div></div>
        <div className="capability-item"><span className="capability-icon">➕</span><div><div className="capability-name">Create issues</div><div className="capability-desc">Open new issues directly from chat</div></div></div>
      </div>
      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

// ── Notion Panel ──────────────────────────────────────────────────────────────

function NotionPanel({
  status,
  onClose,
}: {
  status: IntegrationStatus["notion"] | null;
  onClose: () => void;
}) {
  return (
    <div className="modal-body">
      {status?.configured ? (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>Connected to Notion workspace</span>
        </div>
      ) : (
        <div className="status-banner warning">
          <span className="status-banner-icon">⚠</span>
          <span>Notion token not configured. Set NOTION_TOKEN on the server.</span>
        </div>
      )}
      <div className="info-card">
        <p className="info-card-text">
          Set the following environment variables in the orchestrator <code>.env</code>:
        </p>
        <ul className="info-card-list">
          <li><code>NOTION_TOKEN</code> — Notion Internal Integration Token</li>
          <li><code>NOTION_DATABASE_ID</code> — Default database ID (optional)</li>
        </ul>
        <p className="info-card-text" style={{marginTop: 8}}>
          Get your token at <strong>notion.so/my-integrations</strong>.
        </p>
      </div>
      <div className="capability-list">
        <div className="capability-item"><span className="capability-icon">🔍</span><div><div className="capability-name">Search pages</div><div className="capability-desc">Full-text search across your workspace</div></div></div>
        <div className="capability-item"><span className="capability-icon">📋</span><div><div className="capability-name">Browse databases</div><div className="capability-desc">List pages in any Notion database</div></div></div>
        <div className="capability-item"><span className="capability-icon">✏️</span><div><div className="capability-name">Create pages</div><div className="capability-desc">Add new pages to any database</div></div></div>
      </div>
      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

// ── Google Calendar Panel ─────────────────────────────────────────────────────

function GoogleCalendarPanel({
  status,
  onSave,
  onClose,
}: {
  status: IntegrationStatus["google_calendar"] | null;
  onSave: (s: GoogleCalendarSettings) => Promise<void>;
  onClose: () => void;
}) {
  const [credPath, setCredPath] = useState(status?.configured ? "••• (configured)" : "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    const trimmed = credPath.trim();
    if (!trimmed || trimmed.startsWith("•")) {
      setError("Please enter the absolute path to your gcp-oauth.keys.json file.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave({ credentials_path: trimmed });
      setSaved(true);
    } catch {
      setError("Failed to save. Make sure the orchestrator service is running.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-body">
      {(status?.configured || saved) && (
        <div className="status-banner success">
          <span className="status-banner-icon">✓</span>
          <span>Connected to Google Calendar</span>
        </div>
      )}
      {!status?.configured && !saved && (
        <div className="status-banner warning">
          <span className="status-banner-icon">⚠</span>
          <span>Google Calendar not configured — paste your credentials path below.</span>
        </div>
      )}
      {error && (
        <div className="status-banner error">
          <span className="status-banner-icon">⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className="form-group">
        <label className="form-label">OAuth Credentials File Path</label>
        <input
          className="form-input"
          type="text"
          placeholder="C:\Users\you\.tagent\gcp-oauth.keys.json"
          value={credPath}
          onChange={(e) => { setCredPath(e.target.value); setSaved(false); }}
          onFocus={() => { if (credPath.startsWith("•")) setCredPath(""); }}
          autoComplete="off"
          spellCheck={false}
        />
        <p className="form-hint">
          Absolute path to your <code>gcp-oauth.keys.json</code> Desktop OAuth credentials file from{" "}
          <a href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer">
            Google Cloud Console
          </a>
        </p>
      </div>

      <div className="info-card">
        <p className="info-card-text">
          After saving, run this once to complete OAuth sign-in:
        </p>
        <code style={{ display: "block", padding: "6px 8px", background: "var(--bg-tertiary, #1e1e1e)", borderRadius: 4, fontSize: 13 }}>
          npx @cocal/google-calendar-mcp auth
        </code>
      </div>

      <div className="capability-list">
        <div className="capability-item"><span className="capability-icon">🗓️</span><div><div className="capability-name">View events</div><div className="capability-desc">See today's or any day's calendar events and Google Meet links</div></div></div>
        <div className="capability-item"><span className="capability-icon">⏰</span><div><div className="capability-name">Create &amp; search events</div><div className="capability-desc">Add meetings and search across your calendars</div></div></div>
      </div>

      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ── Memory Panel ──────────────────────────────────────────────────────────────

function MemoryPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-body">
      <div className="status-banner info">
        <span className="status-banner-icon">✓</span>
        <span>Agent memory is always active in your session</span>
      </div>

      <div className="info-card">
        <p className="info-card-text">
          Tagent maintains conversation context and key information throughout
          your session using built-in memory tools. This helps provide more
          relevant and personalised responses over time and allows the agent to
          refer back to earlier parts of your conversation.
        </p>
      </div>

      <div className="capability-list">
        <div className="capability-item">
          <span className="capability-icon">🧠</span>
          <div>
            <div className="capability-name">Session context</div>
            <div className="capability-desc">
              Remembers previous messages within a session
            </div>
          </div>
        </div>
        <div className="capability-item">
          <span className="capability-icon">💾</span>
          <div>
            <div className="capability-name">Key facts</div>
            <div className="capability-desc">
              Stores important facts for use across steps
            </div>
          </div>
        </div>
      </div>

      <div className="form-actions">
        <button className="btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

// ── Modal Shell ───────────────────────────────────────────────────────────────

const MODAL_CONFIG: Record<
  IntegrationType,
  { title: string; subtitle: string; icon: string; bg: string }
> = {
  jira: {
    title: "Jira",
    subtitle: "Connect to your Atlassian Jira workspace",
    icon: "🔷",
    bg: "#0052CC",
  },
  teams: {
    title: "Microsoft Teams",
    subtitle: "Connect Tagent to your Teams workspace",
    icon: "💬",
    bg: "#5059C9",
  },
  calendar: {
    title: "Microsoft 365 Calendar",
    subtitle: "Access your calendar and schedule meetings",
    icon: "📅",
    bg: "#0078D4",
  },
  memory: {
    title: "Agent Memory",
    subtitle: "How Tagent remembers context across steps",
    icon: "🧠",
    bg: "#7C3AED",
  },
  github: {
    title: "GitHub",
    subtitle: "Browse repos, PRs, and issues",
    icon: "🐙",
    bg: "#24292F",
  },
  notion: {
    title: "Notion",
    subtitle: "Search and create pages in your workspace",
    icon: "📝",
    bg: "#000000",
  },
  google_calendar: {
    title: "Google Calendar",
    subtitle: "Access your Google Calendar events",
    icon: "🗓️",
    bg: "#1A73E8",
  },
};

export function SettingsModal({
  type,
  integrationStatus,
  onSaveJira,
  onSaveCalendar,
  onSaveGoogleCalendar,
  onStartTeamsAuth,
  onPollTeamsAuth,
  onClose,
}: Props) {
  const cfg = MODAL_CONFIG[type];

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true">
        {/* Header */}
        <div className="modal-header">
          <div
            className="modal-header-icon"
            style={{ background: cfg.bg + "18" }}
          >
            {cfg.icon}
          </div>
          <div>
            <div className="modal-header-title">{cfg.title}</div>
            <div className="modal-header-subtitle">{cfg.subtitle}</div>
          </div>
          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        {type === "jira" && (
          <JiraPanel
            status={integrationStatus?.jira ?? null}
            onSave={onSaveJira}
            onClose={onClose}
          />
        )}
        {type === "teams" && (
          <TeamsPanel
            status={integrationStatus?.teams ?? null}
            onStart={onStartTeamsAuth}
            onPoll={onPollTeamsAuth}
            onClose={onClose}
          />
        )}
        {type === "calendar" && (
          <CalendarPanel
            status={integrationStatus?.calendar ?? null}
            onSave={onSaveCalendar}
            onClose={onClose}
          />
        )}
        {type === "memory" && <MemoryPanel onClose={onClose} />}
        {type === "github" && (
          <GitHubPanel
            status={integrationStatus?.github ?? null}
            onClose={onClose}
          />
        )}
        {type === "notion" && (
          <NotionPanel
            status={integrationStatus?.notion ?? null}
            onClose={onClose}
          />
        )}
        {type === "google_calendar" && (
          <GoogleCalendarPanel
            status={integrationStatus?.google_calendar ?? null}
            onSave={onSaveGoogleCalendar}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}
