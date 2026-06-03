import type { AgentModel } from "../models/AgentModel";
import type { OrchestratorApi } from "../../services/api";
import type { ToolId, UserSuggestion } from "../../types";

export class ChatController {
  constructor(
    private readonly model: AgentModel,
    private readonly api: OrchestratorApi
  ) {}

  async sendMessage(text: string): Promise<void> {
    if (!text.trim()) return;

    this.model.addMessage({ role: "user", content: text });
    this.model.setLoading(true);

    try {
      const result = await this.api.orchestrate({
        user_id: this.model.userId,
        thread_id: crypto.randomUUID(),
        message: text,
      });

      const content = result.response ?? result.tool_results.at(-1)?.output ?? "Done.";
      this.model.addMessage({ role: "assistant", content });
    } catch (error) {
      this.model.addMessage({
        role: "assistant",
        content: "Failed to reach orchestrator service.",
      });
    } finally {
      this.model.setLoading(false);
    }
  }

  async callTool(toolId: ToolId, query: string, displayLabel: string): Promise<void> {
    const userContent = `#${displayLabel}${query ? `: ${query}` : ""}`;
    this.model.addMessage({ role: "user", content: userContent });
    this.model.setLoading(true);

    try {
      const result = await this.api.callTool({
        tool_name: toolId,
        query: query || undefined,
        user_id: this.model.userId,
      });
      this.model.addMessage({ role: "assistant", content: result.response });
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Tool call failed.";
      this.model.addMessage({ role: "assistant", content: `⚠ ${msg}` });
    } finally {
      this.model.setLoading(false);
    }
  }

  /** Search colleagues by partial name — used for autocomplete in the composer. */
  async searchUsers(name: string): Promise<UserSuggestion[]> {
    if (!name.trim()) return [];
    try {
      const result = await this.api.callTool({ tool_name: "search_user", query: name });
      const raw = result.raw as { status?: string; results?: UserSuggestion[] } | null;
      if (raw?.status === "ok" && Array.isArray(raw.results)) {
        return raw.results;
      }
    } catch {
      // Silently fail — autocomplete is non-critical
    }
    return [];
  }
}

