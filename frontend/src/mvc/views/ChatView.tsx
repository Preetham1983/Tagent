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
  "Summarise today's standups",
  "Schedule a team meeting",
  "What's on my calendar today?",
];

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
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => model.subscribe(() => setTick((t) => t + 1)), [model]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); });

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [input]);

  const messages = model.getMessages();
  const loading = model.isLoading();

  /** Extract the @mention query from the input, if any. Returns null if no active @mention. */
  const extractMentionQuery = (text: string): string | null => {
    const atIdx = text.lastIndexOf("@");
    if (atIdx === -1) return null;
    const after = text.slice(atIdx + 1);
    // If the text after @ contains a dot + domain, it's a typed email — don't search
    if (/\S+\.\S+/.test(after)) return null;
    // Must be at start of input or preceded by a space
    if (atIdx > 0 && text[atIdx - 1] !== " ") return null;
    return after.trimEnd();
  };

  const handleInputChange = (value: string) => {
    setInput(value);

    if (selectedTool) {
      setShowPalette(false);

      // Colleague autocomplete for DM and meeting tools
      const isRecipientTool =
        selectedTool.id === "send_direct_message" ||
        selectedTool.id === "schedule_meeting";
      if (isRecipientTool) {
        // Check for @mention first
        const mentionQuery = extractMentionQuery(value);
        if (mentionQuery !== null && mentionQuery.length >= 2) {
          if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
          searchDebounceRef.current = setTimeout(() => {
            void controller.searchUsers(mentionQuery).then(setUserSuggestions);
          }, 350);
        } else {
          // Fallback: plain name typing (no @, no email, no dash separator yet)
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

    // ── @mention autocomplete in free-text mode ──────────────────────
    const mentionQuery = extractMentionQuery(value);
    if (mentionQuery !== null && mentionQuery.length >= 2) {
      setShowPalette(false);
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
      searchDebounceRef.current = setTimeout(() => {
        void controller.searchUsers(mentionQuery).then(setUserSuggestions);
      }, 350);
      return;
    } else if (mentionQuery !== null) {
      // Typing @ but less than 2 chars — clear suggestions, don't show palette
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
      setUserSuggestions([]);
      return;
    } else {
      setUserSuggestions([]);
    }

    // ── # command palette ────────────────────────────────────────────
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
      // In tool mode: replace the whole input with "email - " so user can type the message
      const mentionQuery = extractMentionQuery(input);
      if (mentionQuery !== null) {
        // Replace @query with the email
        const atIdx = input.lastIndexOf("@");
        const before = input.slice(0, atIdx);
        setInput(`${before}${suggestion.email} - `);
      } else {
        setInput(`${suggestion.email} - `);
      }
    } else {
      // In free-text mode: replace @query with the display name + email
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
        <div className="chat-topbar-icon">⚡</div>
        <div>
          <div className="chat-topbar-title">Tagent</div>
          <div className="chat-topbar-subtitle">Enterprise AI Assistant</div>
        </div>
        <div className="chat-topbar-actions">
          <button
            className="btn-icon"
            title="New conversation"
            onClick={() => window.location.reload()}
          >
            ↺
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-icon">⚡</div>
            <div className="welcome-title">How can I help you today?</div>
            <div className="welcome-subtitle">
              Ask anything, or type{" "}
              <code className="inline-code">#</code> to pick a tool and
              call Jira, Calendar, or Teams directly.
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
              <div className="bubble">
                {msg.role === "assistant" ? (
                  <MarkdownMessage content={msg.content} />
                ) : (
                  msg.content.split("\n").map((line, j, arr) => (
                    <span key={j}>
                      {line}
                      {j < arr.length - 1 && <br />}
                    </span>
                  ))
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="msg-row assistant">
            <div className="msg-avatar">T</div>
            <div className="bubble thinking">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
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
                onMouseDown={(e) => { e.preventDefault(); handleSuggestionSelect(u); }}
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
            # to pick a tool
          </span>
        </p>
      </div>
    </div>
  );
}

