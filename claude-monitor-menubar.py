#!/usr/bin/env python3
"""
Claude Monitor – macOS menu bar app.

Shows the number of active Claude Code sessions in the menu bar.
A green dot appears when at least one session is waiting for input.
A subtle sound plays when a session becomes ready.
Optional inline mode shows each session as its own menu bar item.
"""

import json
import subprocess
import os
import re
import rumps

PREFS_PATH = os.path.expanduser("~/.claude/claude-monitor-prefs.json")
import objc
from AppKit import (
    NSAttributedString,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSFont,
    NSColor,
    NSImage,
    NSBezierPath,
    NSRect,
    NSMakeRect,
    NSGraphicsContext,
    NSCompositingOperationSourceOver,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
)
from Foundation import NSSize

MONITOR_STATE_DIR = os.path.expanduser("~/.claude/monitor-state")


def _cwd_to_project_dir(cwd):
    """Convert a cwd path to the Claude projects directory name."""
    # Claude replaces both / and . with - in the directory name
    return "-" + cwd.lstrip("/").replace("/", "-").replace(".", "-")


def get_conversation_id(cwd):
    """Find the active conversation ID for a session by its cwd.

    The hooks write state files keyed by conversation ID (the ID from the
    projects directory), not the process-level sessionId. We find the most
    recently modified .jsonl in the matching project dir.
    """
    projects_dir = os.path.expanduser("~/.claude/projects")
    project_name = _cwd_to_project_dir(cwd)
    project_path = os.path.join(projects_dir, project_name)
    try:
        jsonl_files = [
            f for f in os.listdir(project_path)
            if f.endswith(".jsonl")
        ]
        if not jsonl_files:
            return None
        # Most recently modified = active conversation
        newest = max(
            jsonl_files,
            key=lambda f: os.path.getmtime(os.path.join(project_path, f)),
        )
        return newest.removesuffix(".jsonl")
    except (FileNotFoundError, OSError):
        return None


def get_hook_state(session_id):
    """Read the state written by the Notification hook. Returns 'idle', 'permission', or None."""
    if not session_id:
        return None
    try:
        with open(os.path.join(MONITOR_STATE_DIR, session_id)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def clear_hook_state(session_id):
    """Remove the state file when a session is detected as working."""
    if not session_id:
        return
    try:
        os.remove(os.path.join(MONITOR_STATE_DIR, session_id))
    except FileNotFoundError:
        pass


def get_claude_processes():
    """Find all running claude processes."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,tty,%cpu,etime,command"],
            capture_output=True, text=True, timeout=5,
        )
        processes = []
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 5 and parts[4] == "claude":
                processes.append({
                    "pid": int(parts[0]),
                    "tty": parts[1],
                    "cpu": float(parts[2]),
                    "elapsed": parts[3],
                })
        return processes
    except Exception:
        return []


def get_cwd(pid):
    """Get working directory for a process."""
    try:
        result = subprocess.run(
            ["lsof", "-p", str(pid), "-Fn"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.split("\n")
        for i, line in enumerate(lines):
            if line == "fcwd":
                if i + 1 < len(lines) and lines[i + 1].startswith("n"):
                    return lines[i + 1][1:]
    except Exception:
        pass
    return "unknown"


def get_working_children(pid):
    """Count child processes that indicate actual work (ignoring background helpers)."""
    IGNORED_COMMANDS = {"caffeinate"}
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True, text=True, timeout=5,
        )
        child_pids = [l for l in result.stdout.strip().split("\n") if l]
        working = 0
        for cpid in child_pids:
            try:
                info = subprocess.run(
                    ["ps", "-p", cpid, "-o", "comm="],
                    capture_output=True, text=True, timeout=5,
                )
                cmd = info.stdout.strip().split("/")[-1]
                if cmd not in IGNORED_COMMANDS:
                    working += 1
            except Exception:
                working += 1
        return working
    except Exception:
        return 0


def shorten_path(path):
    """Shorten a path for display."""
    match = re.search(r"worktrees/(.+)$", path)
    if match:
        return match.group(1)
    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]
    path = path.replace("~/zerocater/zerocater", "~/z/z")
    path = path.replace("~/zerocater/", "~/z/")
    return path


def dir_name(path):
    """Extract just the last directory component for inline display."""
    match = re.search(r"worktrees/(.+)$", path)
    if match:
        return match.group(1)
    return os.path.basename(path) if path != "unknown" else "?"


def infer_status(cpu, children, hook_state=None):
    """Infer session status from hook state, CPU, and child process count."""
    if children > 0 or cpu > 5.0:
        return "WORKING", "running tools" if children > 0 else "thinking/generating"
    # If no signs of work, trust the hook state if available
    if hook_state == "permission":
        return "PERMISSION", "needs approval"
    elif hook_state == "idle":
        return "READY", "waiting for you"
    # No hook state yet — fall back to heuristic
    return "READY", "waiting for you"


def make_inline_image(text, color):
    """Create an NSImage with text and a colored bar underneath."""
    font = NSFont.systemFontOfSize_(10)
    attrs = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: NSColor.labelColor(),
    }
    attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
    text_size = attr_str.size()

    bar_height = 3
    padding_h = 4  # horizontal padding
    padding_top = 1
    padding_bottom = 2
    width = text_size.width + padding_h * 2
    height = text_size.height + bar_height + padding_top + padding_bottom

    img = NSImage.alloc().initWithSize_(NSSize(width, height))
    img.setTemplate_(False)
    img.lockFocus()

    # Draw colored bar at the bottom
    bar_rect = NSMakeRect(padding_h, 0, text_size.width, bar_height)
    color.set()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bar_rect, 1.5, 1.5).fill()

    # Draw text above the bar
    attr_str.drawAtPoint_((padding_h, bar_height + padding_bottom))

    img.unlockFocus()
    return img


_COLORS = {}


def get_colors():
    if not _COLORS:
        _COLORS["green"] = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.2, 0.8, 0.3, 1.0)
        _COLORS["orange"] = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.95, 0.6, 0.1, 1.0)
        _COLORS["blue"] = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.2, 0.5, 1.0, 1.0)
    return _COLORS


from Foundation import NSObject as _NSObject


class _MenuActionHandler(_NSObject):
    """ObjC-compatible target for NSMenuItem actions."""

    def initWithApp_(self, app):
        self = objc.super(_MenuActionHandler, self).init()
        if self is None:
            return None
        self.app = app
        return self

    def toggleInline_(self, sender):
        self.app.inline_mode = not self.app.inline_mode
        self.app.update_display()

    def refresh_(self, sender):
        self.app.update_display()

    def quit_(self, sender):
        rumps.quit_application()


class ClaudeMonitorApp(rumps.App):
    def __init__(self):
        super().__init__("C", quit_button=None)
        self.sessions = []
        self.ready_pids = set()
        self.inline_mode = self._load_prefs().get("inline_mode", False)
        self.inline_items = []  # extra NSStatusItem instances
        self._action_handler = _MenuActionHandler.alloc().initWithApp_(self)

        self.inline_toggle = rumps.MenuItem(
            "Display Inline", callback=self.toggle_inline
        )

        self.menu = [
            rumps.MenuItem("No active sessions"),
            rumps.separator,
            self.inline_toggle,
            rumps.MenuItem("Refresh Now", callback=self.manual_refresh),
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self.update_display()

    @rumps.timer(2)
    def poll(self, _):
        self.update_display()

    def manual_refresh(self, _):
        self.update_display()

    def toggle_inline(self, sender):
        self.inline_mode = not self.inline_mode
        sender.state = self.inline_mode
        self._save_prefs()
        self.update_display()

    @staticmethod
    def _load_prefs():
        try:
            with open(PREFS_PATH) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_prefs(self):
        prefs = self._load_prefs()
        prefs["inline_mode"] = self.inline_mode
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f)

    def clear_inline_items(self):
        """Remove all extra status bar items."""
        status_bar = NSStatusBar.systemStatusBar()
        for item in self.inline_items:
            status_bar.removeStatusItem_(item)
        self.inline_items = []

    def _build_nsmenu(self, sessions, ready_count):
        """Build an NSMenu matching the dropdown contents."""
        menu = NSMenu.alloc().init()
        total = len(sessions)

        if not sessions:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No active sessions", None, "")
            menu.addItem_(item)
        else:
            summary = f"{total} session{'s' if total != 1 else ''}"
            if ready_count > 0:
                summary += f" — {ready_count} ready"
            menu.addItem_(
                NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(summary, None, ""))
            menu.addItem_(NSMenuItem.separatorItem())

            NS_STATUS_ICONS = {
                "READY": "\U0001F7E9",
                "PERMISSION": "\U0001F7E6",
                "WORKING": "\U0001F7E7",
            }
            for sess in sessions:
                icon = NS_STATUS_ICONS.get(sess["status"], "\U0001F7E7")
                label = f"{icon} {sess['project']}  —  {sess['detail']}"
                menu.addItem_(
                    NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, None, ""))

        menu.addItem_(NSMenuItem.separatorItem())

        handler = self._action_handler

        inline_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Display Inline", "toggleInline:", "")
        inline_item.setTarget_(handler)
        inline_item.setState_(1 if self.inline_mode else 0)
        menu.addItem_(inline_item)

        refresh_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Refresh Now", "refresh:", "")
        refresh_item.setTarget_(handler)
        menu.addItem_(refresh_item)

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quit:", "")
        quit_item.setTarget_(handler)
        menu.addItem_(quit_item)

        return menu

    def update_inline_items(self, sessions, ready_count):
        """Create/update one status bar item per session."""
        self.clear_inline_items()
        if not self.inline_mode or not sessions:
            return

        colors = get_colors()
        status_bar = NSStatusBar.systemStatusBar()
        ns_menu = self._build_nsmenu(sessions, ready_count)

        STATUS_COLORS = {
            "READY": colors["green"],
            "PERMISSION": colors["blue"],
            "WORKING": colors["orange"],
        }

        for sess in sessions:
            label = dir_name(sess["cwd"])
            color = STATUS_COLORS.get(sess["status"], colors["orange"])
            img = make_inline_image(label, color)

            item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
            button = item.button()
            button.setImage_(img)
            item.setMenu_(ns_menu)
            self.inline_items.append(item)

    def update_display(self):
        processes = get_claude_processes()
        sessions = []
        ready_count = 0
        new_ready_pids = set()

        for proc in processes:
            cwd = get_cwd(proc["pid"])
            children = get_working_children(proc["pid"])
            session_id = get_conversation_id(cwd)
            hook_state = get_hook_state(session_id)
            status, detail = infer_status(proc["cpu"], children, hook_state)
            if status == "WORKING":
                clear_hook_state(session_id)
            if status in ("READY", "PERMISSION"):
                ready_count += 1
                new_ready_pids.add(proc["pid"])
            sessions.append({
                **proc,
                "cwd": cwd,
                "children": children,
                "status": status,
                "detail": detail,
                "project": shorten_path(cwd),
            })

        self.sessions = sessions
        total = len(sessions)

        # Play sound if a NEW session became ready
        newly_ready = new_ready_pids - self.ready_pids
        if newly_ready:
            self.play_ready_sound()
        self.ready_pids = new_ready_pids

        # Update inline status bar items
        self.update_inline_items(sessions, ready_count)

        # Update main menu bar title (hidden when inline mode is active)
        if self.inline_mode and sessions:
            self.title = ""
            self._hide_main_icon()
        elif total == 0:
            self.title = "C"
            self._show_main_icon()
        else:
            has_permission = any(s["status"] == "PERMISSION" for s in sessions)
            has_ready = any(s["status"] == "READY" for s in sessions)
            dots = ""
            for s in sessions:
                if s["status"] == "READY":
                    dots += "\U0001F7E9"
                elif s["status"] == "PERMISSION":
                    dots += "\U0001F7E6"
                else:
                    dots += "\U0001F7E7"
            self.title = f"C {dots}"
            self._show_main_icon()

        # Rebuild dropdown menu
        self.menu.clear()

        if not sessions:
            self.menu.add(rumps.MenuItem("No active sessions"))
        else:
            summary = f"{total} session{'s' if total != 1 else ''}"
            if ready_count > 0:
                summary += f" — {ready_count} ready"
            self.menu.add(rumps.MenuItem(summary))
            self.menu.add(rumps.separator)

            STATUS_ICONS = {
                "READY": "\U0001F7E9",       # green square
                "PERMISSION": "\U0001F7E6",  # blue square
                "WORKING": "\U0001F7E7",     # orange square
            }
            for i, sess in enumerate(sessions):
                icon = STATUS_ICONS.get(sess["status"], "\u23F3")
                label = f"{icon} {sess['project']}  —  {sess['detail']}"
                item = rumps.MenuItem(label)

                item.add(rumps.MenuItem(f"PID: {sess['pid']}"))
                item.add(rumps.MenuItem(f"TTY: {sess['tty']}"))
                item.add(rumps.MenuItem(f"CPU: {sess['cpu']:.1f}%"))
                item.add(rumps.MenuItem(f"Uptime: {sess['elapsed']}"))

                self.menu.add(item)

        self.menu.add(rumps.separator)

        self.inline_toggle.state = self.inline_mode
        self.menu.add(self.inline_toggle)
        self.menu.add(rumps.MenuItem("Refresh Now", callback=self.manual_refresh))
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def _get_main_status_item(self):
        """Access the underlying NSStatusItem managed by rumps."""
        try:
            return self._nsapp.nsstatusitem
        except AttributeError:
            return None

    def _hide_main_icon(self):
        item = self._get_main_status_item()
        if item:
            item.setLength_(0)

    def _show_main_icon(self):
        item = self._get_main_status_item()
        if item:
            item.setLength_(NSVariableStatusItemLength)

    def play_ready_sound(self):
        """Play a subtle system sound."""
        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Tink.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    ClaudeMonitorApp().run()
