import type { ChatMessage, PendingApproval } from "../../types";

export class AgentModel {
  private messages: ChatMessage[] = [];
  private loading = false;
  private _pendingApproval: PendingApproval | null = null;
  private listeners: Array<() => void> = [];

  private _userId: string = (() => {
    let id = sessionStorage.getItem("tagent_user_id");
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem("tagent_user_id", id);
    }
    return id;
  })();

  private _threadId: string = (() => {
    let id = sessionStorage.getItem("tagent_thread_id");
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem("tagent_thread_id", id);
    }
    return id;
  })();

  get userId(): string {
    return this._userId;
  }

  get threadId(): string {
    return this._threadId;
  }

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private notify(): void {
    this.listeners.forEach((l) => l());
  }

  getMessages(): ChatMessage[] {
    return [...this.messages];
  }

  isLoading(): boolean {
    return this.loading;
  }

  getPendingApproval(): PendingApproval | null {
    return this._pendingApproval;
  }

  addMessage(message: ChatMessage): void {
    this.messages.push(message);
    this.notify();
  }

  setLoading(value: boolean): void {
    this.loading = value;
    this.notify();
  }

  setPendingApproval(approval: PendingApproval | null): void {
    this._pendingApproval = approval;
    this.notify();
  }

  resetConversation(): void {
    this.messages = [];
    this._pendingApproval = null;
    this._threadId = crypto.randomUUID();
    sessionStorage.setItem("tagent_thread_id", this._threadId);
    this.notify();
  }
}
