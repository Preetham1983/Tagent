import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ChatController } from "../controllers/ChatController";
import type { AgentModel } from "../models/AgentModel";
import type { CommandTool, UserSuggestion } from "../../types";
import { CommandPalette } from "./CommandPalette";
import { MarkdownMessage } from "./MarkdownMessage";

const QUICK_PROMPTS = [
  "What's on my calendar today?",
  "Show open Jira issues",
  "Generate my daily standup",
];

const FEATURE_CARDS = [
  {
    icon: "🔷",
    title: "Jira",
    desc: "Issues, projects & tickets",
    prompt: "List my open Jira issues",
    color: "#0052CC",
  },
  {
    icon: "🐙",
    title: "GitHub",
    desc: "Repos, PRs & issues",
    prompt: "List open GitHub pull requests",
    color: "#24292F",
  },
  {
    icon: "💬",
    title: "Teams",
    desc: "Messages & meetings",
    prompt: "Show my recent Teams chats",
    color: "#5059C9",
  },
  {
    icon: "📅",
    title: "Calendar",
    desc: "Schedule & availability",
    prompt: "What's on my calendar today?",
    color: "#0078D4",
  },
  {
    icon: "📝",
    title: "Notion",
    desc: "Pages & databases",
    prompt: "Search my Notion workspace",
    color: "#374151",
  },
  {
    icon: "⚡",
    title: "Automation",
    desc: "Smart cross-tool workflows",
    prompt: "Generate my daily standup",
    color: "#7C3AED",
  },
];

const PROCESSING_LABELS = [
  "Analyzing your request…",
  "Calling tools…",
  "Processing results…",
  "Generating response…",
];

function formatTime(ts: number): string {
  const now = Date.now();
  const diff = now - ts;
  if (diff < 60_000) return "just now";

  const d = new Date(ts);
  const h = d.getHours();
  const m = d.getMinutes().toString().padStart(2, "0");
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  const timeStr = `${h12}:${m} ${ampm}`;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const msgDay = new Date(ts);
  msgDay.setHours(0, 0, 0, 0);
  const dayDiff = Math.round((today.getTime() - msgDay.getTime()) / 86_400_000);

  if (dayDiff === 0) return timeStr;
  if (dayDiff === 1) return `Yesterday ${timeStr}`;
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })} · ${timeStr}`;
}

type Props = {
  controller: ChatController;
  model: AgentModel;
};

export function ChatView({ controller, model }: Props) {
  const [input, setInput] = useState("");
  const [, setTick] = useState(0);
  const [selectedTool, setSelectedTool] = useState<CommandTool | null>(null);
  const [showPalette, setShowPalette] = useState(false);
  const [paletteFilter, setPaletteFilter] = useState("");
  const [userSuggestions, setUserSuggestions] = useState<UserSuggestion[]>([]);
  const [processingLabelIdx, setProcessingLabelIdx] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const processingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => model.subscribe(() => setTick((t) => t + 1)), [model]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [input]);

  // Cycle processing labels while loading
  useEffect(() => {
    if (model.isLoading()) {
      processingTimerRef.current = setInterval(() => {
        setProcessingLabelIdx((i) => (i + 1) % PROCESSING_LABELS.length);
      }, 2200);
    } else {
      if (processingTimerRef.current) {
        clearInterval(processingTimerRef.current);
        processingTimerRef.current = null;
      }
      setProcessingLabelIdx(0);
    }
    return () => {
      if (processingTimerRef.current) clearInterval(processingTimerRef.current);
    };
  }, [model.isLoading()]);

  const messages = model.getMessages();
  const loading = model.isLoading();
  const pendingApproval = model.getPendingApproval();

  const extractMentionQuery = (text: string): string | null => {
    const atIdx = text.lastIndexOf("@");
    if (atIdx === -1) return null;
    const after = text.slice(atIdx + 1);
    if (/\S+\.\S+/.test(after)) return null;
    if (atIdx > 0 && text[atIdx - 1] !== " ") return null;
    return after.trimEnd();
  };

  const handleInputChange = (value: string) => {
    setInput(value);

    if (selectedTool) {
      setShowPalette(false);

      const isRecipientTool =
        selectedTool.id === "send_direct_message" ||
        selectedTool.id === "schedule_meeting";
      if (isRecipientTool) {
        const mentionQuery = extractMentionQuery(value);
        if (mentionQuery !== null && mentionQuery.length >= 2) {
          if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
          searchDebounceRef.current = setTimeout(() => {
            void controller.searchUsers(mentionQuery).then(setUserSuggestions);
          }, 350);
        } else {
          const hasFullEmail = /\S+@\S+\.\S+/.test(value);
          const hasDash = value.includes(" - ");
          if (!hasFullEmail && !hasDash && value.trim().length >= 2 && !value.includes("@")) {
            if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
            searchDebounceRef.current = setTimeout(() => {
              void controller.searchUsers(value.trim()).then(setUserSuggestions);
            }, 350);
          } else {
            if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
            setUserSuggestions([]);
          }
        }
      }
      return;
    }

    const mentionQuery = extractMentionQuery(value);
    if (mentionQuery !== null && mentionQuery.length >= 2) {
      setShowPalette(false);
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
      searchDebounceRef.current = setTimeout(() => {
        void controller.searchUsers(mentionQuery).then(setUserSuggestions);
      }, 350);
      return;
    } else if (mentionQuery !== null) {
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
      setUserSuggestions([]);
      return;
    } else {
      setUserSuggestions([]);
    }

    const hashIdx = value.lastIndexOf("#");
    if (hashIdx !== -1) {
      const after = value.slice(hashIdx + 1);
      if (!after.includes(" ") || after.trim() === "") {
        setShowPalette(true);
        setPaletteFilter(after.trim());
        return;
      }
    }
    setShowPalette(false);
  };

  const handleSuggestionSelect = (suggestion: UserSuggestion) => {
    if (selectedTool) {
      const mentionQuery = extractMentionQuery(input);
      if (mentionQuery !== null) {
        const atIdx = input.lastIndexOf("@");
        const before = input.slice(0, atIdx);
        setInput(`${before}${suggestion.email} - `);
      } else {
        setInput(`${suggestion.email} - `);
      }
    } else {
      const atIdx = input.lastIndexOf("@");
      const before = input.slice(0, atIdx);
      setInput(`${before}${suggestion.name} (${suggestion.email}) `);
    }
    setUserSuggestions([]);
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const handleToolSelect = (tool: CommandTool) => {
    setSelectedTool(tool);
    setShowPalette(false);
    setUserSuggestions([]);
    setInput("");
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const clearTool = () => {
    setSelectedTool(null);
    setUserSuggestions([]);
    setInput("");
    textareaRef.current?.focus();
  };

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (loading) return;

    if (selectedTool) {
      const query = input.trim();
      const label = selectedTool.label;
      setSelectedTool(null);
      setInput("");
      await controller.callTool(selectedTool.id, query, label);
    } else {
      const text = input.trim();
      if (!text) return;
      setInput("");
      await controller.sendMessage(text);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Escape") {
      setShowPalette(false);
      clearTool();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  };

  const canSend = !loading && (selectedTool !== null || input.trim().length > 0);

  const isRecipientPlaceholder =
    selectedTool?.id === "send_direct_message" || selectedTool?.id === "schedule_meeting";
  const placeholder = selectedTool
    ? isRecipientPlaceholder
      ? "Type @name to find a colleague, or paste email - message"
      : selectedTool.placeholderQuery || "Press Enter to run, or type a filter…"
    : "Ask Tagent anything · # pick a tool · @ find a colleague";

  return (
    <div className="chat-layout">
      {/* Top bar */}
      <div className="chat-topbar">
        <div className="chat-topbar-icon">T</div>
        <div>
          <div className="chat-topbar-title">Tagent</div>
          <div className="chat-topbar-subtitle">Enterprise AI Orchestrator</div>
        </div>
        <div className="chat-topbar-actions">
          <button
            className="btn-icon"
            title="New conversation"
            onClick={() => controller.newConversation()}
          >
            ↺
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-logo">T</div>
            <div className="welcome-title">How can I help you today?</div>
            <div className="welcome-subtitle">
              Ask anything in natural language, or pick a tool to call Jira,
              Teams, GitHub, Calendar, and Notion directly.
            </div>

            <div className="feature-grid">
              {FEATURE_CARDS.map((card) => (
                <button
                  key={card.title}
                  className="feature-card"
                  onClick={() => void controller.sendMessage(card.prompt)}
                >
                  <div className="feature-card-header">
                    <span className="feature-card-icon">{card.icon}</span>
                    <span className="feature-card-title">{card.title}</span>
                  </div>
                  <div className="feature-card-desc">{card.desc}</div>
                </button>
              ))}
            </div>

            <div className="welcome-chips">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p}
                  className="chip"
                  onClick={() => void controller.sendMessage(p)}
                >
                  {p}
                </button>
              ))}
              <button
                className="chip chip-tool"
                onClick={() => {
                  setInput("#");
                  setShowPalette(true);
                  setPaletteFilter("");
                  setTimeout(() => textareaRef.current?.focus(), 50);
                }}
              >
                # Pick a tool
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`msg-row ${msg.role}`}>
              <div className="msg-avatar">
                {msg.role === "user" ? "U" : "T"}
              </div>

              <div className="msg-bubble-group">
                <div className="bubble">
                  {msg.role === "user" ? (
                    <>
                      {msg.toolName && (
                        <div className="tool-invocation-label">
                          <span>#</span>
                          <span>{msg.toolName}</span>
                        </div>
                      )}
                      {/* Strip "#Tool: " prefix from content if toolName is shown */}
                      {msg.toolName
                        ? msg.content
                            .replace(/^#[^:]+:\s*/, "")
                            .split("\n")
                            .map((line, j, arr) => (
                              <span key={j}>
                                {line}
                                {j < arr.length - 1 && <br />}
                              </span>
                            ))
                        : msg.content.split("\n").map((line, j, arr) => (
                            <span key={j}>
                              {line}
                              {j < arr.length - 1 && <br />}
                            </span>
                          ))}
                    </>
                  ) : (
                    <>
                      {msg.toolName && (
                        <div className="tool-source-badge">
                          <span>⚡</span>
                          <span>via {msg.toolName}</span>
                        </div>
                      )}
                      <MarkdownMessage content={msg.content} />
                    </>
                  )}
                </div>

                {/* Agent steps accordion */}
                {msg.role === "assistant" && msg.stepResults && msg.stepResults.length > 0 && (
                  <details className="agent-steps">
                    <summary className="agent-steps-summary">
                      <span>⚡</span>
                      <span>Agent steps</span>
                      <span className="agent-steps-count">{msg.stepResults.length}</span>
                    </summary>
                    <div className="agent-steps-list">
                      {msg.stepResults.map((step, j) => (
                        <div key={j} className="agent-step">
                          <div
                            className={`agent-step-status ${step.status === "success" ? "success" : "error"}`}
                          >
                            {step.status === "success" ? "✓" : "✗"}
                          </div>
                          <div className="agent-step-body">
                            <div className="agent-step-name">{step.step}</div>
                            <div className="agent-step-output">
                              {step.output.length > 140
                                ? step.output.slice(0, 140) + "…"
                                : step.output}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {/* BRN Validation Badge */}
                {msg.role === "assistant" && msg.brnValidation?.enabled && (
                  <div className={`brn-validation-badge ${msg.brnValidation.intent_check?.passed ? 'brn-passed' : 'brn-blocked'}`}>
                    <span className="brn-badge-icon">
                      {msg.brnValidation.intent_check?.passed ? "✓" : "🚫"}
                    </span>
                    <span className="brn-badge-text">
                      {msg.brnValidation.intent_check?.passed 
                        ? "BRN Passed" 
                        : "BRN Blocked"}
                    </span>
                    {msg.brnValidation.intent_check?.policy_name && (
                      <span className="brn-badge-policy">
                        {msg.brnValidation.intent_check.policy_name}
                      </span>
                    )}
                  </div>
                )}

                <div className="msg-meta">{formatTime(msg.timestamp)}</div>
              </div>
            </div>
          ))
        )}

        {/* Pending approval card */}
        {pendingApproval?.required && !loading && (
          <div className="msg-row assistant">
            <div className="msg-avatar">T</div>
            <div className="msg-bubble-group" style={{ maxWidth: "72%" }}>
              <div className="approval-card">
                <div className="approval-card-header">
                  <span className="approval-card-icon">⚠️</span>
                  <div>
                    <div className="approval-card-title">Action Requires Approval</div>
                    {pendingApproval.level && (
                      <div className="approval-card-level">
                        Approval level: {pendingApproval.level}
                      </div>
                    )}
                  </div>
                </div>
                {pendingApproval.description && (
                  <div className="approval-card-description">
                    {pendingApproval.description}
                  </div>
                )}
                <div className="approval-card-actions">
                  <button
                    className="btn-approve"
                    onClick={() => void controller.approveAction(true)}
                  >
                    ✓ Approve
                  </button>
                  <button
                    className="btn-reject"
                    onClick={() => void controller.approveAction(false)}
                  >
                    ✗ Reject
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="msg-row assistant">
            <div className="msg-avatar">T</div>
            <div className="msg-bubble-group">
              <div className="processing-bubble">
                <div className="processing-dots">
                  <span className="processing-dot" />
                  <span className="processing-dot" />
                  <span className="processing-dot" />
                </div>
                <span className="processing-label">
                  {PROCESSING_LABELS[processingLabelIdx]}
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="composer-wrapper">
        {showPalette && (
          <CommandPalette
            filter={paletteFilter}
            onSelect={handleToolSelect}
            onClose={() => setShowPalette(false)}
          />
        )}

        {userSuggestions.length > 0 && (
          <div className="user-suggestions">
            <div className="user-suggestions-header">
              <span className="user-suggestions-hint">👥 Teams colleagues</span>
            </div>
            {userSuggestions.map((u) => (
              <div
                key={u.email}
                className="user-suggestion-item"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSuggestionSelect(u);
                }}
                role="option"
                tabIndex={-1}
              >
                <span className="user-suggestion-avatar">{u.name?.[0] ?? "?"}</span>
                <div className="user-suggestion-body">
                  <div className="user-suggestion-name">{u.name}</div>
                  <div className="user-suggestion-email">
                    {u.email}
                    {u.job_title && u.job_title !== "N/A" && (
                      <span className="user-suggestion-title"> · {u.job_title}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={submit}>
          <div className={`composer-box${selectedTool ? " tool-active" : ""}`}>
            {selectedTool && (
              <div className="tool-tag">
                <span className="tool-tag-icon">{selectedTool.icon}</span>
                <span className="tool-tag-label">{selectedTool.label}</span>
                <button
                  type="button"
                  className="tool-tag-remove"
                  onClick={clearTool}
                  title="Remove tool"
                >
                  ✕
                </button>
              </div>
            )}

            <textarea
              ref={textareaRef}
              className="composer-input"
              value={input}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={loading}
              autoFocus
              rows={1}
            />
            <button
              type="submit"
              className="composer-send"
              disabled={!canSend}
              title="Send (Enter)"
            >
              ➤
            </button>
          </div>
        </form>
        <p className="composer-hint">
          Enter to send · Shift+Enter for new line ·{" "}
          <span
            className="composer-hint-link"
            onClick={() => {
              setInput("#");
              setShowPalette(true);
              setPaletteFilter("");
              textareaRef.current?.focus();
            }}
          >
            # pick a tool
          </span>
        </p>
      </div>
    </div>
  );
}
