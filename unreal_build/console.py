"""Styled streaming of child process output.

Child process output is piped, classified by severity and re-emitted in a muted
palette so that build/deploy noise stays visually subordinate to our own logs,
while errors and warnings remain distinguishable.
"""

import codecs
import enum
import locale
import os
import re
import subprocess
import sys
from pathlib import Path

RESET = '\x1b[0m'


class Severity(enum.Enum):
    NORMAL = '\x1b[38;5;244m'
    WARNING = '\x1b[38;5;136m'
    ERROR = '\x1b[38;5;131m'


_ANSI_PATTERN = re.compile(r'\x1b(?:\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])')
_SGR_PATTERN = re.compile(r'\x1b\[([0-9;]*)m')

_ERROR_PATTERNS = (
    re.compile(r'(?:^|[\s:])error(?:\s+[A-Z]+\d+)?\s*:', re.IGNORECASE),
    re.compile(r'^\s*ERROR\b'),
    re.compile(r'\bfatal error\b', re.IGNORECASE),
)
_WARNING_PATTERNS = (
    re.compile(r'(?:^|[\s:])warning(?:\s+[A-Z]+\d+)?\s*:', re.IGNORECASE),
    re.compile(r'^\s*WARN(?:ING)?\b'),
)

_ERROR_SGR_CODES = {'31', '91'}
_WARNING_SGR_CODES = {'33', '93'}

_color_enabled: bool | None = None
_color_forced_off = False


def disable_color():
    """Disable styling for the remainder of the process."""
    global _color_forced_off, _color_enabled
    _color_forced_off = True
    _color_enabled = False


def _enable_windows_vt() -> bool:
    """Turn on virtual terminal processing so ANSI codes render on Windows."""
    if sys.platform != 'win32':
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle in (0, -1):
            return False
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_vt = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if mode.value & enable_vt:
            return True
        return bool(kernel32.SetConsoleMode(handle, mode.value | enable_vt))
    except Exception:
        return False


def color_enabled() -> bool:
    global _color_enabled
    if _color_enabled is None:
        _color_enabled = not _color_forced_off and _detect_color_support()
    return _color_enabled


def _detect_color_support() -> bool:
    if os.environ.get('NO_COLOR') is not None:
        return False
    if os.environ.get('FORCE_COLOR'):
        return _enable_windows_vt()
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    return _enable_windows_vt()


def strip_ansi(line: str) -> str:
    """Remove every ANSI escape sequence from a line."""
    return _ANSI_PATTERN.sub('', line)


def classify(line: str) -> Severity:
    """Determine the severity of a raw (still ANSI-carrying) output line."""
    hinted = _classify_by_ansi(line)
    if hinted is not None:
        return hinted
    return _classify_by_content(strip_ansi(line))


def _classify_by_ansi(line: str) -> Severity | None:
    codes = {
        code
        for match in _SGR_PATTERN.findall(line)
        for code in match.split(';')
        if code
    }
    if codes & _ERROR_SGR_CODES:
        return Severity.ERROR
    if codes & _WARNING_SGR_CODES:
        return Severity.WARNING
    return None


def _classify_by_content(line: str) -> Severity:
    if any(pattern.search(line) for pattern in _ERROR_PATTERNS):
        return Severity.ERROR
    if any(pattern.search(line) for pattern in _WARNING_PATTERNS):
        return Severity.WARNING
    return Severity.NORMAL


def style(line: str, severity: Severity) -> str:
    """Wrap a plain line in the palette colour for its severity."""
    if not color_enabled():
        return line
    return f'{severity.value}{line}{RESET}'


def write_line(line: str):
    """Emit a single raw child output line, styled and stripped of its own colours."""
    try:
        severity = classify(line)
        _write(style(strip_ansi(line), severity) + '\n')
    except Exception:
        pass


def _write(text: str):
    """Write to stdout, degrading unrepresentable characters instead of dropping the line."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, 'encoding', None) or 'ascii'
        sys.stdout.write(
            text.encode(encoding, 'replace').decode(encoding, 'replace'))
    sys.stdout.flush()


def run_streamed(
        cmd: str | list[str] | Path,
        *,
        env: dict = None,
        shell: bool = False,
        cwd: str | Path = None,
        encoding: str = None,
) -> int:
    """Run a command, echoing its output in the muted palette.

    stderr is merged into stdout so the interleaving of the child's streams is
    preserved. Returns the process exit code.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=shell,
        env=env,
        cwd=cwd,
        bufsize=0,
    )
    try:
        _pump(proc.stdout, encoding or locale.getpreferredencoding(False))
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    return proc.wait()


def _read_available(stream, size: int) -> bytes:
    """Read whatever is currently available without waiting for a full buffer."""
    reader = getattr(stream, 'read1', stream.read)
    return reader(size)


def _pump(stream, encoding: str):
    """Read raw chunks and emit complete lines, splitting on \\r as well as \\n."""
    if stream is None:
        return
    decoder = codecs.getincrementaldecoder(encoding)(errors='replace')
    buffer = ''
    while True:
        chunk = _read_available(stream, 4096)
        if not chunk:
            break
        buffer = _emit_lines(buffer + decoder.decode(chunk), hold_trailing_cr=True)

    buffer = _emit_lines(buffer + decoder.decode(b'', final=True),
                         hold_trailing_cr=False)
    if buffer:
        write_line(buffer)


def _emit_lines(buffer: str, hold_trailing_cr: bool) -> str:
    """Emit every complete line in the buffer and return the unconsumed remainder."""
    start = 0
    index = 0
    length = len(buffer)
    while index < length:
        char = buffer[index]
        if char == '\n':
            write_line(buffer[start:index])
            index += 1
        elif char == '\r':
            if index + 1 >= length and hold_trailing_cr:
                # Could be the first half of a split "\r\n"; wait for more input.
                break
            if index + 1 < length and buffer[index + 1] == '\n':
                write_line(buffer[start:index])
                index += 2
            else:
                # A bare "\r" redraws the current line, so an empty segment is
                # an erase (progress bars) rather than a blank line to print.
                if index > start:
                    write_line(buffer[start:index])
                index += 1
        else:
            index += 1
            continue
        start = index
    return buffer[start:]
