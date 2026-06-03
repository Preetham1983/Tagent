import { useEffect, useRef, useState } from "react";
import { ChatController } from "./mvc/controllers/ChatController";
import { AgentModel } from "./mvc/models/AgentModel";
import { ChatView } from "./mvc/views/ChatView";
import { Sidebar } from "./mvc/views/Sidebar";
import { SettingsModal } from "./mvc/views/SettingsModal";
import { OrchestratorApi } from "./services/api";
import type { IntegrationType, IntegrationStatus, JiraSettings, CalendarSettings, GoogleCalendarSettings, TeamsDeviceCodeResponse } from "./types";

export function App() {
  // In production (Vercel), use relative URLs so API calls go to the same domain.
  // Only fall back to localhost during local dev.
  const baseUrl =
    import.meta.env.VITE_ORCHESTRATOR_BASE_URL ??
    (window.location.hostname === "localhost" ? "http://localhost:8001" : "");

  const modelRef = useRef<AgentModel | null>(null);
  const controllerRef = useRef<ChatController | null>(null);
  const apiRef = useRef<OrchestratorApi | null>(null);

  if (!modelRef.current) {
    const model = new AgentModel();
    const api = new OrchestratorApi(baseUrl);
    apiRef.current = api;
    modelRef.current = model;
    controllerRef.current = new ChatController(model, api);
  }

  const [activeIntegration, setActiveIntegration] =
    useState<IntegrationType | null>(null);
  const [integrationStatus, setIntegrationStatus] =
    useState<IntegrationStatus | null>(null);

  useEffect(() => {
    apiRef.current!
      .getIntegrationStatus()
      .then(setIntegrationStatus)
      .catch(() => {}); // silently ignore if backend unavailable
  }, []);

  const handleSaveJira = async (settings: JiraSettings) => {
    await apiRef.current!.saveJiraSettings(settings);
    const status = await apiRef.current!.getIntegrationStatus();
    setIntegrationStatus(status);
    setActiveIntegration(null);
  };

  const handleSaveCalendar = async (settings: CalendarSettings) => {
    await apiRef.current!.saveCalendarSettings(settings);
    const status = await apiRef.current!.getIntegrationStatus();
    setIntegrationStatus(status);
  };

  const handleSaveGoogleCalendar = async (settings: GoogleCalendarSettings) => {
    await apiRef.current!.saveGoogleCalendarSettings(settings);
    const status = await apiRef.current!.getIntegrationStatus();
    setIntegrationStatus(status);
  };

  const handleStartTeamsAuth = async (): Promise<TeamsDeviceCodeResponse> => {
    return apiRef.current!.startTeamsAuth();
  };

  const handlePollTeamsAuth = async (deviceCode: string) => {
    const result = await apiRef.current!.pollTeamsAuth(deviceCode);
    if (result.status === "ok") {
      const status = await apiRef.current!.getIntegrationStatus();
      setIntegrationStatus(status);
    }
    return result;
  };

  return (
    <div className="app-shell">
      <Sidebar
        activeIntegration={activeIntegration}
        onSelectIntegration={setActiveIntegration}
        integrationStatus={integrationStatus}
      />
      <div className="main-content">
        <ChatView
          controller={controllerRef.current!}
          model={modelRef.current!}
        />
      </div>

      {activeIntegration && (
        <SettingsModal
          type={activeIntegration}
          integrationStatus={integrationStatus}
          onSaveJira={handleSaveJira}
          onSaveCalendar={handleSaveCalendar}
          onSaveGoogleCalendar={handleSaveGoogleCalendar}
          onStartTeamsAuth={handleStartTeamsAuth}
          onPollTeamsAuth={handlePollTeamsAuth}
          onClose={() => setActiveIntegration(null)}
        />
      )}
    </div>
  );
}

