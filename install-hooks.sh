#!/bin/bash
set -e

# Install the Claude Code notification hooks required by Claude Monitor.
# This adds idle_prompt and permission_prompt hooks to your Claude settings
# so the monitor can detect session state accurately.

HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

echo "==> Installing monitor state hook..."
mkdir -p "$HOOKS_DIR"

cat > "$HOOKS_DIR/monitor-state.sh" << 'HOOKEOF'
#!/bin/bash
STATE_DIR="$HOME/.claude/monitor-state"
mkdir -p "$STATE_DIR"
STATE_TYPE="$1"
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
if [ -n "$SESSION_ID" ]; then
    echo "$STATE_TYPE" > "$STATE_DIR/$SESSION_ID"
fi
HOOKEOF
chmod +x "$HOOKS_DIR/monitor-state.sh"

echo "==> Adding notification hooks to Claude settings..."

if [ ! -f "$SETTINGS" ]; then
    echo "{}" > "$SETTINGS"
fi

python3 << 'PYEOF'
import json, sys

settings_path = sys.argv[1] if len(sys.argv) > 1 else "$HOME/.claude/settings.json"
import os
settings_path = os.path.expanduser("~/.claude/settings.json")

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})
notifications = hooks.get("Notification", [])

# Check if our hooks are already present
hook_cmd = os.path.expanduser("~/.claude/hooks/monitor-state.sh")
existing_matchers = {entry.get("matcher") for entry in notifications}

added = False
for matcher, arg in [("idle_prompt", "idle"), ("permission_prompt", "permission")]:
    if matcher not in existing_matchers:
        notifications.append({
            "matcher": matcher,
            "hooks": [{
                "type": "command",
                "command": f"{hook_cmd} {arg}",
                "timeout": 5,
            }]
        })
        added = True

if added:
    hooks["Notification"] = notifications
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print("   Hooks added to settings.json")
else:
    print("   Hooks already present, skipping")

PYEOF

echo ""
echo "Done! Claude Monitor hooks are installed."
echo "New Claude sessions will report their state to the monitor."
echo "(Existing sessions need to be restarted to pick up the hooks.)"
