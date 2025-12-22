"""TUI rendering components."""

from typing import List

from domain import VPNState, Status
from infrastructure.log_reader import LogReader
from presentation.terminal import Terminal, visible_len


BOX = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

STATUS_CONFIG = {
    Status.DISCONNECTED: ("○", "Disconnected", "red"),
    Status.WAITING: ("○", "Waiting", "cyan"),
    Status.CONNECTING: (None, "Connecting..", "cyan"),
    Status.CONNECTED: ("●", "Connected", "green"),
}


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

    def format(self, status: Status, frame: int = 0) -> str:
        plain = self.format_plain(status, frame)
        if not self.term.use_color:
            return plain
        return f"{self._get_color(status)}{plain}{self.term.reset()}"

    def _label(self, name: str) -> str:
        """Format a bold label."""
        return f"{self.term.color('bold')}{name}{self.term.reset()}"

    def format_line(self, ext: Status, int_: Status, frame: int) -> str:
        ext_c = f"{self._label('EXT')} {self.format(ext, frame)}"
        int_c = f"{self._label('INT')} {self.format(int_, frame)}"
        return f"{ext_c}  {int_c}"


class TUI:
    """Main TUI renderer."""

    STATUS_HEIGHT = 4

    def __init__(self, term: Terminal = None, log_reader: LogReader = None):
        self.term = term or Terminal()
        self.box = Box(self.term)
        self.status = StatusLine(self.term)
        self.log_reader = log_reader or LogReader()

    def _log_box_heights(self, height: int) -> tuple:
        """Calculate log box heights, distributing remainder to first box."""
        remaining = height - self.STATUS_HEIGHT
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
        ext_box_h, int_box_h = self._log_box_heights(h)
        ext_lines_n, int_lines_n = ext_box_h - 2, int_box_h - 2
        clr = self.term.clear_line()

        lines = []
        lines.append(self.box.top("Status", w))
        lines.append(
            self.box.line(
                self.status.format_line(
                    state.ext_status, state.int_status, state.spinner_frame
                ),
                w,
            )
        )
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
        self.term.move_to(3, 3 + len(prompt))
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
