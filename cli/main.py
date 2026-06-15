#!/usr/bin/env python3
"""
Tagent CLI — unified command-line interface.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import textwrap
import uuid
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.live import Live
from rich.text import Text
from rich import box

from cli.constants import (
    HEALTH_URL,
    ORCHESTRATE_URL,
    PROJECT_ROOT,
    SETTINGS_URL,
    TOOLS_REGISTRY,
)
from cli.services import get_integration_status, get_service_status, start_services, stop_services
from cli.renderer import (
    console,
    full_banner,
    gradient_text,
    print_gradient_divider,
    render_command_table,
    render_options_panel,
    render_examples_panel,
    render_tip,
    render_thinking_animation,
    render_chat_welcome,
    render_user_message,
    render_response_panel,
    render_error,
    render_success,
    chat_prompt,
    NEON,
    GRADIENT_COLORS,
)


# ── Help Screen ────────────────────────────────────────────────────────────────

def print_custom_help() -> None:
    full_banner(animate=True)
    console.print(render_command_table())
    console.print(render_options_panel())
    console.print(render_examples_panel())
    render_tip()


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_start(args: argparse.Namespace) -> None:
    full_banner(animate=False)
    results = {}
    with console.status(
        Text.assemble(
            ("  ▶ ", f"bold {NEON['green']}"),
            ("Starting Tagent services via Docker Compose...", "bold white"),
            ("\n    (This may take a few minutes if building images)", "dim"),
        )
    ):
        results = start_services(verbose=args.verbose, stream_output=False)

    table = Table(show_header=False, box=None, padding=(0, 2))
    for name, status in results.items():
        ok = "started" in status or "already" in status
        dot = Text("●", style=f"bold {NEON['green']}" if ok else f"bold {NEON['red']}")
        table.add_row(dot, Text(name, style="bold white"), Text(status, style="dim"))

    console.print(Panel(
        table,
        title="[bold white] Service Startup [/bold white]",
        border_style=NEON["green"],
        expand=False,
        padding=(1, 1),
    ))

    info = Text()
    info.append("\n  Orchestrator API → ", style="dim")
    info.append("http://localhost:8001", style=f"bold {NEON['cyan']}")
    info.append("\n  Web UI           → ", style="dim")
    info.append("http://localhost:5173", style=f"bold {NEON['cyan']}")
    info.append("\n  Run ", style="dim")
    info.append("tagent ui", style=f"bold {NEON['purple']}")
    info.append(" for the interactive TUI\n", style="dim")
    console.print(info)


def cmd_stop(args: argparse.Namespace) -> None:
    full_banner(animate=False)
    results = {}
    with console.status(
        Text.assemble(
            ("  ⏹ ", f"bold {NEON['red']}"),
            ("Stopping Tagent services...", "bold white"),
        )
    ):
        results = stop_services()

    table = Table(show_header=False, box=None, padding=(0, 2))
    for name, status in results.items():
        ok = "stopped" in status
        dot = Text("●", style=f"bold {NEON['green']}" if ok else "dim")
        table.add_row(dot, Text(name, style="bold white"), Text(status, style="dim"))

    console.print(Panel(
        table,
        title="[bold white] Service Shutdown [/bold white]",
        border_style=NEON["red"],
        expand=False,
        padding=(1, 1),
    ))


def cmd_status(args: argparse.Namespace) -> None:
    full_banner(animate=False)

    # Services
    srv_table = Table(
        show_header=True,
        header_style=f"bold {NEON['cyan']}",
        box=box.SIMPLE_HEAVY,
        padding=(0, 2),
        expand=False,
    )
    srv_table.add_column("", width=3)
    srv_table.add_column("Service", min_width=15)
    srv_table.add_column("Port", min_width=6)
    srv_table.add_column("PID", min_width=8)

    statuses = get_service_status()
    for name, info in statuses.items():
        running = info.get("running") or info.get("healthy", False)
        dot = Text("●", style=f"bold {NEON['green']}" if running else f"bold {NEON['red']}")
        port = str(info.get("port", ""))
        pid_str = str(info.get("pid", "")) if info.get("pid") else "—"
        srv_table.add_row(
            dot,
            Text(name.title(), style="bold white"),
            Text(f":{port}" if port else "—", style=f"{NEON['cyan']}" if port else "dim"),
            Text(pid_str, style="dim"),
        )

    console.print(Panel(
        srv_table,
        title=f"[bold white] 📡 Service Status [/bold white]",
        border_style=NEON["cyan"],
        expand=False,
        padding=(1, 1),
    ))

    # Integrations
    int_table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    integrations = get_integration_status()
    if integrations:
        for name, info in integrations.items():
            ok = info.get("configured", False)
            dot = Text("●", style=f"bold {NEON['green']}" if ok else "dim")
            int_table.add_row(dot, Text(name.replace("_", " ").title(), style="bold white"))
    else:
        int_table.add_row(Text("Orchestrator offline — can't fetch integration status", style="dim"))

    console.print(Panel(
        int_table,
        title="[bold white] 🔗 Integrations [/bold white]",
        border_style="dim",
        expand=False,
        padding=(1, 1),
    ))


def cmd_tools(args: argparse.Namespace) -> None:
    full_banner(animate=False)
    total_tools = sum(len(cat["tools"]) for cat in TOOLS_REGISTRY.values())

    tree = Tree(
        Text.assemble(
            ("🔧 ", ""),
            ("Available Tools", f"bold {NEON['cyan']}"),
            (f"  ({total_tools} tools across {len(TOOLS_REGISTRY)} integrations)", "dim"),
        )
    )

    tool_colors = list(GRADIENT_COLORS)
    for idx, (key, cat) in enumerate(TOOLS_REGISTRY.items()):
        color = tool_colors[idx % len(tool_colors)]
        node = tree.add(
            Text.assemble(
                (f"{cat['icon']} ", ""),
                (cat["name"], f"bold {color}"),
                (f" — {cat['description']}", "dim"),
            )
        )
        for tool in cat["tools"]:
            node.add(Text(tool, style=f"{NEON['purple']}"))

    console.print(Panel(
        tree,
        border_style=NEON["cyan"],
        expand=False,
        padding=(1, 2),
    ))


def _run_chat_once(message: str, thread_id: str) -> None:
    result_container = {}
    def _do_request():
        try:
            r = httpx.post(
                ORCHESTRATE_URL,
                json={
                    "message": message,
                    "thread_id": thread_id,
                    "user_id": "cli-user",
                    "user_role": "authenticated_user",
                    "user_tier": "professional",
                },
                timeout=120,
            )
            result_container["response"] = r
        except Exception as e:
            result_container["error"] = e

    t = threading.Thread(target=_do_request)
    t.start()

    render_thinking_animation(t, result_container)

    if "error" in result_container:
        render_error(str(result_container["error"]))
        if isinstance(result_container["error"], httpx.ConnectError):
            console.print(f"    [dim]Cannot connect to orchestrator. Run [bold {NEON['cyan']}]tagent start[/bold {NEON['cyan']}] first.[/dim]")
        return

    r = result_container["response"]
    if r.status_code == 200:
        data = r.json()
        response = data.get("response", "No response")
        intent = data.get("intent", "unknown")
        render_response_panel(response, intent)
    else:
        render_error(f"HTTP {r.status_code}: {r.text[:200]}")


def cmd_chat(args: argparse.Namespace) -> None:
    """Send a message to the orchestrator (or enter interactive REPL)."""
    message = " ".join(args.message) if getattr(args, "message", None) else ""
    thread_id = str(uuid.uuid4())

    if message:
        render_user_message(message)
        _run_chat_once(message, thread_id)
        return

    # Interactive Mode
    full_banner(animate=True)
    render_chat_welcome()

    while True:
        try:
            msg = chat_prompt().strip()

            if not msg:
                continue
            if msg.lower() in ("exit", "quit"):
                console.print()
                render_success("Session ended. Goodbye!")
                console.print()
                break

            if msg.lower() == "/clear":
                console.clear()
                full_banner(animate=False)
                render_chat_welcome()
                continue

            if msg.lower() == "/help":
                print_custom_help()
                continue

            if msg.lower() == "/tools":
                try:
                    from InquirerPy import inquirer
                    from InquirerPy.base.control import Choice
                    from InquirerPy.utils import get_style

                    style = get_style({"questionmark": "#00ffff bold", "question": "", "input": "#ffffff"})
                    flat_tools = [Choice(value=t, name=f"{t}  [{cat['name']}]") for cat in TOOLS_REGISTRY.values() for t in cat["tools"]]

                    selected_tool = inquirer.fuzzy(
                        message="Select a tool:",
                        choices=flat_tools,
                        instruction="[Type to search, Up/Down to move, Enter to select, Esc to cancel]",
                        max_height="70%",
                        qmark="🔧",
                        style=style,
                    ).execute()

                    if selected_tool:
                        render_success(f"Selected: {selected_tool}")
                        console.print()
                        action = console.input(
                            Text.assemble(
                                (f"  What do you want to do with ", "dim"),
                                (selected_tool, f"bold {NEON['orange']}"),
                                ("? ❯ ", "dim"),
                            )
                        ).strip()

                        if action:
                            msg = f"Using ONLY the {selected_tool} tool, {action}"
                            console.print(f"    [dim]Prompting agent: {msg}[/dim]\n")
                        else:
                            continue
                    else:
                        console.print(f"    [dim {NEON['yellow']}]Tool selection cancelled.[/dim {NEON['yellow']}]\n")
                        continue
                except Exception as e:
                    render_error(f"Fuzzy search error: {e}")
                    cmd_tools(args)
                    continue

            render_user_message(msg)
            _run_chat_once(msg, thread_id)

        except (KeyboardInterrupt, EOFError):
            console.print()
            render_success("Session ended. Goodbye!")
            console.print()
            break


def cmd_agents(args: argparse.Namespace) -> None:
    full_banner(animate=False)

    # Pipeline visualization
    pipeline_nodes = [
        ("Classifier",  NEON["cyan"],   "Intent analysis & routing"),
        ("DACL Guard",  NEON["yellow"], "Business policy compliance"),
        ("Planner",     NEON["blue"],   "Step-by-step strategy"),
        ("Executor",    NEON["orange"], "MCP tool invocation"),
        ("Reviewer",    NEON["purple"], "Output synthesis"),
        ("Human Gate",  NEON["green"],  "HITL action approval"),
    ]

    # Build pipeline as connected nodes
    pipeline = Text()
    for idx, (name, color, desc) in enumerate(pipeline_nodes):
        pipeline.append("  ● ", style=f"bold {color}")
        pipeline.append(name, style=f"bold {color}")
        pipeline.append(f"  {desc}", style="dim")
        if idx < len(pipeline_nodes) - 1:
            pipeline.append(f"\n  │", style="dim")
            pipeline.append(f"\n  ▼", style=f"dim {pipeline_nodes[idx + 1][1]}")
            pipeline.append("\n")

    console.print(Panel(
        pipeline,
        title="[bold white] 🤖 LangGraph Agent Pipeline [/bold white]",
        subtitle=gradient_text(
            " classify → dacl → plan → execute → review → gate → end ",
            GRADIENT_COLORS,
            bold=False,
        ),
        border_style=NEON["cyan"],
        expand=False,
        padding=(1, 2),
    ))


def cmd_keys(args: argparse.Namespace) -> None:
    full_banner(animate=False)
    console.print(gradient_text("  🔑 Set API Keys", [NEON["yellow"], NEON["orange"]]))
    console.print()

    env_path = PROJECT_ROOT / "backend" / "services" / "orchestrator-service" / ".env"
    if not env_path.exists():
        render_error(f".env file not found at {env_path}")
        sys.exit(1)

    from InquirerPy import inquirer
    key_name = inquirer.text(message="Enter key name (e.g. OPENAI_API_KEY):", qmark="❯").execute().strip()
    if not key_name:
        sys.exit(0)

    key_value = inquirer.text(message=f"Enter value for {key_name}:", qmark="❯").execute().strip()

    lines = env_path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key_name}="):
            lines[i] = f"{key_name}={key_value}"
            found = True
            break

    if not found:
        lines.append(f"{key_name}={key_value}")

    env_path.write_text("\n".join(lines) + "\n")
    render_success(f"Saved {key_name} to .env")
    console.print()


def cmd_login(args: argparse.Namespace) -> None:
    full_banner(animate=False)
    console.print(gradient_text("  🌐 Microsoft Graph / Teams Re-authentication", [NEON["blue"], NEON["cyan"]]))
    console.print()

    script_path = PROJECT_ROOT / "trigger_login.py"
    if not script_path.exists():
        render_error("trigger_login.py not found in project root.")
        sys.exit(1)

    try:
        subprocess.run([sys.executable, str(script_path)], cwd=str(PROJECT_ROOT))
    except Exception as e:
        render_error(f"Failed to run login script: {e}")


def cmd_ui(args: argparse.Namespace) -> None:
    """Launch the interactive TUI."""
    from cli.tui import run_tui
    run_tui()


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tagent",
        description="Tagent — AI-powered personal work agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              tagent start              Start orchestrator + frontend
              tagent stop               Stop all services
              tagent status             Check service health
              tagent ui                 Launch interactive TUI dashboard
              tagent chat               Launch interactive REPL
              tagent chat "list tools"  Send a one-shot query
        """),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # start
    p_start = sub.add_parser("start", help="Start orchestrator + frontend services")
    p_start.add_argument("--verbose", "-v", action="store_true")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop all running services")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = sub.add_parser("status", help="Show service & integration status")
    p_status.set_defaults(func=cmd_status)

    # ui
    p_ui = sub.add_parser("ui", help="Launch the interactive TUI dashboard")
    p_ui.set_defaults(func=cmd_ui)

    # tools
    p_tools = sub.add_parser("tools", help="List all available MCP tools")
    p_tools.set_defaults(func=cmd_tools)

    # agents
    p_agents = sub.add_parser("agents", help="List active LangGraph agents")
    p_agents.set_defaults(func=cmd_agents)

    # keys
    p_keys = sub.add_parser("keys", help="Set API keys in .env")
    p_keys.set_defaults(func=cmd_keys)

    # login
    p_login = sub.add_parser("login", help="Re-authenticate Microsoft Graph / Teams")
    p_login.set_defaults(func=cmd_login)

    # chat
    p_chat = sub.add_parser("chat", help="Send a message to the orchestrator or enter interactive mode")
    p_chat.add_argument("message", nargs="*", help="Optional message to send. If omitted, enters interactive mode.")
    p_chat.set_defaults(func=cmd_chat)

    return parser


def main() -> None:
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help")):
        print_custom_help()
        sys.exit(0)

    parser = build_parser()
    args = parser.parse_args()

    if not getattr(args, "command", None):
        print_custom_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
