"""
Tagent TUI — A premium terminal user interface for the Tagent AI agent.

Built with Textual for a rich, interactive terminal experience.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime

import httpx
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    RichLog,
    Rule,
    Static,
)

from cli.constants import (
    HEALTH_URL,
    ORCHESTRATE_URL,
    ORCHESTRATOR_URL,
    SETTINGS_URL,
    TAGENT_BANNER,
    TOOLS_REGISTRY,
)
from cli.services import get_integration_status, get_service_status, start_services, stop_services

# ── CSS for the TUI ────────────────────────────────────────────────────────────
TAGENT_CSS = """
Screen {
    background: $surface;
}

/* ── Sidebar ────────────────────────────────────────── */
#sidebar {
    width: 28;
    background: $panel;
    border-right: thick $primary-background-darken-2;
    padding: 1 0;
}

#sidebar-logo {
    text-align: center;
    color: $accent;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
}

#sidebar-version {
    text-align: center;
    color: $text-muted;
    margin-bottom: 1;
}

.nav-item {
    padding: 0 2;
    height: 3;
    content-align: left middle;
    color: $text;
}

.nav-item:hover {
    background: $primary-background-darken-1;
    color: $accent;
}

.nav-item.--selected {
    background: $accent 15%;
    color: $accent;
    text-style: bold;
    border-left: thick $accent;
}

#nav-list {
    margin: 0;
    padding: 0;
}

#nav-list > ListItem {
    padding: 0;
}

/* ── Status indicators ──────────────────────────────── */
#status-bar {
    dock: bottom;
    height: 3;
    background: $primary-background-darken-3;
    padding: 0 2;
    border-top: tall $primary-background-darken-2;
}

.status-dot-on {
    color: #00ff88;
    text-style: bold;
}

.status-dot-off {
    color: #ff4444;
    text-style: bold;
}

.status-dot-warn {
    color: #ffaa00;
    text-style: bold;
}

/* ── Main content ───────────────────────────────────── */
#main-content {
    padding: 1 2;
}

/* ── Dashboard ──────────────────────────────────────── */
#dashboard-header {
    height: auto;
    margin-bottom: 1;
}

#welcome-text {
    color: $text;
    padding: 0 0 1 0;
}

.stat-card {
    width: 1fr;
    height: 7;
    background: $panel;
    border: round $primary-background-darken-1;
    padding: 1 2;
    margin: 0 1;
}

.stat-card-title {
    color: $text-muted;
    text-style: italic;
}

.stat-card-value {
    color: $accent;
    text-style: bold;
    text-align: center;
}

#stat-cards {
    height: 9;
    margin-bottom: 1;
}

#service-status-panel {
    height: auto;
    background: $panel;
    border: round $primary-background-darken-1;
    padding: 1 2;
    margin-bottom: 1;
}

#integration-panel {
    height: auto;
    background: $panel;
    border: round $primary-background-darken-1;
    padding: 1 2;
}

/* ── Chat ───────────────────────────────────────────── */
#chat-container {
    height: 1fr;
}

#chat-log {
    height: 1fr;
    background: $panel;
    border: round $primary-background-darken-1;
    padding: 1;
    margin-bottom: 1;
}

#chat-input-bar {
    height: 3;
    margin-top: 0;
}

#chat-input {
    width: 1fr;
    margin-right: 1;
}

#send-btn {
    width: 12;
    background: $accent;
    color: $text;
    text-style: bold;
}

#send-btn:hover {
    background: $accent-darken-1;
}

/* ── Tools ──────────────────────────────────────────── */
#tools-container {
    height: 1fr;
}

.tool-category {
    background: $panel;
    border: round $primary-background-darken-1;
    padding: 1 2;
    margin-bottom: 1;
    height: auto;
}

.tool-category-title {
    color: $accent;
    text-style: bold;
    margin-bottom: 0;
}

.tool-category-desc {
    color: $text-muted;
}

.tool-name {
    color: $secondary;
    padding-left: 2;
}

/* ── Logs ───────────────────────────────────────────── */
#logs-panel {
    height: 1fr;
    background: $panel;
    border: round $primary-background-darken-1;
    padding: 1;
}

/* ── Panels ─────────────────────────────────────────── */

.panel-title {
    color: $accent;
    text-style: bold;
    margin-bottom: 1;
}

/* ── Page containers (hidden by default) ────────────── */
.page {
    display: none;
}

.page.--active {
    display: block;
}
"""

# ── Widgets ────────────────────────────────────────────────────────────────────

class StatusBar(Static):
    """Bottom status bar showing live service status."""

    orchestrator_up = reactive(False)
    frontend_up = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("⚡ Tagent", id="status-brand")
            yield Static("  │  ", classes="sep")
            yield Static("● Orchestrator: checking…", id="orch-status")
            yield Static("  │  ")
            yield Static("● Frontend: checking…", id="fe-status")
            yield Static("  │  ")
            yield Static("", id="clock")

    def update_status(self, orch: bool, fe: bool) -> None:
        self.orchestrator_up = orch
        self.frontend_up = fe
        try:
            orch_w = self.query_one("#orch-status", Static)
            fe_w = self.query_one("#fe-status", Static)
            orch_w.update(f"● Orchestrator: {'UP' if orch else 'DOWN'}")
            orch_w.set_class(orch, "status-dot-on")
            orch_w.set_class(not orch, "status-dot-off")
            fe_w.update(f"● Frontend: {'UP' if fe else 'DOWN'}")
            fe_w.set_class(fe, "status-dot-on")
            fe_w.set_class(not fe, "status-dot-off")
        except NoMatches:
            pass

    def update_clock(self) -> None:
        try:
            clock = self.query_one("#clock", Static)
            clock.update(datetime.now().strftime("🕐 %H:%M:%S"))
        except NoMatches:
            pass


class NavItem(Static):
    """A sidebar navigation item."""

    def __init__(self, label: str, page_id: str, icon: str = "", **kwargs):
        super().__init__(f" {icon}  {label}", **kwargs)
        self.page_id = page_id
        self.add_class("nav-item")

    def on_click(self) -> None:
        """Navigate when this item is clicked."""
        app = self.app
        if isinstance(app, TagentApp):
            app.action_switch_page(self.page_id)


# ── Pages ──────────────────────────────────────────────────────────────────────

class DashboardPage(Vertical):
    """Dashboard with stats, service status, and integration overview."""

    def compose(self) -> ComposeResult:
        yield Static("🏠  Dashboard", classes="panel-title")
        yield Static(
            "Welcome back! Your AI agent is ready to plan, execute, and automate.",
            id="welcome-text",
        )

        with Horizontal(id="stat-cards"):
            with Vertical(classes="stat-card"):
                yield Static("SERVICES", classes="stat-card-title")
                yield Static("—", id="stat-services", classes="stat-card-value")
            with Vertical(classes="stat-card"):
                yield Static("TOOLS", classes="stat-card-title")
                yield Static(
                    str(sum(len(t["tools"]) for t in TOOLS_REGISTRY.values())),
                    classes="stat-card-value",
                )
            with Vertical(classes="stat-card"):
                yield Static("INTEGRATIONS", classes="stat-card-title")
                yield Static("—", id="stat-integrations", classes="stat-card-value")
            with Vertical(classes="stat-card"):
                yield Static("UPTIME", classes="stat-card-title")
                yield Static("—", id="stat-uptime", classes="stat-card-value")

        with Vertical(id="service-status-panel"):
            yield Static("🔌  Service Status", classes="panel-title")
            yield Static("Loading…", id="service-detail")

        with Vertical(id="integration-panel"):
            yield Static("🔗  Integrations", classes="panel-title")
            yield Static("Loading…", id="integration-detail")


class ChatPage(Vertical):
    """Interactive chat with the Tagent orchestrator."""

    def compose(self) -> ComposeResult:
        yield Static("💬  Chat with Tagent", classes="panel-title")
        yield RichLog(highlight=True, markup=True, wrap=True, id="chat-log")
        with Horizontal(id="chat-input-bar"):
            yield Input(placeholder="Ask Tagent anything… (e.g. 'list my Jira issues')", id="chat-input")
            yield Button("Send ⚡", id="send-btn", variant="primary")


class ToolsPage(VerticalScroll):
    """Browse all available MCP tools."""

    def compose(self) -> ComposeResult:
        yield Static("🔧  Available Tools", classes="panel-title")
        yield Static(
            f"Tagent ships with {sum(len(t['tools']) for t in TOOLS_REGISTRY.values())} MCP tools across "
            f"{len(TOOLS_REGISTRY)} integrations.\n",
        )
        for key, cat in TOOLS_REGISTRY.items():
            with Vertical(classes="tool-category"):
                yield Static(f"{cat['icon']}  {cat['name']}", classes="tool-category-title")
                yield Static(f"   {cat['description']}", classes="tool-category-desc")
                for tool in cat["tools"]:
                    yield Static(f"   ├─ {tool}", classes="tool-name")


class LogsPage(Vertical):
    """Live system logs."""

    def compose(self) -> ComposeResult:
        yield Static("📋  System Logs", classes="panel-title")
        yield RichLog(highlight=True, markup=True, wrap=True, id="logs-panel")


class SettingsPage(VerticalScroll):
    """Settings and server controls."""

    def compose(self) -> ComposeResult:
        yield Static("⚙️  Settings & Controls", classes="panel-title")

        with Vertical(classes="tool-category"):
            yield Static("🚀  Server Management", classes="tool-category-title")
            with Horizontal():
                yield Button("▶  Start Services", id="btn-start", variant="success")
                yield Button("⏹  Stop Services", id="btn-stop", variant="error")
                yield Button("🔄  Restart", id="btn-restart", variant="warning")

        with Vertical(classes="tool-category"):
            yield Static("📡  Endpoints", classes="tool-category-title")
            yield Static(f"   Orchestrator API:  http://localhost:8001")
            yield Static(f"   Web UI:            http://localhost:5173")
            yield Static(f"   Teams Bot:         http://localhost:3978")

        with Vertical(classes="tool-category"):
            yield Static("📂  Architecture", classes="tool-category-title")
            yield Static("   classify → dacl_guard → plan → step_dacl_guard → execute → review → [human_gate] → end")
            yield Static("   LangGraph nodes with Human-in-the-Loop gating")


# ── Main TUI App ───────────────────────────────────────────────────────────────

class TagentApp(App):
    """The Tagent Terminal User Interface — your AI agent, in your terminal."""

    TITLE = "Tagent TUI"
    SUB_TITLE = "AI-powered personal work agent"
    CSS = TAGENT_CSS
    BINDINGS = [
        Binding("d", "switch_page('dashboard')", "Dashboard", show=True),
        Binding("c", "switch_page('chat')", "Chat", show=True),
        Binding("t", "switch_page('tools')", "Tools", show=True),
        Binding("l", "switch_page('logs')", "Logs", show=True),
        Binding("s", "switch_page('settings')", "Settings", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+s", "start_services", "Start Services"),
        Binding("ctrl+x", "stop_services", "Stop Services"),
    ]

    current_page = reactive("dashboard")
    thread_id = reactive("")
    _start_time: float = 0.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.thread_id = str(uuid.uuid4())
        self._start_time = time.time()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            # Sidebar
            with Vertical(id="sidebar"):
                yield Static("⚡ TAGENT", id="sidebar-logo")
                yield Static("v0.1.0", id="sidebar-version")
                yield Rule()
                yield NavItem("Dashboard", "dashboard", "🏠", id="nav-dashboard")
                yield NavItem("Chat", "chat", "💬", id="nav-chat")
                yield NavItem("Tools", "tools", "🔧", id="nav-tools")
                yield NavItem("Logs", "logs", "📋", id="nav-logs")
                yield NavItem("Settings", "settings", "⚙️", id="nav-settings")

            # Main content
            with VerticalScroll(id="main-content"):
                yield DashboardPage(id="page-dashboard", classes="page --active")
                yield ChatPage(id="page-chat", classes="page")
                yield ToolsPage(id="page-tools", classes="page")
                yield LogsPage(id="page-logs", classes="page")
                yield SettingsPage(id="page-settings", classes="page")

        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app first loads."""
        self._log("Tagent TUI initialized")
        self._log(f"Thread ID: {self.thread_id}")
        self.set_interval(2.0, self._poll_status)
        self.set_interval(1.0, self._update_clock)
        self._poll_status()

        # Welcome message in chat
        try:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write(
                "[bold cyan]⚡ Tagent AI Agent[/bold cyan]\n"
                "[dim]Your AI-powered personal work agent — plan, execute, and automate.[/dim]\n"
                "[dim]─────────────────────────────────────────────────────────────[/dim]\n"
                "[green]Ready.[/green] Type a message and press Enter or click Send.\n"
            )
        except NoMatches:
            pass

    # ── Navigation ─────────────────────────────────────────────────────────

    def action_switch_page(self, page_id: str) -> None:
        """Switch to a different page."""
        for page in self.query(".page"):
            page.remove_class("--active")
        try:
            self.query_one(f"#page-{page_id}").add_class("--active")
        except NoMatches:
            pass

        for nav in self.query(".nav-item"):
            nav.remove_class("--selected")
        try:
            self.query_one(f"#nav-{page_id}").add_class("--selected")
        except NoMatches:
            pass

        self.current_page = page_id

        # Focus chat input when switching to chat
        if page_id == "chat":
            try:
                self.query_one("#chat-input", Input).focus()
            except NoMatches:
                pass

    # Navigation is handled by NavItem.on_click()

    # ── Status polling ─────────────────────────────────────────────────────

    def _poll_status(self) -> None:
        self._refresh_status_async()

    @work(thread=True)
    def _refresh_status_async(self) -> None:
        status = get_service_status()
        orch_up = status.get("orchestrator", {}).get("healthy", False)
        fe_up = status.get("frontend", {}).get("running", False)

        self.call_from_thread(self._update_dashboard, status, orch_up, fe_up)

        # Integration status
        if orch_up:
            integrations = get_integration_status()
            if integrations:
                self.call_from_thread(self._update_integrations, integrations)

    def _update_dashboard(self, status: dict, orch_up: bool, fe_up: bool) -> None:
        # Status bar
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.update_status(orch_up, fe_up)
        except NoMatches:
            pass

        # Stat cards
        running_count = sum(1 for s in status.values() if s.get("running") or s.get("healthy"))
        try:
            self.query_one("#stat-services", Static).update(
                f"{'🟢' if running_count > 0 else '🔴'} {running_count}/2"
            )
        except NoMatches:
            pass

        # Uptime
        uptime = int(time.time() - self._start_time)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        try:
            self.query_one("#stat-uptime", Static).update(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        except NoMatches:
            pass

        # Service detail
        lines = []
        for name, info in status.items():
            running = info.get("running") or info.get("healthy", False)
            dot = "🟢" if running else "🔴"
            pid_str = f"  PID {info['pid']}" if info.get("pid") else ""
            port = info.get("port", "")
            lines.append(f"   {dot}  {name.title():16s}  :{port}{pid_str}")
        try:
            self.query_one("#service-detail", Static).update("\n".join(lines) or "   No services detected")
        except NoMatches:
            pass

    def _update_integrations(self, integrations: dict) -> None:
        lines = []
        configured_count = 0
        for name, info in integrations.items():
            ok = info.get("configured", False)
            if ok:
                configured_count += 1
            dot = "🟢" if ok else "⚫"
            lines.append(f"   {dot}  {name.replace('_', ' ').title()}")

        try:
            self.query_one("#stat-integrations", Static).update(
                f"{'🟢' if configured_count > 0 else '⚫'} {configured_count}/{len(integrations)}"
            )
        except NoMatches:
            pass

        try:
            self.query_one("#integration-detail", Static).update(
                "\n".join(lines) or "   Orchestrator offline"
            )
        except NoMatches:
            pass

    def _update_clock(self) -> None:
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.update_clock()
        except NoMatches:
            pass

    # ── Chat ───────────────────────────────────────────────────────────────

    @on(Input.Submitted, "#chat-input")
    def chat_submitted(self, event: Input.Submitted) -> None:
        self._send_message(event.value)

    @on(Button.Pressed, "#send-btn")
    def send_clicked(self, event: Button.Pressed) -> None:
        try:
            inp = self.query_one("#chat-input", Input)
            self._send_message(inp.value)
        except NoMatches:
            pass

    def _send_message(self, message: str) -> None:
        message = message.strip()
        if not message:
            return

        try:
            inp = self.query_one("#chat-input", Input)
            inp.value = ""
            inp.focus()
        except NoMatches:
            pass

        try:
            chat_log = self.query_one("#chat-log", RichLog)
            ts = datetime.now().strftime("%H:%M")
            chat_log.write(f"\n[bold white]You[/bold white] [dim]{ts}[/dim]")
            chat_log.write(f"  {message}\n")
            chat_log.write("[dim italic]⏳ Thinking…[/dim italic]")
        except NoMatches:
            pass

        self._log(f"→ Sending: {message[:80]}…")
        self._call_orchestrator(message)

    @work(thread=True)
    def _call_orchestrator(self, message: str) -> None:
        try:
            r = httpx.post(
                ORCHESTRATE_URL,
                json={
                    "message": message,
                    "thread_id": self.thread_id,
                    "user_id": "tui-user",
                    "user_role": "authenticated_user",
                    "user_tier": "professional",
                },
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                response = data.get("response", "No response")
                intent = data.get("intent", "unknown")
                brn = data.get("brn_validation", {})
                approval = data.get("approval", {})

                self.call_from_thread(self._display_response, response, intent, brn, approval)
                self.call_from_thread(self._log, f"← Response received (intent={intent})")
            else:
                self.call_from_thread(
                    self._display_error,
                    f"API returned {r.status_code}: {r.text[:200]}"
                )
        except httpx.ConnectError:
            self.call_from_thread(
                self._display_error,
                "Cannot connect to orchestrator. Run `tagent start` first."
            )
        except Exception as exc:
            self.call_from_thread(self._display_error, str(exc)[:300])

    def _display_response(self, response: str, intent: str, brn: dict, approval: dict) -> None:
        try:
            chat_log = self.query_one("#chat-log", RichLog)
            ts = datetime.now().strftime("%H:%M")
            chat_log.write("")  # clear "Thinking..."
            chat_log.write(f"[bold cyan]Tagent[/bold cyan] [dim]{ts}[/dim]  [dim italic]intent={intent}[/dim italic]")

            # BRN badge
            if brn and brn.get("enabled"):
                ic = brn.get("intent_check", {})
                if ic.get("passed"):
                    chat_log.write(f"  [green]✓ BRN Policy: {ic.get('policy_name', '—')}[/green]")
                else:
                    chat_log.write(f"  [red]✗ BRN Blocked: {ic.get('policy_name', '—')}[/red]")

            # Approval badge
            if approval and approval.get("required"):
                chat_log.write(f"  [yellow]⚠ Approval required: {approval.get('description', '—')}[/yellow]")

            # Response text
            for line in response.split("\n"):
                chat_log.write(f"  {line}")
            chat_log.write("")
        except NoMatches:
            pass

    def _display_error(self, error: str) -> None:
        try:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write(f"\n[bold red]Error[/bold red]  {error}\n")
        except NoMatches:
            pass

    # ── Service controls ───────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-start")
    def btn_start(self) -> None:
        self.action_start_services()

    @on(Button.Pressed, "#btn-stop")
    def btn_stop(self) -> None:
        self.action_stop_services()

    @on(Button.Pressed, "#btn-restart")
    def btn_restart(self) -> None:
        self.action_stop_services()
        self.set_timer(2.0, lambda: self.action_start_services())

    def action_start_services(self) -> None:
        self._log("Starting services…")
        self._start_services_async()

    @work(thread=True)
    def _start_services_async(self) -> None:
        results = start_services()
        for name, status in results.items():
            self.call_from_thread(self._log, f"  {name}: {status}")
        self.call_from_thread(self._log, "Service start complete")
        self.call_from_thread(self.notify, "Services started!", severity="information")

    def action_stop_services(self) -> None:
        self._log("Stopping services…")
        self._stop_services_async()

    @work(thread=True)
    def _stop_services_async(self) -> None:
        results = stop_services()
        for name, status in results.items():
            self.call_from_thread(self._log, f"  {name}: {status}")
        self.call_from_thread(self._log, "Service stop complete")
        self.call_from_thread(self.notify, "Services stopped.", severity="warning")

    # ── Logging ────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            logs = self.query_one("#logs-panel", RichLog)
            logs.write(f"[dim]{ts}[/dim]  {msg}")
        except NoMatches:
            pass


# ── Entry point ────────────────────────────────────────────────────────────────

def run_tui() -> None:
    """Launch the Tagent TUI."""
    app = TagentApp()
    app.run()
