import type { ChatMessage } from "../../types";

export class AgentModel {
  private messages: ChatMessage[] = [];
  private loading = false;
  private listeners: Array<() => void> = [];

  // Stable per-browser-session user identity
  readonly userId: string = sessionStorage.getItem("tagent_user_id") ?? (() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem("tagent_user_id", id);
    return id;
  })();

  /** Subscribe to any model change. Returns an unsubscribe function. */
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

  addMessage(message: ChatMessage): void {
    this.messages.push(message);
    this.notify();
  }

  setLoading(value: boolean): void {
    this.loading = value;
    this.notify();
  }
}
