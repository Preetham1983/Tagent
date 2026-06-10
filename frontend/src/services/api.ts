import type {
  OrchestrateResponse,
  JiraSettings,
  CalendarSettings,
  GoogleCalendarSettings,
  IntegrationStatus,
  TeamsDeviceCodeResponse,
  TeamsAuthPollResponse,
} from "../types";

type OrchestratePayload = {
  user_id: string;
  thread_id: string;
  message: string;
};

async function extractError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    return (body as { detail?: string }).detail ?? fallback;
  } catch {
    return fallback;
  }
}

export class OrchestratorApi {
  constructor(private readonly baseUrl: string) {}

  async orchestrate(payload: OrchestratePayload): Promise<OrchestrateResponse> {
    const response = await fetch(`${this.baseUrl}/orchestrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await extractError(response, "Orchestrator request failed"));
    return response.json() as Promise<OrchestrateResponse>;
  }

  async approve(payload: {
    thread_id: string;
    approved: boolean;
    user_id: string;
  }): Promise<{ status: string; response?: string }> {
    const response = await fetch(`${this.baseUrl}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await extractError(response, "Approval request failed"));
    return response.json();
  }

  async saveJiraSettings(settings: JiraSettings): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/settings/jira`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error(await extractError(response, "Failed to save Jira settings"));
    return response.json();
  }

  async saveCalendarSettings(settings: CalendarSettings): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/settings/calendar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error(await extractError(response, "Failed to save calendar settings"));
    return response.json();
  }

  async saveGoogleCalendarSettings(settings: GoogleCalendarSettings): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/settings/google-calendar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error(await extractError(response, "Failed to save Google Calendar settings"));
    return response.json();
  }

  async getIntegrationStatus(): Promise<IntegrationStatus> {
    const response = await fetch(`${this.baseUrl}/settings/status`);
    if (!response.ok) throw new Error(await extractError(response, "Failed to fetch integration status"));
    return response.json() as Promise<IntegrationStatus>;
  }

  async startTeamsAuth(): Promise<TeamsDeviceCodeResponse> {
    const response = await fetch(`${this.baseUrl}/auth/teams/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) throw new Error(await extractError(response, "Failed to start Teams auth"));
    return response.json() as Promise<TeamsDeviceCodeResponse>;
  }

  async pollTeamsAuth(deviceCode: string): Promise<TeamsAuthPollResponse> {
    const response = await fetch(`${this.baseUrl}/auth/teams/poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_code: deviceCode }),
    });
    if (!response.ok) throw new Error(await extractError(response, "Poll failed"));
    return response.json() as Promise<TeamsAuthPollResponse>;
  }

  async callTool(
    req: import("../types").DirectToolRequest,
  ): Promise<import("../types").DirectToolResponse> {
    const response = await fetch(`${this.baseUrl}/tool/call`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!response.ok) throw new Error(await extractError(response, "Tool call failed"));
    return response.json() as Promise<import("../types").DirectToolResponse>;
  }
}
