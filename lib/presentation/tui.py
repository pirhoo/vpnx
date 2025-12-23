"""TUI rendering components."""

from typing import List, Union

from domain import VPNState, Status, BandwidthStats
from domain.value_objects import VPNType
from infrastructure.log_reader import LogReader
from presentation.terminal import Terminal, visible_len


BOX = {
    "tl": "╭",
    "tr": "╮",
    "bl": "╰",
    "br": "╯",
    "h": "─",
    "v": "│",
    "ml": "├",
    "mr": "┤",
    "mt": "┬",
    "mb": "┴",
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

    # Fixed content: "LBL ● ↓nnnnnnnn/s ↑nnnnnnnn/s  (nnnnnn)"
    # Visible chars: 3 + 2 + 12 + 1 + 12 + 2 + ~10 = ~42 without sparkline
    FIXED_WIDTH = 42

    def __init__(self, term: Terminal):
        self.term = term
        self.sparkline = Sparkline(term)

    def _get_sparkline(self, stats: BandwidthStats, width: int) -> str:
        """Generate sparkline from bandwidth history."""
        if width <= 0:
            return ""
        combined = []
        for i in range(max(len(stats.history_in), len(stats.history_out))):
            h_in = stats.history_in[i] if i < len(stats.history_in) else 0
            h_out = stats.history_out[i] if i < len(stats.history_out) else 0
            combined.append(h_in + h_out)
        return self.sparkline.render(combined, width)

    def format(self, stats: BandwidthStats, label: str, width: int = 50) -> str:
        """Format bandwidth line: LABEL ↓rate ↑rate [sparkline] (total)."""
        down = format_rate(stats.rate_in)
        up = format_rate(stats.rate_out)
        total = format_bytes(stats.total_in + stats.total_out)
        spark_width = max(5, width - self.FIXED_WIDTH)
        spark = self._get_sparkline(stats, spark_width)

        lbl = f"{self.term.color('bold')}{label}{self.term.reset()}"
        down_c = f"{self.term.color('green')}↓{down:>10}{self.term.reset()}"
        up_c = f"{self.term.color('cyan')}↑{up:>10}{self.term.reset()}"
        total_c = f"{self.term.color('dim')}({total}){self.term.reset()}"

        return f"{lbl} {down_c} {up_c} {spark} {total_c}"

    def format_with_status(
        self,
        stats: BandwidthStats,
        label: str,
        status: Status,
        frame: int = 0,
        width: int = 50,
    ) -> str:
        """Format bandwidth with status icon: LABEL ● ↓rate ↑rate [sparkline] (total)."""
        icon, _, color_name = STATUS_CONFIG[status]
        if icon is None:
            icon = SPINNER[frame % len(SPINNER)]

        down = format_rate(stats.rate_in)
        up = format_rate(stats.rate_out)
        total = format_bytes(stats.total_in + stats.total_out)
        spark_width = max(5, width - self.FIXED_WIDTH)
        spark = self._get_sparkline(stats, spark_width)

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
        return self._c(
            f"{BOX['ml']}{self.hline(left_w)}{BOX['mb']}{self.hline(right_w)}{BOX['mr']}"
        )

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


class TUI:
    """Main TUI renderer."""

    STATUS_HEIGHT = 5  # top + content + separator + prompt + bottom

    def __init__(self, term: Terminal = None, log_reader: LogReader = None):
        self.term = term or Terminal()
        self.box = Box(self.term)
        self.status = StatusLine(self.term)
        self.bandwidth = BandwidthLine(self.term)
        self.log_reader = log_reader or LogReader()

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

    def render_single(
        self, state: VPNState, vpn_name: str, w: int = None, h: int = None
    ) -> str:
        """Render TUI for a single VPN connection."""
        w, h = w or self.term.width, h or self.term.height
        status_h = 4  # top + content + prompt + bottom (no separator needed)
        log_h = h - status_h
        log_lines_n = log_h - 2
        clr = self.term.clear_line()

        # Get the appropriate status/bandwidth/log for this VPN using generic accessors
        vpn_type = VPNType(vpn_name)
        vpn_status = state.get_status(vpn_type)
        vpn_bandwidth = state.get_bandwidth(vpn_type)
        vpn_log = state.get_log(vpn_type)

        has_bw = vpn_bandwidth.total_in > 0

        lines = []
        lines.append(self.box.top("Status", w))

        # Status/bandwidth line
        content_width = w - 4
        if has_bw:
            cell = self.bandwidth.format_with_status(
                vpn_bandwidth, vpn_name, vpn_status, state.spinner_frame, content_width
            )
        else:
            cell = self.status.format(vpn_name, vpn_status, state.spinner_frame)

        lines.append(self.box.line(cell, w))

        hint = f"{self.term.color('dim')}q:quit  r:reconnect  ↑↓:scroll{self.term.reset()}"
        lines.append(self.box.line(state.prompt if state.prompt else hint, w))
        lines.append(self.box.bottom(w))

        scroll_offset = state.get_scroll_offset(vpn_name)
        log_lines = self.log_reader.read_tail(vpn_log, log_lines_n, scroll_offset)
        log_title = f"{vpn_name} Log"
        if scroll_offset > 0:
            log_title += f" (+{scroll_offset})"
        lines.extend(self._render_box(log_title, log_lines, log_lines_n, w))

        return self.term.home() + (clr + "\n").join(lines) + clr

    def render_two(
        self, state: VPNState, vpn_names: List[str], w: int = None, h: int = None
    ) -> str:
        """Render TUI for two VPNs in side-by-side layout."""
        w, h = w or self.term.width, h or self.term.height
        name1, name2 = vpn_names[0], vpn_names[1]

        # Calculate heights
        first_box_h, second_box_h = self._log_box_heights(h, self.STATUS_HEIGHT)
        first_lines_n, second_lines_n = first_box_h - 2, second_box_h - 2
        clr = self.term.clear_line()

        # Split position for two-column layout
        split = w // 2

        # Get status/bandwidth for each VPN
        vpn1_type, vpn2_type = VPNType(name1), VPNType(name2)
        status1 = state.get_status(vpn1_type)
        status2 = state.get_status(vpn2_type)
        bw1 = state.get_bandwidth(vpn1_type)
        bw2 = state.get_bandwidth(vpn2_type)
        log1 = state.get_log(vpn1_type)
        log2 = state.get_log(vpn2_type)

        lines = []
        lines.append(self.box.top_split("Status", w, split))

        # Cell widths
        left_width = split - 3
        right_width = w - split - 4

        has_bw = bw1.total_in > 0 or bw2.total_in > 0

        if has_bw:
            cell1 = self.bandwidth.format_with_status(
                bw1, name1, status1, state.spinner_frame, left_width
            )
            cell2 = self.bandwidth.format_with_status(
                bw2, name2, status2, state.spinner_frame, right_width
            )
        else:
            cell1 = self.status.format(name1, status1, state.spinner_frame)
            cell2 = self.status.format(name2, status2, state.spinner_frame)

        lines.append(self.box.two_cells(cell1, cell2, w, split))
        lines.append(self.box.separator_join(w, split))

        hint = f"{self.term.color('dim')}q:quit  r:reconnect  ↑↓:scroll  tab:switch{self.term.reset()}"
        lines.append(self.box.line(state.prompt if state.prompt else hint, w))
        lines.append(self.box.bottom(w))

        # Log boxes with scroll offset - highlight active one
        scroll1 = state.get_scroll_offset(name1)
        scroll2 = state.get_scroll_offset(name2)
        log1_lines = self.log_reader.read_tail(log1, first_lines_n, scroll1)
        log2_lines = self.log_reader.read_tail(log2, second_lines_n, scroll2)
        marker1 = "▶ " if state.active_vpn_index == 0 else ""
        marker2 = "▶ " if state.active_vpn_index == 1 else ""
        title1 = f"{marker1}{name1} Log" + (f" (+{scroll1})" if scroll1 > 0 else "")
        title2 = f"{marker2}{name2} Log" + (f" (+{scroll2})" if scroll2 > 0 else "")
        lines.extend(self._render_box(title1, log1_lines, first_lines_n, w))
        lines.extend(self._render_box(title2, log2_lines, second_lines_n, w))

        return self.term.home() + (clr + "\n").join(lines) + clr

    def render_multi(
        self, state: VPNState, vpn_names: List[str], w: int = None, h: int = None
    ) -> str:
        """Render TUI for N VPNs (3+) in vertical stack layout."""
        w, h = w or self.term.width, h or self.term.height
        n = len(vpn_names)
        clr = self.term.clear_line()

        # Status box: top + N status lines + prompt + bottom = N + 3
        status_h = n + 3
        # Remaining height for log boxes, divided equally
        remaining = h - status_h
        log_h_per_vpn = max(3, remaining // n)

        lines = []
        lines.append(self.box.top("Status", w))

        content_width = w - 4
        has_bw = any(
            state.get_bandwidth(VPNType(name)).total_in > 0 for name in vpn_names
        )

        # Render each VPN status line
        for name in vpn_names:
            vpn_type = VPNType(name)
            status = state.get_status(vpn_type)
            bw = state.get_bandwidth(vpn_type)

            if has_bw:
                cell = self.bandwidth.format_with_status(
                    bw, name, status, state.spinner_frame, content_width
                )
            else:
                cell = self.status.format(name, status, state.spinner_frame)
            lines.append(self.box.line(cell, w))

        hint = f"{self.term.color('dim')}q:quit  r:reconnect  ↑↓:scroll  tab:switch{self.term.reset()}"
        lines.append(self.box.line(state.prompt if state.prompt else hint, w))
        lines.append(self.box.bottom(w))

        # Render log boxes for each VPN with scroll offset - highlight active one
        log_lines_n = log_h_per_vpn - 2
        for i, name in enumerate(vpn_names):
            vpn_type = VPNType(name)
            log_path = state.get_log(vpn_type)
            scroll_offset = state.get_scroll_offset(name)
            log_lines = self.log_reader.read_tail(log_path, log_lines_n, scroll_offset)
            marker = "▶ " if state.active_vpn_index == i else ""
            title = f"{marker}{name} Log" + (f" (+{scroll_offset})" if scroll_offset > 0 else "")
            lines.extend(self._render_box(title, log_lines, log_lines_n, w))

        return self.term.home() + (clr + "\n").join(lines) + clr

    def _normalize_vpn_names(self, vpn_names: Union[str, List[str]]) -> List[str]:
        """Normalize vpn_names to a list."""
        if isinstance(vpn_names, str):
            return [vpn_names]
        return vpn_names

    def display(self, state: VPNState, vpn_names: Union[str, List[str]]) -> None:
        """Display TUI for the given VPN(s).

        Args:
            state: Current VPN state
            vpn_names: VPN name(s) to display:
                - str: single VPN name
                - List[str]: list of VPN names (1=single, 2=two-column, 3+=stacked)
        """
        names = self._normalize_vpn_names(vpn_names)

        if len(names) == 1:
            self.term.write(self.render_single(state, names[0]))
        elif len(names) == 2:
            self.term.write(self.render_two(state, names))
        else:
            self.term.write(self.render_multi(state, names))
        self.term.flush()

    def position_input(self, prompt: str, vpn_names: Union[str, List[str]]) -> None:
        """Position cursor at input location.

        Args:
            prompt: Current prompt text
            vpn_names: VPN name(s) being displayed
        """
        names = self._normalize_vpn_names(vpn_names)

        if len(names) == 1:
            row = 3  # top, content, prompt
        elif len(names) == 2:
            row = 4  # top, cells, separator, prompt
        else:
            # For N VPNs: top + N status lines + prompt
            row = 2 + len(names)

        self.term.move_to(row, 3 + len(prompt))
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
