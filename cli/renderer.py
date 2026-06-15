"""
Tagent CLI — Premium visual rendering engine.

Gradient text, animated banners, custom spinners, and beautiful formatting.
"""

from __future__ import annotations

import itertools
import math
import platform
import shutil
import sys
import time
from datetime import datetime

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.align import Align
from rich.live import Live
from rich import box

console = Console()

# ── Version ────────────────────────────────────────────────────────────────────
VERSION = "0.1.0"

# ── Color Palettes ─────────────────────────────────────────────────────────────
# Cyan → Blue → Purple gradient
GRADIENT_COLORS = [
    "#00ffff", "#00e5ff", "#00ccff", "#00b3ff", "#0099ff",
    "#0080ff", "#0066ff", "#1a4dff", "#3333ff", "#4d1aff",
    "#6600ff", "#7f00ff", "#9933ff", "#b366ff", "#cc99ff",
]

# Warm accent gradient (for highlights)
ACCENT_COLORS = [
    "#ff6b6b", "#ff8e72", "#ffb07c", "#ffd093", "#ffe0b2",
]

# Neon glow palette
NEON = {
    "cyan": "#00ffff",
    "blue": "#4d94ff",
    "purple": "#b366ff",
    "pink": "#ff66b2",
    "green": "#66ff66",
    "yellow": "#ffff66",
    "orange": "#ff9933",
    "red": "#ff4444",
}

# ── Banner Lines ───────────────────────────────────────────────────────────────
BANNER_LINES = [
    "████████╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗",
    "╚══██╔══╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝",
    "   ██║   ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ",
    "   ██║   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ",
    "   ██║   ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ",
    "   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ",
]

# ── Custom Spinner Frames ──────────────────────────────────────────────────────
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

WAVE_FRAMES = [
    "░▒▓██▓▒░",
    "▒▓██▓▒░░",
    "▓██▓▒░░▒",
    "██▓▒░░▒▓",
    "█▓▒░░▒▓█",
    "▓▒░░▒▓██",
    "▒░░▒▓██▓",
    "░░▒▓██▓▒",
]

PULSE_CHARS = "⣾⣽⣻⢿⡿⣟⣯⣷"


# ── Gradient Helpers ───────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _lerp_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return _rgb_to_hex(r, g, b)


def gradient_text(text: str, colors: list[str] | None = None, bold: bool = True) -> Text:
    """Render text with a smooth multi-stop gradient."""
    if colors is None:
        colors = GRADIENT_COLORS
    if len(text) == 0:
        return Text("")

    rich_text = Text()
    n = len(text)
    num_stops = len(colors)

    for i, char in enumerate(text):
        t = i / max(n - 1, 1)
        seg = t * (num_stops - 1)
        idx = int(seg)
        frac = seg - idx
        if idx >= num_stops - 1:
            idx = num_stops - 2
            frac = 1.0
        color = _lerp_color(colors[idx], colors[idx + 1], frac)
        style = f"bold {color}" if bold else color
        rich_text.append(char, style=style)

    return rich_text


def gradient_banner() -> Text:
    """Render the TAGENT banner with per-row gradient shifting."""
    combined = Text()
    num_lines = len(BANNER_LINES)
    for row_idx, line in enumerate(BANNER_LINES):
        # Shift the gradient palette per row for a diagonal effect
        shift = row_idx * 2
        shifted_colors = GRADIENT_COLORS[shift:] + GRADIENT_COLORS[:shift]
        combined.append_text(gradient_text(line, shifted_colors))
        if row_idx < num_lines - 1:
            combined.append("\n")
    return combined


# ── Animated Banner ────────────────────────────────────────────────────────────

def animate_banner(speed: float = 0.015) -> None:
    """Type-on animation for the banner, line by line with gradient."""
    console.print()
    term_width = shutil.get_terminal_size().columns
    banner_width = max(len(line) for line in BANNER_LINES)
    pad = max((term_width - banner_width) // 2, 0)

    for row_idx, line in enumerate(BANNER_LINES):
        shift = row_idx * 2
        shifted_colors = GRADIENT_COLORS[shift:] + GRADIENT_COLORS[:shift]
        rendered = Text(" " * pad)
        for i, char in enumerate(line):
            t = i / max(len(line) - 1, 1)
            seg = t * (len(shifted_colors) - 1)
            idx = int(seg)
            frac = seg - idx
            if idx >= len(shifted_colors) - 1:
                idx = len(shifted_colors) - 2
                frac = 1.0
            color = _lerp_color(shifted_colors[idx], shifted_colors[idx + 1], frac)
            rendered.append(char, style=f"bold {color}")
        console.print(rendered)
        time.sleep(speed)


def print_tagline() -> None:
    """Print the tagline with a glowing effect."""
    term_width = shutil.get_terminal_size().columns
    tagline = "⚡ AI-powered personal work agent"
    pad = max((term_width - len(tagline)) // 2, 0)

    tag_text = Text(" " * pad)
    tag_text.append("⚡ ", style=f"bold {NEON['yellow']}")
    tag_text.append_text(gradient_text(
        "AI-powered personal work agent",
        ["#ffffff", "#cccccc", "#aaaaaa"],
        bold=True,
    ))
    console.print(tag_text)


def print_version_bar() -> None:
    """Print a sleek system info bar."""
    term_width = shutil.get_terminal_size().columns

    parts = Text()
    parts.append("  v", style="dim")
    parts.append(VERSION, style=f"bold {NEON['cyan']}")
    parts.append("  │  ", style="dim")
    parts.append(f"Python {platform.python_version()}", style="dim")
    parts.append("  │  ", style="dim")
    parts.append(platform.system(), style="dim")
    parts.append("  │  ", style="dim")
    now = datetime.now().strftime("%H:%M")
    parts.append(now, style="dim")

    pad = max((term_width - len(parts.plain)) // 2, 0)
    padded = Text(" " * pad)
    padded.append_text(parts)
    console.print(padded)


def print_divider(char: str = "─", style: str = "dim cyan") -> None:
    """Print a full-width divider."""
    width = min(shutil.get_terminal_size().columns, 80)
    console.print(Text(char * width, style=style))


def print_gradient_divider() -> None:
    """Print a gradient-colored divider line."""
    term_w = shutil.get_terminal_size().columns
    width = min(term_w - 1, 79)  # -1 to prevent line wrap
    divider = Text()
    chars = "─" * width
    for i, c in enumerate(chars):
        t = i / max(width - 1, 1)
        seg = t * (len(GRADIENT_COLORS) - 1)
        idx = int(seg)
        frac = seg - idx
        if idx >= len(GRADIENT_COLORS) - 1:
            idx = len(GRADIENT_COLORS) - 2
            frac = 1.0
        color = _lerp_color(GRADIENT_COLORS[idx], GRADIENT_COLORS[idx + 1], frac)
        divider.append(c, style=color)
    console.print(divider)


# ── Full Banner Sequence ───────────────────────────────────────────────────────

def full_banner(animate: bool = True) -> None:
    """Print the complete startup banner with animation."""
    if animate:
        animate_banner(speed=0.012)
    else:
        console.print()
        banner = gradient_banner()
        console.print(Align.center(banner))
    console.print()
    print_tagline()
    print_version_bar()
    print_gradient_divider()
    console.print()


# ── Command Card Rendering ─────────────────────────────────────────────────────

COMMAND_CARDS = [
    {"cmd": "start",  "icon": "▶", "color": NEON["green"],  "desc": "Start orchestrator + frontend services"},
    {"cmd": "stop",   "icon": "⏹", "color": NEON["red"],    "desc": "Stop all running services"},
    {"cmd": "status", "icon": "📡", "color": NEON["blue"],   "desc": "Show service & integration status"},
    {"cmd": "ui",     "icon": "🖥", "color": NEON["purple"], "desc": "Launch the interactive TUI dashboard"},
    {"cmd": "tools",  "icon": "🔧", "color": NEON["orange"], "desc": "List all available MCP tools"},
    {"cmd": "agents", "icon": "🤖", "color": NEON["cyan"],   "desc": "List active LangGraph agents"},
    {"cmd": "keys",   "icon": "🔑", "color": NEON["yellow"], "desc": "Set API keys in .env"},
    {"cmd": "login",  "icon": "🌐", "color": NEON["blue"],   "desc": "Re-authenticate Microsoft Graph"},
    {"cmd": "chat",   "icon": "💬", "color": NEON["pink"],   "desc": "Interactive REPL or one-shot query"},
]


def render_command_table() -> Panel:
    """Render commands as a sleek table with icons and gradient accents."""
    table = Table(
        show_header=True,
        header_style=f"bold {NEON['cyan']}",
        box=box.SIMPLE_HEAVY,
        padding=(0, 2),
        expand=False,
    )
    table.add_column("", width=3, justify="center")
    table.add_column("Command", min_width=10)
    table.add_column("Description", min_width=40)

    for card in COMMAND_CARDS:
        cmd_text = Text(card["cmd"], style=f"bold {card['color']}")
        desc_text = Text(card["desc"], style="white")
        table.add_row(card["icon"], cmd_text, desc_text)

    return Panel(
        table,
        title="[bold white] Commands [/bold white]",
        title_align="left",
        border_style=NEON["cyan"],
        expand=False,
        padding=(1, 1),
    )


def render_options_panel() -> Panel:
    """Render options panel."""
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_row(
        Text("-h, --help", style=f"bold {NEON['cyan']}"),
        Text("Show this help message and exit", style="white"),
    )
    table.add_row(
        Text("-v, --verbose", style=f"bold {NEON['cyan']}"),
        Text("Verbose output", style="white"),
    )
    return Panel(
        table,
        title="[bold white] Options [/bold white]",
        title_align="left",
        border_style="dim",
        expand=False,
        padding=(0, 1),
    )


def render_examples_panel() -> Panel:
    """Render examples with styled commands."""
    examples = [
        ("tagent start", "Start orchestrator + frontend"),
        ("tagent stop", "Stop all services"),
        ("tagent status", "Check service health"),
        ("tagent ui", "Launch interactive TUI"),
        ("tagent chat", "Launch interactive REPL"),
        ('tagent chat "list tools"', "Send a one-shot query"),
    ]
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    for cmd, desc in examples:
        table.add_row(
            Text(f"$ {cmd}", style=f"bold {NEON['green']}"),
            Text(desc, style="dim white"),
        )
    return Panel(
        table,
        title="[bold white] Examples [/bold white]",
        title_align="left",
        border_style="dim",
        expand=False,
        padding=(0, 1),
    )


def render_tip() -> None:
    """Render a rotating tip at the bottom."""
    tips = [
        "Use [bold cyan]tagent chat[/bold cyan] to launch an interactive AI session",
        "Run [bold cyan]tagent status[/bold cyan] to check all services at a glance",
        "Use [bold cyan]tagent ui[/bold cyan] to launch the full TUI dashboard",
        "Type [bold magenta]/tools[/bold magenta] in chat mode for fuzzy tool search",
    ]
    import random
    tip = random.choice(tips)
    console.print(f"  [dim]💡 Tip: {tip}[/dim]")
    console.print()


# ── Chat REPL Rendering ───────────────────────────────────────────────────────

def chat_prompt() -> str:
    """Render a styled chat input prompt and return user input."""
    prompt_text = Text()
    prompt_text.append("❯ ", style=f"bold {NEON['cyan']}")
    return console.input(prompt_text)


def render_thinking_animation(thread, result_container: dict) -> None:
    """Show a beautiful multi-stage thinking animation while waiting."""
    stages = [
        (NEON["cyan"],   "⠋", "Classifier",  "Analyzing intent & routing..."),
        (NEON["yellow"], "⠙", "DACL Guard",   "Evaluating business policies..."),
        (NEON["blue"],   "⠹", "Planner",      "Developing execution plan..."),
        (NEON["orange"], "⠸", "Executor",     "Invoking MCP tools..."),
        (NEON["purple"], "⠼", "Reviewer",     "Synthesizing output..."),
        (NEON["green"],  "⠴", "Tagent",       "Finalizing response..."),
    ]

    spinner_cycle = itertools.cycle(SPINNER_FRAMES)
    wave_cycle = itertools.cycle(WAVE_FRAMES)
    stage_idx = 0
    tick = 0

    def build_frame() -> Text:
        nonlocal stage_idx, tick
        color, _, name, desc = stages[stage_idx]
        spinner = next(spinner_cycle)
        wave = next(wave_cycle)

        frame = Text()
        frame.append(f"  {spinner} ", style=f"bold {color}")
        frame.append(f"{name}", style=f"bold {color}")
        frame.append(f"  {desc}", style="dim")
        frame.append(f"  {wave}", style=f"dim {color}")
        return frame

    with Live(build_frame(), console=console, refresh_per_second=8, transient=True) as live:
        while thread.is_alive():
            live.update(build_frame())
            time.sleep(0.12)
            tick += 1
            if tick % 12 == 0 and stage_idx < len(stages) - 1:
                stage_idx += 1

    thread.join()


def render_chat_welcome() -> None:
    """Render the chat mode welcome screen."""
    console.print()
    shortcuts = Text()
    shortcuts.append("  Commands: ", style="dim")
    shortcuts.append("/tools", style=f"bold {NEON['orange']}")
    shortcuts.append(" search tools  ", style="dim")
    shortcuts.append("/clear", style=f"bold {NEON['blue']}")
    shortcuts.append(" clear screen  ", style="dim")
    shortcuts.append("/help", style=f"bold {NEON['purple']}")
    shortcuts.append(" show help  ", style="dim")
    shortcuts.append("exit", style=f"bold {NEON['red']}")
    shortcuts.append(" quit", style="dim")
    console.print(shortcuts)
    print_gradient_divider()
    console.print()


def render_user_message(msg: str) -> None:
    """Render the user's message in the chat."""
    text = Text()
    text.append("  ● ", style=f"bold {NEON['green']}")
    text.append("You", style="bold white")
    console.print(text)
    console.print(f"    {msg}")
    console.print()


def render_response_panel(response: str, intent: str = "unknown") -> None:
    """Render the agent response in a beautiful panel."""
    from rich.markdown import Markdown

    intent_text = Text()
    intent_text.append("  ◆ ", style=f"bold {NEON['cyan']}")
    intent_text.append("Tagent", style=f"bold {NEON['cyan']}")
    intent_text.append(f"  /{intent}", style="dim italic")
    console.print(intent_text)

    panel = Panel(
        Markdown(response),
        border_style=NEON["cyan"],
        padding=(1, 2),
        expand=False,
    )
    console.print(panel)
    console.print()


def render_error(msg: str) -> None:
    """Render a styled error message."""
    text = Text()
    text.append("  ✖ ", style=f"bold {NEON['red']}")
    text.append(msg, style=f"{NEON['red']}")
    console.print(text)


def render_success(msg: str) -> None:
    """Render a styled success message."""
    text = Text()
    text.append("  ✔ ", style=f"bold {NEON['green']}")
    text.append(msg, style="white")
    console.print(text)
