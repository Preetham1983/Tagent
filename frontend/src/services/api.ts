import type { OrchestrateResponse, JiraSettings, CalendarSettings, GoogleCalendarSettings, IntegrationStatus, TeamsDeviceCodeResponse, TeamsAuthPollResponse } from "../types";

type OrchestratePayload = {
  user_id: string;
  thread_id: string;
  message: string;
};

export class OrchestratorApi {
  constructor(private readonly baseUrl: string) {}

  async orchestrate(payload: OrchestratePayload): Promise<OrchestrateResponse> {
    const response = await fetch(`${this.baseUrl}/orchestrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("Orchestrator request failed");
    return response.json() as Promise<OrchestrateResponse>;
  }

  async saveJiraSettings(settings: JiraSettings): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/settings/jira`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error("Failed to save Jira settings");
    return response.json();
  }

  async saveCalendarSettings(settings: CalendarSettings): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/settings/calendar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error("Failed to save calendar settings");
    return response.json();
  }

  async saveGoogleCalendarSettings(settings: GoogleCalendarSettings): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/settings/google-calendar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error("Failed to save Google Calendar settings");
    return response.json();
  }

  async getIntegrationStatus(): Promise<IntegrationStatus> {
    const response = await fetch(`${this.baseUrl}/settings/status`);
    if (!response.ok) throw new Error("Failed to fetch integration status");
    return response.json() as Promise<IntegrationStatus>;
  }

  async startTeamsAuth(): Promise<TeamsDeviceCodeResponse> {
    const response = await fetch(`${this.baseUrl}/auth/teams/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to start Teams auth" }));
      throw new Error((err as { detail?: string }).detail ?? "Failed to start Teams auth");
    }
    return response.json() as Promise<TeamsDeviceCodeResponse>;
  }

  async pollTeamsAuth(deviceCode: string): Promise<TeamsAuthPollResponse> {
    const response = await fetch(`${this.baseUrl}/auth/teams/poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_code: deviceCode }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Poll failed" }));
      throw new Error((err as { detail?: string }).detail ?? "Poll failed");
    }
    return response.json() as Promise<TeamsAuthPollResponse>;
  }

  async callTool(req: import("../types").DirectToolRequest): Promise<import("../types").DirectToolResponse> {
    const response = await fetch(`${this.baseUrl}/tool/call`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Tool call failed" }));
      throw new Error((err as { detail?: string }).detail ?? "Tool call failed");
    }
    return response.json() as Promise<import("../types").DirectToolResponse>;
  }
}
