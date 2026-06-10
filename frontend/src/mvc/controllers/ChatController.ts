import type { AgentModel } from "../models/AgentModel";
import type { OrchestratorApi } from "../../services/api";
import type { ToolId, UserSuggestion } from "../../types";

export class ChatController {
  constructor(
    private readonly model: AgentModel,
    private readonly api: OrchestratorApi,
  ) {}

  async sendMessage(text: string): Promise<void> {
    if (!text.trim()) return;

    this.model.addMessage({ role: "user", content: text, timestamp: Date.now() });
    this.model.setLoading(true);
    this.model.setPendingApproval(null);

    try {
      const result = await this.api.orchestrate({
        user_id: this.model.userId,
        thread_id: this.model.threadId,
        message: text,
      });

      const content = result.response ?? result.tool_results.at(-1)?.output ?? "Done.";
      const stepResults = result.tool_results.length > 0 ? result.tool_results : undefined;

      this.model.addMessage({
        role: "assistant",
        content,
        timestamp: Date.now(),
        stepResults,
        brnValidation: result.brn_validation,
      });

      if (result.approval?.required) {
        this.model.setPendingApproval(result.approval);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      this.model.addMessage({
        role: "assistant",
        content: `Unable to reach the orchestrator service. ${msg}`,
        timestamp: Date.now(),
      });
    } finally {
      this.model.setLoading(false);
    }
  }

  async callTool(toolId: ToolId, query: string, displayLabel: string): Promise<void> {
    const userContent = `#${displayLabel}${query ? `: ${query}` : ""}`;
    this.model.addMessage({
      role: "user",
      content: userContent,
      timestamp: Date.now(),
      toolName: displayLabel,
    });
    this.model.setLoading(true);
    this.model.setPendingApproval(null);

    try {
      const result = await this.api.callTool({
        tool_name: toolId,
        query: query || undefined,
        user_id: this.model.userId,
      });
      this.model.addMessage({
        role: "assistant",
        content: result.response,
        timestamp: Date.now(),
        toolName: displayLabel,
        brnValidation: result.brn_validation,
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Tool call failed.";
      this.model.addMessage({
        role: "assistant",
        content: `Unable to run tool: ${msg}`,
        timestamp: Date.now(),
      });
    } finally {
      this.model.setLoading(false);
    }
  }

  async approveAction(approved: boolean): Promise<void> {
    this.model.addMessage({
      role: "user",
      content: approved ? "Approved" : "Rejected",
      timestamp: Date.now(),
    });
    this.model.setPendingApproval(null);
    this.model.setLoading(true);

    try {
      const result = await this.api.approve({
        thread_id: this.model.threadId,
        approved,
        user_id: this.model.userId,
      });
      const content =
        result.response ??
        (approved
          ? "Action approved and executed successfully."
          : "Action has been rejected.");
      this.model.addMessage({ role: "assistant", content, timestamp: Date.now() });
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Request failed.";
      this.model.addMessage({
        role: "assistant",
        content: `Approval request failed: ${msg}`,
        timestamp: Date.now(),
      });
    } finally {
      this.model.setLoading(false);
    }
  }

  newConversation(): void {
    this.model.resetConversation();
  }

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
