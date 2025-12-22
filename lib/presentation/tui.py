"""TUI rendering components."""

from typing import List

from domain import VPNState, Status, BandwidthStats
from infrastructure.log_reader import LogReader
from presentation.terminal import Terminal, visible_len


BOX = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│",
    "ml": "├", "mr": "┤", "mt": "┬", "mb": "┴",
}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"

STATUS_CONFIG = {
    Status.DISCONNECTED: ("○", "Disconnected", "red"),
    Status.WAITING: ("○", "Waiting", "cyan"),
    Status.CONNECTING: (None, "Connecting..", "cyan"),
    Status.CONNECTED: ("●", "Connected", "green"),
}


def format_bytes(n: float) -> str:
    """Format bytes to human readable string."""
    if n < 1024:
        return f"{n:.0f} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    else:
        return f"{n / (1024 * 1024 * 1024):.1f} GB"


def format_rate(n: float) -> str:
    """Format bytes/sec to human readable string."""
    return f"{format_bytes(n)}/s"


class Sparkline:
    """Colored sparkline bar chart for bandwidth visualization."""

    def __init__(self, term: Terminal):
        self.term = term

    def render(self, values: List[float], width: int) -> str:
        """Render a sparkline from values, fitting to width."""
        if not values:
            return " " * width

        # Pad or truncate to fit width
        if len(values) < width:
            values = [0.0] * (width - len(values)) + list(values)
        elif len(values) > width:
            values = values[-width:]

        max_val = max(values) if values else 1
        if max_val == 0:
            max_val = 1

        result = []
        for v in values:
            # Normalize to 0-7 range for sparkline chars
            level = int((v / max_val) * 7)
            level = min(7, max(0, level))
            char = SPARKLINE_CHARS[level]

            # Color based on level: green -> yellow -> red
            if level <= 2:
                color = self.term.color("green")
            elif level <= 5:
                color = self.term.color("yellow")
            else:
                color = self.term.color("red")

            if self.term.use_color:
                result.append(f"{color}{char}{self.term.reset()}")
            else:
                result.append(char)

        return "".join(result)


class BandwidthLine:
    """Bandwidth display with sparkline and stats."""

    SPARKLINE_WIDTH = 10

    def __init__(self, term: Terminal):
        self.term = term
        self.sparkline = Sparkline(term)

    def _get_sparkline(self, stats: BandwidthStats) -> str:
        """Generate sparkline from bandwidth history."""
        combined = []
        for i in range(max(len(stats.history_in), len(stats.history_out))):
            h_in = stats.history_in[i] if i < len(stats.history_in) else 0
            h_out = stats.history_out[i] if i < len(stats.history_out) else 0
            combined.append(h_in + h_out)
        return self.sparkline.render(combined, self.SPARKLINE_WIDTH)

    def format(self, stats: BandwidthStats, label: str) -> str:
        """Format bandwidth line: LABEL ↓rate ↑rate [sparkline] (total)."""
        down = format_rate(stats.rate_in)
        up = format_rate(stats.rate_out)
        total = format_bytes(stats.total_in + stats.total_out)
        spark = self._get_sparkline(stats)

        lbl = f"{self.term.color('bold')}{label}{self.term.reset()}"
        down_c = f"{self.term.color('green')}↓{down:>10}{self.term.reset()}"
        up_c = f"{self.term.color('cyan')}↑{up:>10}{self.term.reset()}"
        total_c = f"{self.term.color('dim')}({total}){self.term.reset()}"

        return f"{lbl} {down_c} {up_c} {spark} {total_c}"

    def format_with_status(
        self, stats: BandwidthStats, label: str, status: Status, frame: int = 0
    ) -> str:
        """Format bandwidth with status icon: LABEL ● ↓rate ↑rate [sparkline] (total)."""
        icon, _, color_name = STATUS_CONFIG[status]
        if icon is None:
            icon = SPINNER[frame % len(SPINNER)]

        down = format_rate(stats.rate_in)
        up = format_rate(stats.rate_out)
        total = format_bytes(stats.total_in + stats.total_out)
        spark = self._get_sparkline(stats)

        lbl = f"{self.term.color('bold')}{label}{self.term.reset()}"
        icon_c = f"{self.term.color(color_name)}{icon}{self.term.reset()}"
        down_c = f"{self.term.color('green')}↓{down:>10}{self.term.reset()}"
        up_c = f"{self.term.color('cyan')}↑{up:>10}{self.term.reset()}"
        total_c = f"{self.term.color('dim')}({total}){self.term.reset()}"

        return f"{lbl} {icon_c} {down_c} {up_c} {spark} {total_c}"


class Box:
    """Box drawing utilities."""

    def __init__(self, term: Terminal):
        self.term = term

    def _c(self, text: str) -> str:
        """Wrap text in box color."""
        return f"{self.term.color('gray')}{text}{self.term.reset()}"

    def hline(self, n: int) -> str:
        return BOX["h"] * n

    def top(self, title: str, width: int) -> str:
        inner = width - 2
        if not title:
            return self._c(f"{BOX['tl']}{self.hline(inner)}{BOX['tr']}")
        title_part = f"{BOX['h']} {title} "
        return self._c(
            f"{BOX['tl']}{title_part}{self.hline(inner - len(title) - 3)}{BOX['tr']}"
        )

    def bottom(self, width: int) -> str:
        return self._c(f"{BOX['bl']}{self.hline(width - 2)}{BOX['br']}")

    def separator(self, width: int) -> str:
        """Horizontal separator line: ├────────┤"""
        return self._c(f"{BOX['ml']}{self.hline(width - 2)}{BOX['mr']}")

    def top_split(self, title: str, width: int, split_pos: int) -> str:
        """Top line with vertical divider: ╭─ Title ──┬──────╮"""
        inner = width - 2
        left_w = split_pos - 1
        right_w = inner - split_pos
        if not title:
            left = self.hline(left_w)
        else:
            title_part = f"{BOX['h']} {title} "
            left = f"{title_part}{self.hline(left_w - len(title) - 3)}"
        return self._c(f"{BOX['tl']}{left}{BOX['mt']}{self.hline(right_w)}{BOX['tr']}")

    def separator_join(self, width: int, split_pos: int) -> str:
        """Separator that joins columns: ├────────┴────────┤"""
        inner = width - 2
        left_w = split_pos - 1
        right_w = inner - split_pos
        return self._c(f"{BOX['ml']}{self.hline(left_w)}{BOX['mb']}{self.hline(right_w)}{BOX['mr']}")

    def _truncate_ansi(self, content: str, max_len: int) -> str:
        """Truncate string preserving ANSI codes."""
        from presentation.terminal import ANSI_RE

        parts, count, result = ANSI_RE.split(content), 0, []
        for i, part in enumerate(ANSI_RE.findall(content) + [""]):
            if count < max_len and i < len(parts):
                take = min(len(parts[i]), max_len - count)
                result.extend([parts[i][:take], part])
                count += take
        return "".join(result) + self.term.reset()

    def line(self, content: str, width: int) -> str:
        inner = width - 4
        vlen = visible_len(content)
        if vlen > inner:
            content = self._truncate_ansi(content, inner)
            vlen = visible_len(content)
        v = self._c(BOX["v"])
        return f"{v} {content}{' ' * (inner - vlen)} {v}"

    def empty(self, width: int) -> str:
        v = self._c(BOX["v"])
        return f"{v} {' ' * (width - 4)} {v}"

    def two_cells(self, left: str, right: str, width: int, split_pos: int) -> str:
        """Two cells side by side: │ left │ right │"""
        left_inner = split_pos - 3  # "│ " at start + " " before middle = 3
        right_inner = width - split_pos - 4  # "│ " after middle + " │" at end = 4

        left_vlen = visible_len(left)
        right_vlen = visible_len(right)

        if left_vlen > left_inner:
            left = self._truncate_ansi(left, left_inner)
            left_vlen = visible_len(left)
        if right_vlen > right_inner:
            right = self._truncate_ansi(right, right_inner)
            right_vlen = visible_len(right)

        v = self._c(BOX["v"])
        left_pad = " " * (left_inner - left_vlen)
        right_pad = " " * (right_inner - right_vlen)
        return f"{v} {left}{left_pad} {v} {right}{right_pad} {v}"


class StatusLine:
    """Status indicator formatting."""

    WIDTH = 14

    def __init__(self, term: Terminal):
        self.term = term

    def _get_icon(self, status: Status, frame: int) -> str:
        icon = STATUS_CONFIG[status][0]
        return SPINNER[frame % len(SPINNER)] if icon is None else icon

    def _get_text(self, status: Status) -> str:
        return STATUS_CONFIG[status][1]

    def _get_color(self, status: Status) -> str:
        return self.term.color(STATUS_CONFIG[status][2])

    def format_plain(self, status: Status, frame: int = 0) -> str:
        return f"{self._get_icon(status, frame)} {self._get_text(status)}".ljust(
            self.WIDTH
        )

    def format(self, label: str, status: Status, frame: int = 0) -> str:
        """Format status with label: LABEL ● Status"""
        icon = self._get_icon(status, frame)
        text = self._get_text(status)
        color = self._get_color(status)
        lbl = f"{self.term.color('bold')}{label}{self.term.reset()}"
        if self.term.use_color:
            return f"{lbl} {color}{icon} {text}{self.term.reset()}"
        return f"{label} {icon} {text}"

    def format_line(self, ext: Status, int_: Status, frame: int) -> str:
        ext_c = self.format("EXT", ext, frame)
        int_c = self.format("INT", int_, frame)
        return f"{ext_c}  {int_c}"


class TUI:
    """Main TUI renderer."""

    STATUS_HEIGHT = 5  # top + content + separator + prompt + bottom

    def __init__(self, term: Terminal = None, log_reader: LogReader = None):
        self.term = term or Terminal()
        self.box = Box(self.term)
        self.status = StatusLine(self.term)
        self.bandwidth = BandwidthLine(self.term)
        self.log_reader = log_reader or LogReader()

    def _has_bandwidth(self, state: VPNState) -> bool:
        """Check if we have bandwidth data to display."""
        return state.ext_bandwidth.total_in > 0 or state.int_bandwidth.total_in > 0

    def _log_box_heights(self, height: int, status_height: int) -> tuple:
        """Calculate log box heights, distributing remainder to first box."""
        remaining = height - status_height
        base = max(4, remaining // 2)
        extra = remaining - (base * 2)
        return base + extra, base

    def _render_box(
        self, title: str, lines: List[str], count: int, w: int
    ) -> List[str]:
        out = [self.box.top(title, w)]
        pad = count - len(lines)
        for i in range(count):
            if i < pad:
                out.append(self.box.empty(w))
            else:
                out.append(self.box.line(lines[i - pad], w))
        out.append(self.box.bottom(w))
        return out

    def render(self, state: VPNState, w: int = None, h: int = None) -> str:
        w, h = w or self.term.width, h or self.term.height
        ext_box_h, int_box_h = self._log_box_heights(h, self.STATUS_HEIGHT)
        ext_lines_n, int_lines_n = ext_box_h - 2, int_box_h - 2
        clr = self.term.clear_line()

        # Split position for two-column layout (middle of box)
        split = w // 2

        lines = []
        lines.append(self.box.top_split("Status", w, split))

        # Show status in two cells (EXT left, INT right)
        if self._has_bandwidth(state):
            ext_cell = self.bandwidth.format_with_status(
                state.ext_bandwidth, "EXT", state.ext_status, state.spinner_frame
            )
            int_cell = self.bandwidth.format_with_status(
                state.int_bandwidth, "INT", state.int_status, state.spinner_frame
            )
        else:
            ext_cell = self.status.format("EXT", state.ext_status, state.spinner_frame)
            int_cell = self.status.format("INT", state.int_status, state.spinner_frame)

        lines.append(self.box.two_cells(ext_cell, int_cell, w, split))
        lines.append(self.box.separator_join(w, split))

        hint = f"{self.term.color('dim')}Ctrl+C to disconnect{self.term.reset()}"
        lines.append(self.box.line(state.prompt if state.prompt else hint, w))
        lines.append(self.box.bottom(w))

        ext_lines = self.log_reader.read_tail(state.ext_log, ext_lines_n)
        int_lines = self.log_reader.read_tail(state.int_log, int_lines_n)
        lines.extend(self._render_box("EXT Log", ext_lines, ext_lines_n, w))
        lines.extend(self._render_box("INT Log", int_lines, int_lines_n, w))

        return self.term.home() + (clr + "\n").join(lines) + clr

    def display(self, state: VPNState) -> None:
        self.term.write(self.render(state))
        self.term.flush()

    def position_input(self, prompt: str) -> None:
        self.term.move_to(4, 3 + len(prompt))  # Row 4: after top, content, separator
        self.term.flush()

    def setup(self) -> None:
        self.term.enter_alt_screen()
        self.term.hide_cursor()

    def cleanup(self) -> None:
        self.term.show_cursor()
        self.term.leave_alt_screen()

    def hide_cursor(self) -> None:
        self.term.hide_cursor()

    def show_cursor(self) -> None:
        self.term.show_cursor()
